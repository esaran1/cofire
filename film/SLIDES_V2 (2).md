# COFIRE Demo Film v2: Slides

Four slides plus a short closing beat ("the turn"), placed 1:55 to 2:36. Built in Remotion with the app's design tokens, dark theme, and display face. Motion builds with the narration; the voice explains, the slide holds keywords.

Rules for every slide:
- Title plus at most 6 words per line. Nothing a judge has to pause to read.
- Every number comes from `facts.json`, artifacts, or `film/SOURCES.md`. Bracketed numbers are replaced with verified values or cut.
- Icons are generic shapes or plain text labels. No product logos or brand marks.
- The 3:00 countdown timer stays visible in its corner.

---

## Slide 1: How it's built

**Title:** How it's built

**Layout:** A row of labeled tiles that light up one by one as P1 names them.

| Tile | Label |
|---|---|
| Python | Data pipeline and models |
| xarray, pandas, SciPy, scikit-learn, statsmodels | Analysis libraries |
| TypeScript + React + Next.js | The app |
| MapLibre GL + PMTiles | The map |
| Postgres | Predictions and reports |
| GitHub Actions | Weekly auto-update |
| Playwright | Automated browser tests |

**Footer line, always visible:**
Open-source libraries listed in our repo · AI-assisted parts disclosed in AI_USAGE.md

**Motion:** Tiles stagger in left to right in sync with the voice. Footer fades in last and holds.

**Narration (P1):** Under the hood: Python for the data pipeline and models. TypeScript, React, and Next.js for the app. MapLibre for the map. GitHub Actions refreshes everything every week. We used AI coding tools for parts of the build, and our repo documents exactly where.

---

## Slide 2: The data

**Title:** Real data, checked every week

**Layout:** An animated left-to-right flow diagram.

Sources (left column):
- U.S. Drought Monitor
- gridMET fire danger
- SNOTEL snowpack
- Colorado EnviroScreen
- Denver Water

Middle: **Checked download** (allowlist, checksum, error-page rejection)

Right: **Weekly pipeline → COFIRE**

**Counters along the bottom, animating up from zero:**
- [19] years of history
- [5] areas
- [1,245] map cells at 4 km
- Updated weekly

**Motion:** Data flows as particles from each source into the check gate, then into the app. Counters tick up as P1 says them.

**Narration (P2):** Nineteen years of Drought Monitor and fire-danger data, [1,245] map cells, and every download checked before we trust it.

---

## Slide 3: Simple beat complex

**Title:** Simple beat complex

**Layout:** Four model cards in a row:
- Gradient boosting
- LSTM
- ConvLSTM
- Two-stage climate model

**Motion:** All four cards appear, then dim and slide away one at a time. One card remains and moves to center:

> **Weeks like this one → what happened next**

Caption under the remaining card:
> Calibrated. Explainable. Hard to beat.

**Narration (P2):** We tried [four] machine-learning models. The simplest one won: look at every week like today since 2007, and count what happened next. It's calibrated, and you can explain it in one sentence.

Note for the agent: confirm the exact count and names of the non-shipping arms from `research/README` before render. If the count differs, update both the narration and the cards.

---

## Slide 4: How we know it works

**Title:** Tested before we trusted it

**Layout:** A horizontal timeline, segments filling left to right:

| Years | Label |
|---|---|
| 2007 to 2021 | Train |
| 2022 to 2023 | Validate |
| 2024 to 2025 | Calibrate |
| 2026 | Locked · scored once (lock icon) |

**Three badges appear below the timeline, one at a time:**
- Shuffled-data control
- Multiple-testing correction
- [N] forecasts beat their baselines

**Narration (P2):** Then we locked away all of 2026 and tested on it exactly once. [N] forecasts beat their baselines.

**The turn, immediately after this slide:** the slide dims to black and music drops out. A single line appears in the display face, timed to P3 and P1:

> One result looked perfect.

A small "forecast band" chip appears, then a strike-through animates across it as P1 speaks:

> We found the flaw. We pulled it.

**P3:** One of our results looked perfect. That's what worried us.
**P1:** We dug in, found a flaw in how we'd tested it, and pulled it from the app. Now COFIRE says plainly when it can't back up a number.

Note for the agent: [N] is the current survivor count in `facts.json` after the leak-free refit and the 2022 map fix. Do not use an older count.

---

## Timing summary

| Slide | Start | Length |
|---|---|---|
| 1. How it's built | 1:55 | ~12 s |
| 2. The data | 2:07 | ~6 s |
| 3. Simple beat complex | 2:13 | ~9 s |
| 4. How we know it works | 2:22 | ~5 s |
| The turn | 2:27 | ~9 s |

If the total runs long, trim Slide 2 first, then Slide 3. Never cut Slide 1; it carries the required tools and languages and the AI disclosure.
