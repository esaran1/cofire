"""Executable leakage audit: what could actually have been read at issue time.

Two distinct questions, and the second is the harder one.

1. Latency. A value labelled "week of 2020-06-02" is not readable on 2020-06-02.
   ESI composites post several days after the compositing window closes; USDM
   publishes Thursday for a Tuesday valid date. `available_at(t)` returns the
   earliest timestamp at which a value for week t could have been read, and the
   feature builder asserts that no feature carries a value whose `available_at`
   is later than the issue date.

2. Reprocessing. ESI and EDDI are inputs the Drought Monitor authors themselves
   consult, so a model trained on today's archived value may be learning from a
   number that did not exist in that form at the time. The archived value can
   differ from the published one if the provider reprocessed the series. Where
   the provider exposes no versioned or dated copy to compare against, the
   source is marked `retrospectively_reprocessed: unknown` and its features are
   shifted one extra week as a conservative guard. The guard is behind a flag so
   the ablation can measure what it costs, because an unmeasured guard is just a
   guess with better manners.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum


class Reprocessing(str, Enum):
    """Whether the archived value can be shown to equal the published one."""

    VERSIONED = "versioned"  # provider exposes dated or versioned copies
    APPEND_ONLY = "append_only"  # provider states the archive is never revised
    UNKNOWN = "unknown"  # no way to tell; guard applies


@dataclass(frozen=True)
class SourceAvailability:
    """Latency and reprocessing posture for one source.

    `latency_days` is the lag from the nominal valid date to first publication.
    `extra_guard_weeks` is the additional shift applied when reprocessing status
    is unknown, so a possibly-revised value is never read at the issue it would
    have informed.
    """

    name: str
    latency_days: int
    reprocessing: Reprocessing
    note: str = ""

    @property
    def guard_weeks(self) -> int:
        return 1 if self.reprocessing is Reprocessing.UNKNOWN else 0

    def available_at(self, valid_week: date, *, apply_guard: bool = True) -> date:
        """Earliest date a value for `valid_week` could have been read."""
        d = valid_week + timedelta(days=self.latency_days)
        if apply_guard:
            d = d + timedelta(weeks=self.guard_weeks)
        return d

    def usable_at_issue(self, valid_week: date, issue: date, *, apply_guard: bool = True) -> bool:
        return self.available_at(valid_week, apply_guard=apply_guard) <= issue


# Latencies are the providers' own stated or observed posting lags.
#
# ESI: SERVIR posts a composite after its window closes; observed lag from the
#   day-of-year stamp to file availability is several days. 7 days is used as a
#   conservative round number rather than the observed minimum.
# EDDI: NOAA PSL posts next-day for a valid date.
# USDM: valid Tuesday, published Thursday.
# gridMET: ~5 day lag for the provisional product.
REGISTRY: dict[str, SourceAvailability] = {
    "esi_4wk": SourceAvailability(
        name="SERVIR ESI 4WK",
        latency_days=7,
        reprocessing=Reprocessing.UNKNOWN,
        note="No versioned or dated archive exposed; a single current file per date.",
    ),
    "esi_12wk": SourceAvailability(
        name="SERVIR ESI 12WK",
        latency_days=7,
        reprocessing=Reprocessing.UNKNOWN,
        note="Same archive structure as 4WK.",
    ),
    "eddi": SourceAvailability(
        name="NOAA EDDI",
        latency_days=1,
        reprocessing=Reprocessing.UNKNOWN,
        note="Flat archive, no version markers observed.",
    ),
    "usdm": SourceAvailability(
        name="US Drought Monitor",
        latency_days=2,
        reprocessing=Reprocessing.APPEND_ONLY,
        note="Weekly maps are the historical record and are not revised.",
    ),
    "gridmet": SourceAvailability(
        name="gridMET",
        latency_days=5,
        reprocessing=Reprocessing.UNKNOWN,
        note="Provisional values can be revised; treated conservatively.",
    ),
}


def assert_no_future_reads(
    source_key: str,
    valid_weeks: list[date],
    issue: date,
    *,
    apply_guard: bool = True,
) -> None:
    """Raise if any value would not have been readable at `issue`.

    Called by the feature builder. Failing loudly is the point: a silent
    future read is exactly the class of bug this project has already been bitten
    by twice.
    """
    av = REGISTRY.get(source_key)
    if av is None:
        raise KeyError(f"no availability record for source {source_key!r}")
    bad = [w for w in valid_weeks if not av.usable_at_issue(w, issue, apply_guard=apply_guard)]
    if bad:
        raise AssertionError(
            f"{av.name}: {len(bad)} value(s) would not have been readable at issue {issue}; "
            f"earliest offender {min(bad)} became available "
            f"{av.available_at(min(bad), apply_guard=apply_guard)}"
        )


def max_usable_week(source_key: str, issue: date, *, apply_guard: bool = True) -> date:
    """Latest valid week whose value was readable by `issue`."""
    av = REGISTRY[source_key]
    shift = timedelta(days=av.latency_days) + timedelta(weeks=av.guard_weeks if apply_guard else 0)
    return issue - shift


def audit_table(apply_guard: bool = True) -> list[dict[str, object]]:
    """Rows for docs/DATA.md, generated rather than typed by hand."""
    ref = date(2024, 6, 4)  # an arbitrary Tuesday, for illustration
    rows: list[dict[str, object]] = []
    for key, av in REGISTRY.items():
        rows.append(
            {
                "key": key,
                "source": av.name,
                "latency_days": av.latency_days,
                "reprocessing": av.reprocessing.value,
                "guard_weeks": av.guard_weeks if apply_guard else 0,
                "example_valid_week": ref.isoformat(),
                "readable_from": av.available_at(ref, apply_guard=apply_guard).isoformat(),
                "max_usable_week_for_that_issue": max_usable_week(
                    key, ref, apply_guard=apply_guard
                ).isoformat(),
                "note": av.note,
            }
        )
    return rows


# ------------------------------------------------------- reprocessing probe


def probe_reprocessing(
    url_builder: Callable[[date], str],
    sample_weeks: list[date],
    *,
    timeout: int = 20,
) -> dict[str, object]:
    """Ask whether the provider exposes any way to detect revision.

    The probe is deliberately cheap: it reads HTTP metadata only, never file
    bodies, so it costs no download budget. Three signals are checked:

      Last-Modified far later than the valid date suggests the file was
        rewritten after publication.
      ETag presence at least allows a future session to detect a change.
      A dated or versioned sibling path would allow a direct comparison.

    None of these can *prove* a file was never revised. The honest outcome is
    usually UNKNOWN, which is why the guard exists.
    """
    import requests

    from cofire.model.http import USER_AGENT

    findings: list[dict[str, object]] = []
    for wk in sample_weeks:
        url = url_builder(wk)
        try:
            r = requests.head(
                url, allow_redirects=True, timeout=timeout, headers={"User-Agent": USER_AGENT}
            )
            lm = r.headers.get("Last-Modified")
            findings.append(
                {
                    "week": wk.isoformat(),
                    "status": r.status_code,
                    "last_modified": lm,
                    "etag": r.headers.get("ETag"),
                }
            )
        except Exception as exc:  # noqa: BLE001
            findings.append({"week": wk.isoformat(), "status": "error", "error": str(exc)[:120]})

    have_lm = sum(1 for f in findings if f.get("last_modified"))
    have_etag = sum(1 for f in findings if f.get("etag"))

    # The decisive signal is not whether headers exist but whether the file was
    # written long after the week it describes. A composite modified months
    # after its valid date was demonstrably rewritten, which means the value in
    # the archive today is not necessarily the value published then.
    from email.utils import parsedate_to_datetime

    lags: list[float] = []
    for f in findings:
        lm_raw = f.get("last_modified")
        lm_str = lm_raw if isinstance(lm_raw, str) else None
        if not lm_str or not isinstance(f.get("week"), str):
            continue
        try:
            mod = parsedate_to_datetime(lm_str).date()
            wk = date.fromisoformat(str(f["week"]))
            lag = (mod - wk).days
            f["modified_lag_days"] = lag
            lags.append(lag)
        except (TypeError, ValueError):
            continue

    max_lag: float | None = max(lags) if lags else None
    # A lag beyond a month cannot be first publication of a weekly product.
    revised = [lag for lag in lags if lag > 31]
    if revised:
        verdict = Reprocessing.UNKNOWN.value
        reason = (
            f"{len(revised)} of {len(lags)} sampled files were last modified more than a "
            f"month after their valid week (max {max_lag} days), which is evidence of "
            "retrospective reprocessing rather than of an immutable archive"
        )
    elif have_lm == len(findings) and have_etag == len(findings):
        verdict = Reprocessing.UNKNOWN.value
        reason = (
            "Last-Modified and ETag are present on every sampled file, which lets a later "
            "session detect a change, but presence of headers cannot establish that the "
            "archived value equals the value published at the time"
        )
    else:
        verdict = Reprocessing.UNKNOWN.value
        reason = "no metadata available to detect revision"

    return {
        "n_probed": len(findings),
        "with_last_modified": have_lm,
        "with_etag": have_etag,
        "verdict": verdict,
        "reason": reason,
        "max_modified_lag_days": max_lag,
        "findings": findings,
        "note": (
            "Metadata-only probe, no bodies fetched, no budget consumed. Presence of "
            "Last-Modified and ETag lets a later session detect a change, but cannot "
            "establish that the value published at the time equalled the archived one."
        ),
    }
