"""PI-ConvLSTM shapes, overfit, physics penalties."""

from __future__ import annotations

import torch
from cofire.model.models.pi_convlstm import (
    CHANNELS,
    HIDDEN,
    SEQ_LEN,
    TILE,
    ConvLSTM,
    PhysicsCoeffs,
    fuel_loss,
    hydro_loss,
    task_loss,
    total_loss,
)


def _batch(b: int = 2) -> dict[str, torch.Tensor]:
    x = torch.randn(b, SEQ_LEN, len(CHANNELS), TILE, TILE)
    x[:, :, :, :, :] = x.abs()
    y_usdm = torch.randint(0, 5, (b, 3, TILE, TILE)).float()
    y_erc = torch.rand(b, 3, TILE, TILE) * 100
    mask = torch.ones(b, TILE, TILE, dtype=torch.bool)
    return {"x": x, "y_usdm": y_usdm, "y_erc": y_erc, "mask": mask}


def test_forward_shapes() -> None:
    net = ConvLSTM(in_ch=len(CHANNELS), hid=HIDDEN)
    batch = _batch(1)
    pred = net(batch["x"])
    assert pred["dryness"].shape == (1, SEQ_LEN, 1, TILE, TILE)
    assert pred["usdm_h4"].shape == (1, 1, TILE, TILE)
    assert pred["erc_pct_h8"].shape == (1, 1, TILE, TILE)


def test_overfit_single_batch() -> None:
    torch.manual_seed(0)
    net = ConvLSTM(in_ch=len(CHANNELS), hid=16)
    batch = _batch(1)
    opt = torch.optim.Adam(net.parameters(), lr=5e-3)
    first = None
    last = None
    for i in range(25):
        opt.zero_grad()
        pred = net(batch["x"])
        loss = task_loss(pred, batch["y_usdm"], batch["y_erc"], batch["mask"])
        loss.backward()
        opt.step()
        if i == 0:
            first = float(loss.detach())
        last = float(loss.detach())
    assert last is not None and first is not None
    assert last < first


def test_penalties_non_negative_and_zero_when_satisfied() -> None:
    b, t = 1, SEQ_LEN
    mask = torch.ones(b, TILE, TILE, dtype=torch.bool)
    # Dryness never rises faster than k * pet.
    pet = torch.ones(b, t, 1, TILE, TILE)
    dryness = torch.cumsum(0.1 * pet, dim=1)  # delta = 0.1, k=1 → 0.1 < 1
    h = hydro_loss(dryness, pet, mask, k=1.0)
    assert float(h) >= 0
    assert float(h) == 0.0
    # Violate: delta = 5, k*pet = 1
    dryness_bad = torch.cumsum(5 * pet, dim=1)
    h_bad = hydro_loss(dryness_bad, pet, mask, k=1.0)
    assert float(h_bad) > 0

    coeffs = PhysicsCoeffs(k=1.0, a=0.0, b=0.0, c=0.0)
    pred_fm = torch.full((b, t, 1, TILE, TILE), -1.0)  # below f=0
    vpd = torch.ones(b, t, 1, TILE, TILE)
    pr = torch.ones(b, t, 1, TILE, TILE)
    f0 = fuel_loss(pred_fm, vpd, pr, mask, coeffs)
    assert float(f0) == 0.0
    pred_wet = torch.full((b, t, 1, TILE, TILE), 2.0)
    f1 = fuel_loss(pred_wet, vpd, pr, mask, coeffs)
    assert float(f1) > 0


def test_lambda_zero_reproduces_task_loss() -> None:
    net = ConvLSTM(in_ch=len(CHANNELS), hid=8)
    batch = _batch(1)
    pred = net(batch["x"])
    coeffs = PhysicsCoeffs()
    task = task_loss(pred, batch["y_usdm"], batch["y_erc"], batch["mask"])
    total, parts = total_loss(pred, batch, coeffs, 0.0, 0.0)
    assert abs(float(total.detach()) - float(task.detach())) < 1e-5
    assert parts["total"] == float(total.detach())
