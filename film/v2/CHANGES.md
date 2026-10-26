# Film v2: changes made to the second script and slides, and why

Built from `film/SCRIPT_V2 (1).md` and `film/SLIDES_V2 (2).md`. They were
followed as written, except where a line said something the repository or a
primary source does not support, or the cut could not fit under 2:58. Each
change uses the fewest words that make the line true. `script/v2/lines.json`
holds the lines as recorded; `script/v2/beats.json` the picture.

## Changed because they were not true

| Where | Script said | Film says | Why |
|---|---|---|---|
| Numbers 1 | "[Ninety-four] percent of Colorado in drought." | "Sixty-one percent of Colorado is in drought." | The latest U.S. Drought Monitor map (Oct. 20, 2026) is 61.05% D1 to D4. 94% could not be verified for any recent week. |
| Numbers 2 | "[Two hundred thirty-five thousand] acres burned." | "About eighty percent of Denver's drinking water passes through one reservoir." | No official Colorado year-to-date acreage could be verified tonight, so the brief's rule applies: cut it and use the next verified number (Denver Water, Strontia Springs). |
| Numbers 3 | "...ended up in the reservoir that feeds those taps." | "...ended up in it." | Same fact (Denver Water, 2017); "it" is the reservoir the line before names. |
| Team, P1 timer line | "And we have about two and a half minutes." | "And we have just under two and a half minutes." | The timer reads about 2:16 at that moment. "About two and a half" would round up; the phrase is computed from the timer (`timer_minutes`). |
| Demo, icon array | "In 100 weeks like this one, [N] reached severe drought within a month." | "...about 66 were in severe drought four weeks later." | The app's number is the chance of D2 or worse at the four-week horizon (`d_ge2_h4`), not at any time within it. 66 is what the captured card shows (the app's rounding of 65.5%). |
| Demo, record | "Every forecast is time-stamped before the outcome exists" | "Every new forecast is time-stamped before its outcome is known" | 40 earlier issues were published late, and the record marks them so. |
| Slide 1 narration | "We used AI coding tools for parts of the build" | "We used AI coding tools, and our repo documents exactly where." | `AI_USAGE.md` attributes most modules to an AI coding agent; "parts" would understate it. The film does not call the app AI-made. |
| Slide 1 footer | "AI-assisted parts disclosed in AI_USAGE.md" | "AI-assisted development is disclosed in AI_USAGE.md." | As above. |
| Slide 2 sources | U.S. Drought Monitor, gridMET, SNOTEL, Colorado EnviroScreen, Denver Water | U.S. Drought Monitor, gridMET fire danger, Colorado EnviroScreen, USGS watershed boundaries | SNOTEL was a research arm that was not adopted (`research/README.md`); Denver Water is cited, not a data feed. The watershed outlines are USGS WBD. |
| Slide 2 check gate | "allowlist, checksum, error-page rejection" | "Host allowlist · error pages rejected · every file logged with its checksum" | `safe_fetch.py` logs each file's sha256; it does not verify against a known checksum. |
| Slide 2 counter | "1,245 map cells at 4 km" | "1,245 map cells" | Cells are 1/24 degree, about 4.6 km north-south and 3.6 km east-west here; "4 km" is not exact. |
| Slide 3 | "We tried [four] machine-learning models." Cards: gradient boosting, LSTM, ConvLSTM, two-stage climate model. | "We tried three machine-learning models." Cards: Gradient boosting (LightGBM), Physics-informed neural network (ConvLSTM), Ensemble of the two. | The trained arms are LightGBM, a physics-informed ConvLSTM and their ensemble (README, Science notes). There is no separate LSTM. The two-stage climate model (`research/v12/stage2.py`, SNOTEL) was a research arm on top of the shipped model, not one of the machine-learning models, and was not adopted. |
| Slide 3 | "The simplest one won: look at every week like today since 2007" | "The simplest approach won: look at every week like today from 2007 to 2021" | What ships is a Markov transition model for drought (counts of what followed each category, fit on 2007 to 2021) and simple persistence models for fire danger (README, Science notes), so "approach", not one model; the cases are the training years (`facts.json` split). |
| Slide 3 | "It's calibrated, and you can explain it in one sentence." / caption "Calibrated. Explainable. Hard to beat." | "And you can explain it in one sentence." / "Explainable. Hard to beat." | 15 of 54 probability tests failed reliability, so "calibrated" is not true of every forecast. |
| Slide 4 | "Then we locked away all of 2026 and tested on it exactly once." Segment "Locked · scored once" | "Then we locked away 2026 before testing, and counted every look." Segment "Locked, every look counted" | The sealed year has been looked at three times, each counted (`facts.json` hindcast_looks). |
| End card | a URL | no URL | The deployed site has never deployed successfully and the repository is private, so no URL opens. The brief: never show a URL that does not open. |
| Timer | "appears reading about 2:38", "stops at about 0:02" | Shows 3:00 minus real film time: about 2:32 when it appears, 0:05 at the last frame. | The timer counts real time; it shows what is true at each frame. |

## Cut to fit under 2:58

The second script, corrected, runs 3:08 with the scratch voices. Cuts follow
the script's own order:

1. **The timer glance line** ("Twenty seconds. We're fine."). The first
   glance, at "This is COFIRE", stays.
2. **P2's second demo line** ("And you can see why..."), with its two
   "weeks like this one" shots.
3. **Slide 2 narration** shortened to "Nineteen years of drought and
   fire-danger data, and every download checked before we trust it." The
   counters (19 years, 5 areas, 1,245 cells) stay on the slide.

The open was tightened by about a second (no words cut). Result: 2:54.3.

## Interpretations of the quality brief

- **The backward trace.** One MapLibre camera move with no cut, from the demo's
  Denver garden cell, past Strontia Springs Reservoir, along the Roberts Tunnel
  to Dillon Reservoir, on the app's basemap and palette. The route is drawn
  schematically and the film says so. The watershed cells take the latest
  published Drought Monitor week (Oct. 20, 2026), spreading out from Dillon;
  before that they are tinted spruce, the app's accent, not a data colour. The
  numbers land on the same map while the camera keeps moving, so the open is
  one shot from the drop to the team intro.
- **The forward trace** in the close is the same motif reversed and is held
  as one shot (about 12 s), like the open. It is the only other shot over
  4 s besides the turn.
- **Music.** No music was downloaded. The bed is a soft four-chord pad
  synthesised with ffmpeg in `scripts/v2/build.mjs`. It enters on the hard cut
  to the team, ducks under the voice, is silent from the start of the turn
  until 0.7 s after its last word, and fades on the end card. The tap, the
  drip, the rising tone and the low hits are synthesised the same way; the
  hits are doubled with Kenney's CC0 drop sound pitched down.
- **No shot over 4 s.** Slides are cut into framings (wide, then close on what
  the voice names), each 4 s or shorter; the purpose sentence holds on screen
  for its line and the audience line (about 18 s, enough to read twice) while
  the app captures behind it cut every 3.6 s or less.
