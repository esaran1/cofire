# Data sources

Generated in part from `cofire/model/data/availability.py` and `data/ledger.json`.
Do not hand-edit the audit table; regenerate it.

## New in v1.0

| product | provider | native res | coverage | latency | license | subset fetched | bytes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ESI 4-week composite | SERVIR / ALEXI | 0.05 deg (~5 km) | 2001 to present, weekly | ~7 days | public, no key | domain bbox window via HTTP range | 801 MB |
| ESI 12-week composite | SERVIR / ALEXI | 0.05 deg (~5 km) | 2001 to present, weekly | ~7 days | public, no key | domain bbox window, biweekly sampled | 201 MB |
| EDDI 4-week | NOAA PSL | 0.125 deg (~12 km) | 1980 to present, daily | ~1 day | public, no key | CONUS grid, clipped on arrival | 23 MB (deferred) |

### Why ESI is fetched by windowed read

Each global ESI GeoTIFF is 86 MB. The server answers HTTP range requests, so GDAL's
`/vsicurl/` driver reads only the scanlines covering the domain: **1.93 MB per file
against 86 MB, a 45x saving**. The files are striped rather than tiled, so a read still
costs whole scanlines, and that is priced into the budget rather than wished away.

### Why ESI 12WK is sampled biweekly

A 12-week composite changes little week to week. Sampling every second week and
interpolating halves the bytes. That claim is tested rather than assumed:
`tests/test_esi_interp.py` reconstructs the dropped weeks and requires the mean
absolute error to stay under 20% of the series' own standard deviation. Measured on
real fetched data, **ESI 12WK scores 0.166** and the faster-moving 4-week composite
scores 0.229, which is exactly why 12WK is strided and 4WK is not. Interpolation is
behind a flag so the ablation runs with and without it.

### Why EDDI was deferred

EDDI has no subsetting endpoint, no compression and no tiled format, so each file costs
its full 1.77 MB whatever the domain. With ESI at both products across both domains the
remaining budget bought 132 EDDI weeks, too short to span the training window, which
would make it useless as a training feature rather than merely weaker. Its 4-week
evaporative demand also largely duplicates what gridMET already carries through VPD,
reference ET and precipitation deficits. The source class is implemented and working; it
needs its own budget. See DECISIONS.md.

## Leakage audit

Two separate questions. First, whether a value existed at issue time. Second, and harder,
whether the value archived today equals the value published then. ESI and EDDI are inputs
the Drought Monitor authors themselves consult, so the second question matters.

### Latency and guard, generated

| source | latency (days) | reprocessing | guard (weeks) | example valid week | readable from | max usable week for that issue |
| --- | --- | --- | --- | --- | --- | --- |
| SERVIR ESI 4WK | 7 | unknown | 1 | 2024-06-04 | 2024-06-18 | 2024-05-21 |
| SERVIR ESI 12WK | 7 | unknown | 1 | 2024-06-04 | 2024-06-18 | 2024-05-21 |
| NOAA EDDI | 1 | unknown | 1 | 2024-06-04 | 2024-06-12 | 2024-05-27 |
| US Drought Monitor | 2 | append_only | 0 | 2024-06-04 | 2024-06-06 | 2024-06-02 |
| gridMET | 5 | unknown | 1 | 2024-06-04 | 2024-06-16 | 2024-05-23 |

`assert_no_future_reads` is called by the feature builder and raises if any feature
carries a value whose `available_at` is later than the issue date. Eleven tests cover it,
including that `max_usable_week` is tight: one day later must fail, or the bound is loose
and is costing skill for nothing.

### Reprocessing probe, measured

**Verdict: `unknown`.** 1 of 4 sampled files were last modified more than a month after their valid week (max 273 days), which is evidence of retrospective reprocessing rather than of an immutable archive.

| sampled valid week | file last modified | lag |
| --- | --- | --- |
| 2019-06-04 | Tue, 25 Jun 2019 17:39:13 | 21 days |
| 2021-03-02 | Tue, 30 Nov 2021 03:54:34 | 273 days |
| 2023-08-01 | Fri, 18 Aug 2023 15:40:02 | 17 days |
| 2025-05-06 | Mon, 05 May 2025 15:31:18 | -1 days |

The probe reads HTTP metadata only and never file bodies, so it costs no download budget.

This is not a formality. One sampled ESI file was **last modified 273 days after its valid
week**, which is direct evidence that the archive is rewritten after publication rather
than being an immutable record. A model trained on today's archived value may therefore be
learning from a number that did not exist in that form at the time. Because SERVIR exposes
no dated or versioned copy to compare against, ESI is encoded as
`retrospectively_reprocessed: unknown` and its features are shifted one extra week as a
conservative guard. The guard is behind a flag so the ablation can measure what it costs;
an unmeasured guard is a guess with better manners.

