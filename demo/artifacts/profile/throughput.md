# Statewide throughput profile

Measured on the Larimer subset, no statewide run launched. Every number here is timed on this
machine, not extrapolated from theory. Supersedes the v0.4 estimate of 11.2 h, which assumed cost
scales linearly with domain area. It does not.

## Where train time actually goes

LightGBM ERC h=4 on the full training split (100,320 rows x 95 features, 200 rounds) fits in
**3.58 s**. All six LightGBM fits (2 targets x 3 horizons) are ~21 s, i.e. **~3% of the 745.67 s
train stage**. The remaining ~97% is the three PI-ConvLSTM configs plus the group ablation.

Tuning LightGBM threading is therefore not worth doing for throughput. The section-6 premise that
`n_jobs` is the lever is wrong on this workload.

## LightGBM thread scaling (why `n_jobs` does not help)

| num_threads | time | speedup |
| --- | --- | --- |
| 1 | 3.58 s | 1.00x |
| 2 | 2.25 s | 1.59x |
| 4 | 2.16 s | 1.66x |
| 8 | 2.41 s | 1.49x |

Speedup saturates at ~1.66x by 4 threads and **regresses at 8** — this box has 10 logical / 4
performance cores, so past 4 threads the fits contend. Even a perfect 1.66x on 3% of the stage is a
~1% end-to-end win.

The 1-thread pin also exists for correctness, not just caution: unbounded OpenMP after LightGBM
deadlocked the PI-ConvLSTM fit at ~0% CPU (DECISIONS.md). Any unpinning must keep LightGBM in a
process that never subsequently imports torch. Given the ~1% payoff, **recommendation: keep the pin**.

## Tree training scales with rows^0.41, not linearly

Subsampling the training rows and refitting:

| rows | time |
| --- | --- |
| 12,540 | 0.94 s |
| 25,080 | 1.10 s |
| 50,160 | 1.45 s |
| 100,320 | 2.19 s |

Log-log fit: **time ~ rows^0.406**. So 50x the rows costs **4.9x** the time, not 50x — histogram
binning dominates and the bin count is fixed. This directly answers the section-6 question: the 50x
cell ratio does *not* translate to 50x training time for the tree arm. Statewide LightGBM is ~103 s.

## ConvLSTM: already tiled, and cost is linear in tile count

The ConvLSTM does **not** grow a domain tensor — `frame_to_samples` already emits 32x32 x T=8 tiles
into a `DataLoader` at `batch_size=4`. Measured tile memory against domain size:

| cells | tiles | build time | tile bytes |
| --- | --- | --- | --- |
| 120 | 201 | 0.1 s | 110.9 MB |
| 240 | 201 | 0.1 s | 110.9 MB |
| 480 | 201 | 0.1 s | 110.9 MB |

Tile count and memory are **flat** (`cells^0.00`) across the Larimer range because the whole 26x19
domain fits inside one 32x32 tile — so there is one tile per timestep and nothing to scale yet. The
v0.4 claim that ConvLSTM memory "grows superlinearly" is **not supported by measurement**; per-tile
cost is fixed by construction.

What does scale is the number of tiles per timestep:

| domain | grid at 4 km | tiles/timestep |
| --- | --- | --- |
| Larimer | 26 x 19 | 1 |
| Colorado (buffered) | 173 x 138 | 30 |

So the ConvLSTM cost multiplier is **30x**, linear in tiles, not 50x linear in cells.

One caveat this profile does *not* resolve: `frame_to_samples` builds dense full-domain cubes of
shape `(timesteps, height, width)` per channel *before* tiling. At Larimer that intermediate is
trivial; statewide it is ~173x138x261 float32 per channel (~50 MB each), which is why the staged
target below chunks feature construction per year rather than materialising all years at once.

## Revised ETA

| stage | Larimer | statewide | basis |
| --- | --- | --- | --- |
| LightGBM (6 fits) | 21 s | ~103 s | rows^0.41 |
| PI-ConvLSTM + ablation | ~724 s | ~6.0 h | 30x tiles, linear |
| **train total** | 745.67 s | **~6.1 h** | measured |

Down from the v0.4 figure of 10.4 h for train. Still well over the 60-minute stop rule, so it must
be staged — which is what `make statewide` below does. It is not a single background job.
