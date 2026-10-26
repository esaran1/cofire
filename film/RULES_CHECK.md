# Film v2: CAC demonstration-video requirements

Written by `scripts/v2/build.mjs` (draft build), from the timeline it lays out. The build fails if any row fails, except names still being placeholders in a draft.

| Requirement | Pass | Where (film time) | Note |
|---|---|---|---|
| Name of every participant (four), spoken | **FAIL** | 0:16.3, 0:22.3, 0:28.9, 0:35.8, 2:49.1 | names are placeholders until film/team/team.json is filled in |
| Name of every participant (four), on screen | **FAIL** | 0:16.0, 0:22.0, 0:28.6, 0:35.5, 2:46.0 |  |
| Name of the app, spoken | PASS | 0:42.9, 2:46.2 |  |
| Name of the app, on screen | PASS | 0:42.7, 2:46.0 |  |
| Purpose in one sentence, spoken | PASS | 0:55.9 |  |
| Purpose in one sentence, on screen verbatim | PASS | 0:54.3 | the Purpose scene sets the same text the line speaks (both from script/v2/lines.json) |
| Target audience, spoken | PASS | 1:04.0 |  |
| Tools and coding languages, spoken | PASS | 1:58.3 |  |
| Tools and coding languages, on screen | PASS | 1:58.0 |  |
| Open-source libraries and AI-assisted development disclosed on screen | PASS | 1:58.0 |  |
| Functionality shown with real app captures | PASS | 1:14.2 to 1:58.0 |  |
| Duration between 1:00 and 2:58 | PASS | 2:53.8 |  |

Duration: 2:53.8 (173.8 s). Voices: 0 recorded, 27 scratch (macOS say).

## Timing warnings

- demo_ws: the line runs 1.06 s past the v1 window; it holds its last frame for that long
- demo_brief: the line runs 0.42 s past the v1 window; it holds its last frame for that long
- close_map: the line runs 1.17 s past the v1 window; it holds its last frame for that long
