# Film v2: changes made to SCRIPT_V2.md and SLIDES_V2.md, and why

The script and slides were followed, except where a line said something the
repository or a primary source does not support, or the cut could not fit
under 2:58. Each change uses the fewest words that make the line true.
`script/v2/lines.json` holds the lines as recorded.

## Changed because they were not true

| Where | Script said | Film says | Why |
|---|---|---|---|
| Cold open 1 | "Ninety-four percent of Colorado. In drought." | "Sixty-one percent of Colorado. In drought." | The latest U.S. Drought Monitor map (Oct 20) is 61.05% D1 to D4 (SOURCES.md). |
| Cold open 2 | "Two hundred thirty-five thousand acres burned this year." | "About eighty percent of Denver's drinking water passes through one reservoir." | No official Colorado year-to-date acreage could be verified; the next verified number replaces it (SOURCES.md). |
| Cold open 3 | "...more than a million cubic yards of mud, after two fires, inside the reservoir that feeds Denver's taps." | "And after two fires, more than a million cubic yards of mud ended up in it." | Same fact (Denver Water); "it" is the reservoir the new second line names. |
| Intro, P3 | "Dark mode, because fire is already bright enough." | "Calm colors, because fire is bright enough." | The app has no dark mode; its palette is calm. |
| Demo, icon array | "In 100 weeks like this one, [N] got worse within a month." | "...about 66 were in severe drought a month later." | The captured icon array is the "drought reaching D2 or worse" row (66), not a worsening row (18). The figure is the app's own (`demo_freq_n`). |
| Demo, weeks like this one | "the actual past years that started exactly like today" | "the real past weeks that looked like today" | The cases are training weeks in the same drought category and season, not exact matches. |
| Demo, record | "Every forecast is time-stamped before we know the outcome" | (beat cut for time; the corrected wording was "Every new forecast") | 40 earlier issues were published late, and marked so. |
| Slide 1 | "We used AI coding tools for parts of the build, and we documented exactly where in our repo." | "We used AI coding tools, and our repo documents exactly where." | `AI_USAGE.md` attributes most modules to the AI agent; "parts" would understate it. The film does not call the app AI-made. |
| Slide 2 | Sources: SNOTEL, EnviroScreen, Denver Water | (slide cut for time) | SNOTEL is not in the weekly pipeline (a v1.2 arm that did not ship), and Denver Water is cited, not a data feed. |
| Slide 3 | "We tried four neural-network models." Cards: gradient boosting, LSTM, ConvLSTM, two-stage climate model. | "We tried three machine-learning models, one of them a neural network." Cards: Gradient boosting (LightGBM), Neural network (ConvLSTM), Ensemble of both. | The trained arms tried are LightGBM, a physics-informed ConvLSTM and their ensemble (README, Science notes); one is a neural network; there is no separate LSTM. |
| Slide 3 caption | "Calibrated. Explainable. Hard to beat." | "Explainable. Hard to beat." | 15 of 54 probability tests failed reliability, so "calibrated" is not true of every forecast. |
| Slide 4 | "We locked away all of 2026 before testing, and scored it once." | "We locked away 2026 before testing, and counted every look." | The sealed year has been looked at three times, each counted (`facts.json` hindcast_looks). |
| Close, P1 | "COFIRE. Free, open source, updated every week." | "COFIRE. Free, and updated every week." | The repository is private, so "open source" is not yet true. Restore it if the repository is made public before submission. |
| End card | URL | no URL | The deployed site has never deployed successfully and the repository is private, so no URL opens (the brief: never show one that does not). |
| Timer | "Timer stops at about 0:03." | The timer counts real film time from 3:00 at the first intro card and stops at the end card, near 0:22. | A real-time count from 0:16 cannot reach 0:03 by 2:53; faking it would contradict "counting real elapsed time". P4's "[Thirty] seconds" reads the timer's real value at that moment. |

## Cut to fit under 2:58

The script as written runs 3:36 at a normal reading pace. The cuts below
follow the brief's order (slide and demo seconds before required items), and
leave about four seconds of room for slower real reads.
- **Slide 2 (the data), its line and slide.** Trimmed first, as SLIDES_V2.md
  says to.
- **Slide 3 narration shortened.** The slide's own card shows the method.
- **"Here's what's under the hood."** Cut from Slide 1.
- **The forecast-record beat** (demo seconds).
- **Shorter visual windows:** the stakes map, the start of the pick
  sequence, the icon-array window.
- **Intro gags and the "next" line trimmed** to fit trailer-length cards.

## Added

- **The purpose sentence is spoken (P2) as well as shown.** The script showed
  it but gave no one the line, and the rules require both.
