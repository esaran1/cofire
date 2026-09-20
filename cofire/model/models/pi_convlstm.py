"""Physics-informed ConvLSTM for drought and fire-spread conditions.

INTENDED FOR HAND-REWRITE. Two ConvLSTM layers, 1x1 heads, no attention.
Implemented from scratch against Colorado gridMET tiles. See docs/PRIOR_ART.md
for what is precedent (physics-informed loss + anti-leakage) and what is new
(fuel-moisture constraint, fire-condition targets, Colorado domain).

Input  x : (B, T=8, C, 32, 32)
Output    : per-cell USDM ordinal and ERC percentile at horizons 2, 4, 8 weeks,
            plus auxiliary dryness / fm100 / fm1000 trajectories used only by
            the physics penalties.

Loss
----
    L = L_task + lambda_hydro * L_hydro + lambda_fuel * L_fuel

`lambda_* = 0` MUST reproduce L_task (tested). Coefficients k and f(·) are fit
on the training split only and then frozen.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset

from cofire.model.config import HORIZONS_WEEKS, SEED, get_settings
from cofire.model.models import PRED_COLS, ConditionModel

TILE = 32
SEQ_LEN = 8
HIDDEN = 64
KERNEL = 3
# Channels packed into the tensor. Order is part of the contract; do not reorder
# without updating CHANNELS and the physics-term index constants below.
CHANNELS: tuple[str, ...] = (
    "pr",
    "pet",
    "tmmx",
    "vpd",
    "erc",
    "bi",
    "fm100",
    "fm1000",
    "usdm",
    "swe_pct_median",
    "elev_mean",
    "elev_roughness",
    "erc_pct",
    "fm1000_anom",
    "fm100_anom",
    "pr_roll4",
)
CH_PET = CHANNELS.index("pet")
CH_VPD = CHANNELS.index("vpd")
CH_PR28 = CHANNELS.index("pr_roll4")  # 4-week precip ≈ 28 days
CH_FM1000_ANOM = CHANNELS.index("fm1000_anom")
CH_FM100_ANOM = CHANNELS.index("fm100_anom")


class ConvLSTMCell(nn.Module):
    def __init__(self, in_ch: int, hid: int, k: int = KERNEL) -> None:
        super().__init__()
        self.hid = hid
        self.conv = nn.Conv2d(in_ch + hid, 4 * hid, k, padding=k // 2)

    def forward(
        self, x: torch.Tensor, h: torch.Tensor, c: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor]:
        gates = self.conv(torch.cat([x, h], dim=1))
        i, f, o, g = torch.chunk(gates, 4, dim=1)
        i, f, o = torch.sigmoid(i), torch.sigmoid(f), torch.sigmoid(o)
        g = torch.tanh(g)
        c = f * c + i * g
        h = o * torch.tanh(c)
        return h, c


class ConvLSTM(nn.Module):
    def __init__(self, in_ch: int, hid: int = HIDDEN) -> None:
        super().__init__()
        self.cell1 = ConvLSTMCell(in_ch, hid)
        self.cell2 = ConvLSTMCell(hid, hid)
        # Task heads: last hidden → 3 horizons × (usdm, erc, ge2 logit, ge3 logit)
        self.task_head = nn.Conv2d(hid, 3 * 4, 1)
        # Aux heads decoded every step so L_hydro / L_fuel see a trajectory.
        self.dry_head = nn.Conv2d(hid, 1, 1)
        self.fm100_head = nn.Conv2d(hid, 1, 1)
        self.fm1000_head = nn.Conv2d(hid, 1, 1)
        self.hid = hid

    def forward(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        # x: (B, T, C, H, W)
        b, t, _, h, w = x.shape
        device = x.device
        h1 = torch.zeros(b, self.hid, h, w, device=device)
        c1 = torch.zeros(b, self.hid, h, w, device=device)
        h2 = torch.zeros(b, self.hid, h, w, device=device)
        c2 = torch.zeros(b, self.hid, h, w, device=device)
        dryness, fm100, fm1000 = [], [], []
        for step in range(t):
            h1, c1 = self.cell1(x[:, step], h1, c1)
            h2, c2 = self.cell2(h1, h2, c2)
            dryness.append(self.dry_head(h2))
            fm100.append(self.fm100_head(h2))
            fm1000.append(self.fm1000_head(h2))
        task = self.task_head(h2)  # (B, 12, H, W) = 3 horizons × 4
        out: dict[str, torch.Tensor] = {
            "dryness": torch.stack(dryness, dim=1),  # (B, T, 1, H, W)
            "fm100_anom": torch.stack(fm100, dim=1),
            "fm1000_anom": torch.stack(fm1000, dim=1),
        }
        for i, horizon in enumerate(HORIZONS_WEEKS):
            base = i * 4
            out[f"usdm_h{horizon}"] = task[:, base : base + 1]
            out[f"erc_pct_h{horizon}"] = task[:, base + 1 : base + 2]
            out[f"ge2_h{horizon}"] = task[:, base + 2 : base + 3]
            out[f"ge3_h{horizon}"] = task[:, base + 3 : base + 4]
        return out


@dataclass
class PhysicsCoeffs:
    """Frozen after the training split. Never refit on val/hindcast."""

    # Max dryness increase per mm of PET (99th percentile of train positives).
    k: float = 1.0
    # f(vpd, precip_28d) = a + b * vpd + c * precip_28d  (fm anomaly upper bound)
    a: float = 0.0
    b: float = 0.0  # clipped ≤ 0  (higher VPD → drier → lower fm anomaly)
    c: float = 0.0  # clipped ≥ 0  (more rain → wetter fuels)
    n_hydro: int = 0
    n_fuel: int = 0


def fit_physics_coeffs(train_tensors: list[dict[str, np.ndarray]]) -> PhysicsCoeffs:
    """Fit k and f on training tiles only.

    k: 99th percentile of week-over-week (-fm1000_anom) / pet among cells with
    pet > 0 and a positive drying step. This is an empirical PET-implied cap,
    not a tuned hyperparameter.

    f: OLS of observed fm1000_anom on (vpd, precip_28d), then clip coefficients
    so the relation is monotone in the physically expected direction.
    """
    deltas: list[float] = []
    vpd_list: list[float] = []
    pr_list: list[float] = []
    fm_list: list[float] = []
    for sample in train_tensors:
        x = sample["x"]  # (T, C, H, W)
        mask = sample["mask"]  # (H, W) bool
        dryness = -x[:, CH_FM1000_ANOM]
        pet = x[:, CH_PET]
        for t in range(1, x.shape[0]):
            d = dryness[t] - dryness[t - 1]
            p = pet[t]
            valid = mask & np.isfinite(d) & np.isfinite(p) & (p > 0) & (d > 0)
            if valid.any():
                deltas.extend((d[valid] / p[valid]).astype(float).tolist())
        vpd = x[-1, CH_VPD]
        pr28 = x[-1, CH_PR28]
        fm = x[-1, CH_FM1000_ANOM]
        valid2 = mask & np.isfinite(vpd) & np.isfinite(pr28) & np.isfinite(fm)
        if valid2.any():
            vpd_list.extend(vpd[valid2].astype(float).tolist())
            pr_list.extend(pr28[valid2].astype(float).tolist())
            fm_list.extend(fm[valid2].astype(float).tolist())
    k = float(np.quantile(deltas, 0.99)) if len(deltas) >= 20 else 1.0
    k = max(k, 1e-4)
    if len(fm_list) >= 20:
        a_mat = np.column_stack(
            [np.ones(len(fm_list)), np.asarray(vpd_list), np.asarray(pr_list)]
        )
        coef, *_ = np.linalg.lstsq(a_mat, np.asarray(fm_list), rcond=None)
        a, b, c = (float(coef[0]), float(min(coef[1], 0.0)), float(max(coef[2], 0.0)))
    else:
        a, b, c = 0.0, 0.0, 0.0
    return PhysicsCoeffs(k=k, a=a, b=b, c=c, n_hydro=len(deltas), n_fuel=len(fm_list))


def task_loss(
    pred: dict[str, torch.Tensor],
    y_usdm: torch.Tensor,
    y_erc: torch.Tensor,
    mask: torch.Tensor,
) -> torch.Tensor:
    """MSE on ERC percentile + soft-ordinal drought (MSE on 0–4 + BCE on ≥2, ≥3).

    y_usdm, y_erc: (B, 3, H, W)  — one channel per horizon, NaN where unlabeled.
    mask: (B, 1, H, W) valid cells.
    """
    total = y_erc.new_zeros(())
    n_h = len(HORIZONS_WEEKS)
    for i, horizon in enumerate(HORIZONS_WEEKS):
        m_usdm = mask.squeeze(1) & torch.isfinite(y_usdm[:, i])
        m_erc = mask.squeeze(1) & torch.isfinite(y_erc[:, i])
        usdm_hat = pred[f"usdm_h{horizon}"].squeeze(1)
        erc_hat = pred[f"erc_pct_h{horizon}"].squeeze(1)
        if m_erc.any():
            total = total + torch.mean((erc_hat[m_erc] - y_erc[:, i][m_erc]) ** 2)
        if m_usdm.any():
            target = y_usdm[:, i][m_usdm]
            total = total + torch.mean((usdm_hat[m_usdm] - target) ** 2)
            ge2 = pred[f"ge2_h{horizon}"].squeeze(1)[m_usdm]
            ge3 = pred[f"ge3_h{horizon}"].squeeze(1)[m_usdm]
            total = total + nn.functional.binary_cross_entropy_with_logits(ge2, (target >= 2).float())
            total = total + nn.functional.binary_cross_entropy_with_logits(ge3, (target >= 3).float())
    return total / n_h


def hydro_loss(
    dryness: torch.Tensor,
    pet: torch.Tensor,
    mask: torch.Tensor,
    k: float,
) -> torch.Tensor:
    """Penalize drying faster than PET can evaporate.

    dryness, pet: (B, T, 1, H, W)  (pet is broadcast from the input channel)
    relu(delta_dryness - k * pet_week)^2  summed over steps, masked.

    When the trajectory already respects the cap, this term is exactly 0.
    """
    delta = dryness[:, 1:] - dryness[:, :-1]
    pet_step = pet[:, 1:]
    excess = torch.relu(delta - k * pet_step)
    # mask is (B, H, W) → (B, 1, 1, H, W) to match (B, T-1, 1, H, W)
    m = mask[:, None, None, :, :].expand_as(excess)
    m = m & torch.isfinite(excess)
    if not m.any():
        return dryness.new_zeros(())
    return torch.mean(excess[m] ** 2)


def fuel_loss(
    pred_fm: torch.Tensor,
    vpd: torch.Tensor,
    precip_28d: torch.Tensor,
    mask: torch.Tensor,
    coeffs: PhysicsCoeffs,
) -> torch.Tensor:
    """Penalize fm anomalies wetter than the training-split monotone bound f.

    f = a + b * vpd + c * precip_28d, with b ≤ 0, c ≥ 0.
    relu(pred_fm_anomaly - f)^2. Zero when pred_fm ≤ f.
    """
    bound = coeffs.a + coeffs.b * vpd + coeffs.c * precip_28d
    excess = torch.relu(pred_fm - bound)
    m = mask[:, None, None, :, :].expand_as(excess)
    m = m & torch.isfinite(excess)
    if not m.any():
        return pred_fm.new_zeros(())
    return torch.mean(excess[m] ** 2)


def total_loss(
    pred: dict[str, torch.Tensor],
    batch: dict[str, torch.Tensor],
    coeffs: PhysicsCoeffs,
    lambda_hydro: float,
    lambda_fuel: float,
) -> tuple[torch.Tensor, dict[str, float]]:
    l_task = task_loss(pred, batch["y_usdm"], batch["y_erc"], batch["mask"])
    pet = batch["x"][:, :, CH_PET : CH_PET + 1]
    vpd = batch["x"][:, :, CH_VPD : CH_VPD + 1]
    pr28 = batch["x"][:, :, CH_PR28 : CH_PR28 + 1]
    l_hydro = hydro_loss(pred["dryness"], pet, batch["mask"], coeffs.k)
    l_fuel = fuel_loss(pred["fm1000_anom"], vpd, pr28, batch["mask"], coeffs)
    loss = l_task + lambda_hydro * l_hydro + lambda_fuel * l_fuel
    parts = {
        "task": float(l_task.detach()),
        "hydro": float(l_hydro.detach()),
        "fuel": float(l_fuel.detach()),
        "total": float(loss.detach()),
    }
    return loss, parts


class TileDataset(Dataset[dict[str, torch.Tensor]]):
    def __init__(self, samples: list[dict[str, np.ndarray]]) -> None:
        self.samples = samples

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        s = self.samples[idx]
        return {
            "x": torch.from_numpy(s["x"]).float(),
            "y_usdm": torch.from_numpy(s["y_usdm"]).float(),
            "y_erc": torch.from_numpy(s["y_erc"]).float(),
            "mask": torch.from_numpy(s["mask"]).bool(),
        }


def pad_grid(arr: np.ndarray, h: int = TILE, w: int = TILE) -> np.ndarray:
    """Pad / crop a (C, H, W) or (H, W) array to (…, 32, 32)."""
    if arr.ndim == 2:
        arr = arr[None, ...]
        squeeze = True
    else:
        squeeze = False
    c, hh, ww = arr.shape
    out = np.zeros((c, h, w), dtype=arr.dtype)
    out[:, : min(hh, h), : min(ww, w)] = arr[:, : min(hh, h), : min(ww, w)]
    return out[0] if squeeze else out


def frame_to_samples(frame: pd.DataFrame) -> list[dict[str, np.ndarray]]:
    """Build overlapping (or single padded) 32×32 × T=8 samples from a long table."""
    frame = frame.copy()
    frame["time"] = pd.to_datetime(frame["time"])
    lats = np.sort(frame["lat"].unique())[::-1]
    lons = np.sort(frame["lon"].unique())
    times = np.sort(frame["time"].unique())
    h0, w0 = len(lats), len(lons)
    lat_i = {float(v): i for i, v in enumerate(lats)}
    lon_i = {float(v): i for i, v in enumerate(lons)}
    cubes: dict[str, np.ndarray] = {}
    for ch in CHANNELS:
        grid = np.full((len(times), h0, w0), np.nan, dtype=np.float32)
        if ch in frame.columns:
            for row in frame.itertuples():
                yi = lat_i.get(float(row.lat))
                xi = lon_i.get(float(row.lon))
                ti = int(np.searchsorted(times, row.time))
                if yi is None or xi is None or ti >= len(times):
                    continue
                grid[ti, yi, xi] = float(getattr(row, ch, np.nan))
        cubes[ch] = grid
    y_usdm = np.full((len(times), len(HORIZONS_WEEKS), h0, w0), np.nan, dtype=np.float32)
    y_erc = np.full_like(y_usdm, np.nan)
    for i, h in enumerate(HORIZONS_WEEKS):
        col_u, col_e = f"usdm_h{h}", f"erc_pct_h{h}"
        if col_u in frame.columns:
            for row in frame.itertuples():
                yi = lat_i.get(float(row.lat))
                xi = lon_i.get(float(row.lon))
                ti = int(np.searchsorted(times, row.time))
                if yi is None or xi is None or ti >= len(times):
                    continue
                y_usdm[ti, i, yi, xi] = float(getattr(row, col_u, np.nan))
        if col_e in frame.columns:
            for row in frame.itertuples():
                yi = lat_i.get(float(row.lat))
                xi = lon_i.get(float(row.lon))
                ti = int(np.searchsorted(times, row.time))
                if yi is None or xi is None or ti >= len(times):
                    continue
                y_erc[ti, i, yi, xi] = float(getattr(row, col_e, np.nan))
    mask0 = np.zeros((h0, w0), dtype=bool)
    if "erc" in frame.columns:
        last = cubes["erc"]
        mask0 = np.isfinite(last).any(axis=0)
    else:
        mask0[:, :] = True

    # Single padded tile when the domain is smaller than 32×32 (Larimer).
    # Statewide: stride-24 overlapping tiles.
    origins: list[tuple[int, int]] = [(0, 0)]
    if h0 > TILE or w0 > TILE:
        origins = []
        stride = TILE - 8
        for y0 in range(0, max(h0 - TILE, 0) + 1, stride):
            for x0 in range(0, max(w0 - TILE, 0) + 1, stride):
                origins.append((y0, x0))
        if not origins:
            origins = [(0, 0)]

    samples: list[dict[str, np.ndarray]] = []
    for t0 in range(0, len(times) - SEQ_LEN):
        t_slice = slice(t0, t0 + SEQ_LEN)
        t_last = t0 + SEQ_LEN - 1
        for y0, x0 in origins:
            x_ch = []
            for ch in CHANNELS:
                patch = cubes[ch][t_slice, y0 : y0 + TILE, x0 : x0 + TILE]
                # pad if the patch is short
                padded = np.zeros((SEQ_LEN, TILE, TILE), dtype=np.float32)
                padded[:, : patch.shape[1], : patch.shape[2]] = patch
                x_ch.append(padded)
            x = np.stack(x_ch, axis=1)  # (T, C, h, w)
            yu = np.zeros((len(HORIZONS_WEEKS), TILE, TILE), dtype=np.float32)
            ye = np.zeros_like(yu)
            src_u = y_usdm[t_last, :, y0 : y0 + TILE, x0 : x0 + TILE]
            src_e = y_erc[t_last, :, y0 : y0 + TILE, x0 : x0 + TILE]
            yu[:, : src_u.shape[1], : src_u.shape[2]] = src_u
            ye[:, : src_e.shape[1], : src_e.shape[2]] = src_e
            m = np.zeros((TILE, TILE), dtype=bool)
            m[: min(TILE, mask0.shape[0] - y0), : min(TILE, mask0.shape[1] - x0)] = mask0[
                y0 : y0 + TILE, x0 : x0 + TILE
            ]
            samples.append(
                {
                    "x": np.nan_to_num(x, nan=0.0),
                    "y_usdm": yu,
                    "y_erc": ye,
                    "mask": m,
                    "t_last": np.asarray(t_last),
                    "y0": np.asarray(y0),
                    "x0": np.asarray(x0),
                    "lat0": lats,
                    "lon0": lons,
                    "times": times,
                }
            )
    return samples


class PhysicsInformedConvLSTM(ConditionModel):
    name = "pi_convlstm"

    def __init__(
        self,
        lambda_hydro: float = 0.1,
        lambda_fuel: float = 0.1,
        seed: int = SEED,
        max_epochs: int = 12,
        patience: int = 3,
    ) -> None:
        self.lambda_hydro = lambda_hydro
        self.lambda_fuel = lambda_fuel
        self.seed = seed
        self.max_epochs = max_epochs
        self.patience = patience
        self.coeffs = PhysicsCoeffs()
        self.net = ConvLSTM(in_ch=len(CHANNELS))
        self.lat_axis: np.ndarray | None = None
        self.lon_axis: np.ndarray | None = None
        self.tag = f"hydro{lambda_hydro}_fuel{lambda_fuel}"

    def fit(self, train: pd.DataFrame, valid: pd.DataFrame | None = None) -> None:
        torch.manual_seed(self.seed)
        np.random.seed(self.seed)
        train_samples = frame_to_samples(train)
        if not train_samples:
            return
        self.lat_axis = train_samples[0]["lat0"]
        self.lon_axis = train_samples[0]["lon0"]
        self.coeffs = fit_physics_coeffs(train_samples)
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.net.to(device)
        loader = DataLoader(TileDataset(train_samples), batch_size=4, shuffle=True)
        valid_loader = None
        if valid is not None and len(valid):
            vs = frame_to_samples(valid)
            if vs:
                valid_loader = DataLoader(TileDataset(vs), batch_size=4, shuffle=False)
        opt = torch.optim.Adam(self.net.parameters(), lr=1e-3)
        use_amp = device.type == "cuda"
        scaler = torch.cuda.amp.GradScaler(enabled=use_amp)
        best = float("inf")
        stale = 0
        best_state = {k: v.detach().cpu().clone() for k, v in self.net.state_dict().items()}
        for _epoch in range(self.max_epochs):
            self.net.train()
            for batch in loader:
                batch = {k: v.to(device) if torch.is_tensor(v) else v for k, v in batch.items()}
                opt.zero_grad(set_to_none=True)
                with torch.cuda.amp.autocast(enabled=use_amp):
                    pred = self.net(batch["x"])
                    loss, _parts = total_loss(
                        pred, batch, self.coeffs, self.lambda_hydro, self.lambda_fuel
                    )
                scaler.scale(loss).backward()  # type: ignore[no-untyped-call]
                scaler.step(opt)
                scaler.update()
            if valid_loader is None:
                continue
            val = self._eval_task(valid_loader, device)
            if val + 1e-6 < best:
                best = val
                stale = 0
                best_state = {k: v.detach().cpu().clone() for k, v in self.net.state_dict().items()}
            else:
                stale += 1
                if stale >= self.patience:
                    break
        self.net.load_state_dict(best_state)
        self.net.to("cpu")
        self.net.eval()

    def _eval_task(self, loader: DataLoader[dict[str, torch.Tensor]], device: torch.device) -> float:
        self.net.eval()
        total = 0.0
        n = 0
        with torch.no_grad():
            for batch in loader:
                batch = {k: v.to(device) if torch.is_tensor(v) else v for k, v in batch.items()}
                pred = self.net(batch["x"])
                loss = task_loss(pred, batch["y_usdm"], batch["y_erc"], batch["mask"])
                total += float(loss)
                n += 1
        return total / max(n, 1)

    def predict(self, frame: pd.DataFrame) -> pd.DataFrame:
        samples = frame_to_samples(frame)
        out = pd.DataFrame(index=frame.index)
        for col in PRED_COLS:
            out[col] = np.nan
        if not samples:
            return out
        self.net.eval()
        # Map (time, lat, lon) → row index for writing predictions.
        frame = frame.copy()
        frame["time"] = pd.to_datetime(frame["time"])
        key_to_pos = {
            (pd.Timestamp(r.time), round(float(r.lat), 4), round(float(r.lon), 4)): i
            for i, r in enumerate(frame.itertuples())
        }
        acc: dict[str, dict[int, list[float]]] = {c: {} for c in PRED_COLS}
        with torch.no_grad():
            for sample in samples:
                x = torch.from_numpy(sample["x"][None, ...]).float()
                pred = self.net(x)
                t_last = int(sample["t_last"])
                times = sample["times"]
                lats = sample["lat0"]
                lons = sample["lon0"]
                y0 = int(sample["y0"])
                x0 = int(sample["x0"])
                issue = pd.Timestamp(times[t_last])
                for h in HORIZONS_WEEKS:
                    usdm = pred[f"usdm_h{h}"][0, 0].numpy()
                    erc = pred[f"erc_pct_h{h}"][0, 0].numpy()
                    ge2 = torch.sigmoid(pred[f"ge2_h{h}"][0, 0]).numpy()
                    ge3 = torch.sigmoid(pred[f"ge3_h{h}"][0, 0]).numpy()
                    for yi in range(min(TILE, len(lats) - y0)):
                        for xi in range(min(TILE, len(lons) - x0)):
                            lat = round(float(lats[y0 + yi]), 4)
                            lon = round(float(lons[x0 + xi]), 4)
                            pos = key_to_pos.get((issue, lat, lon))
                            if pos is None:
                                continue
                            for col, val in (
                                (f"usdm_h{h}_hat", float(usdm[yi, xi])),
                                (f"erc_pct_h{h}_hat", float(erc[yi, xi])),
                                (f"usdm_ge2_h{h}_hat", float(ge2[yi, xi])),
                                (f"usdm_ge3_h{h}_hat", float(ge3[yi, xi])),
                            ):
                                acc[col].setdefault(pos, []).append(val)
        for col, mapping in acc.items():
            for pos, vals in mapping.items():
                out.iloc[pos, out.columns.get_loc(col)] = float(np.mean(vals))
        return out

    def extra(self) -> dict[str, float | int | str]:
        d = asdict(self.coeffs)
        d["lambda_hydro"] = self.lambda_hydro
        d["lambda_fuel"] = self.lambda_fuel
        d["tag"] = self.tag
        return d

    def save(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        torch.save(self.net.state_dict(), path / "weights.pt")
        meta = {
            "lambda_hydro": self.lambda_hydro,
            "lambda_fuel": self.lambda_fuel,
            "coeffs": asdict(self.coeffs),
            "seed": self.seed,
        }
        (path / "meta.json").write_text(json.dumps(meta, indent=2))

    @classmethod
    def load(cls, path: Path) -> PhysicsInformedConvLSTM:
        meta = json.loads((path / "meta.json").read_text())
        inst = cls(lambda_hydro=float(meta["lambda_hydro"]), lambda_fuel=float(meta["lambda_fuel"]))
        inst.coeffs = PhysicsCoeffs(**meta["coeffs"])
        inst.net.load_state_dict(torch.load(path / "weights.pt", map_location="cpu"))
        inst.net.eval()
        return inst


def get_settings_device() -> torch.device:
    _ = get_settings()
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")
