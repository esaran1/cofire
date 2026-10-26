# COFIRE Demo Film v2: Slides

Four slides, about 10 seconds each, placed 1:58 to 2:40. Built in Remotion with the app's design tokens, dark theme, and display face. Motion builds with the narration; the voice explains, the slide holds keywords.

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

**Narration (P1):** Here's what's under the hood. Python for the data and models. TypeScript, React, and Next.js for the app. MapLibre for the map. GitHub Actions runs the weekly update. We used AI coding tools for parts of the build, and we documented exactly where in our repo.

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

**Narration (P1):** Nineteen years of the U.S. Drought Monitor and fire-danger data, across [five] areas and [1,245] map cells. Every download is checked before we trust it.

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

**Narration (P2):** We tried [four] neural-network models. The simple one won: for every week like today since 2007, count what happened next. It beat the fancy ones, and you can explain it in one sentence.

Note for the agent: confirm the exact count and names of the non-shipping arms from `research/README` before render. If the count differs, update both the narration and the cards. Use "models" rather than "neural-network models" if any arm is not a neural network.

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

**Bottom line, appears last on P3's line, with a strike-through animation on a small "forecast band" chip:**
> Found a bug in our best result → removed it

**Narration:**
**P2:** We locked away all of 2026 before testing, and scored it once. We checked every result against shuffled data. [N] forecasts beat their baselines.
**P3:** And when we found a bug in our own best result, we took it out of the app and said why.

Note for the agent: [N] is the current survivor count in `facts.json` after the leak-free refit and the 2022 map fix. Do not use an older count.

---

## Timing summary

| Slide | Start | Length |
|---|---|---|
| 1. How it's built | 1:58 | ~10 s |
| 2. The data | 2:08 | ~9 s |
| 3. Simple beat complex | 2:17 | ~10 s |
| 4. How we know it works | 2:27 | ~13 s |

If the total runs long, trim Slide 2 first, then Slide 3. Never cut Slide 1; it carries the required tools and languages and the AI disclosure.
