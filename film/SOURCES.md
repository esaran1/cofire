# COFIRE demo film: sources

Every fact in the film is one of two kinds.

- **The project's own numbers**:
  - drought counts, survivors, coverage, dates, hashes and so on;
  - each comes from `app/lib/facts.json` or a project artifact, through
    `public/data/film.json`, which `scripts/prepare.mjs` builds;
  - each field in that file names the file and key it came from;
  - the render fails on any number on screen that does not come from a field
    (`src/trace.ts`), and the captions fail the same way (`scripts/lib.mjs`
    `fill`);
  - the storyboard lists the field behind every number.
- **Outside facts**: there are two. Each is shown with a source line on
  screen, and both come from Denver Water pages the app already cites
  (`app/lib/links.ts`, checked by the app's link test).

## Outside facts

| Shown when | What the film says | Source (as quoted on 2026-10-15) | URL |
|---|---|---|---|
| 0:15 to 0:27 (narration 3 and 4, source line) | About half of Denver's water comes from mountain rivers west of the Continental Divide; a tunnel carries it under the Divide from Dillon Reservoir. | Denver Water, "Where does your water come from?": "Denver Water collects around 50% of its drinking water from tributaries of the Colorado River … on the west side of the Continental Divide"; "The Roberts Tunnel brings water from Dillon under the Continental Divide to the Front Range." | https://www.denverwater.org/tap/where-does-your-water-come |
| 0:27 to 0:33 (narration 5, quote card, source line) | Denver Water calls wildfire the greatest threat to that supply. Quote card: "Moderate and severe wildfires are the greatest threat to Denver's raw water supply." | Denver Water, "Watershed Protection": "Moderate and severe wildfires are the greatest threat to Denver's raw water supply." | https://www.denverwater.org/your-water/water-supply-and-planning/watershed-protection-and-management |

The tunnel is drawn from Dillon Reservoir's label point in the basemap
(OpenStreetMap) to the nearest Upper South Platte cell. The film says the
route is drawn schematically, because the tunnel's exact path is not in the
project's sources.

## Data shown, and its credit

| What | Where it comes from | Credit on screen |
|---|---|---|
| Drought category of every cell, every 2026 issue (cold open, map act) | The bundles the app published (`app/out/data/domains/*/<issue>.json`), which carry U.S. Drought Monitor categories. These are observed inputs, not outcomes scored against a forecast. | "Drought: U.S. Drought Monitor, as COFIRE published it each week"; end card |
| Denver's two source watersheds | `artifacts/domains/footprints.json` (USGS Watershed Boundary Dataset HUC8 10190002 and 14010002) | Labels |
| Dillon and Strontia Springs reservoir positions | The app's basemap archive (`app/public/tiles/colorado.pmtiles`), from OpenStreetMap via Protomaps | "© OpenStreetMap contributors · © Protomaps" on every map frame; end card |
| Basemap | The same archive, the app's own style (`app/lib/basemap.ts`) | Same |
| 115 comparisons, 22 survivors | `artifacts/v11/survivors_v11.csv`, checked against `facts.json` `multiplicity` | none needed (project result) |
| The frozen model, the test fingerprint, the counted looks | `facts.json` `freeze_commit`, `preregistration_sha256`, `hindcast_looks` | none needed |
| Unseal date | `app/lib/seal.json` (the owner's decision, `docs/DECISIONS.md`) | none needed |
| Ranges as tested, and in real time | `facts.json` `look3.pid`, `interval_audit.as_tested`, `interval_audit.real_time`, `interval_audit.real_time_roll13_min` | none needed |
| Fuel dryness in the app captures | gridMET, as the app shows it | End card: "Fuel dryness: gridMET" |
| App screens | The production static build, captured locally (`capture/capture.mjs`) | n/a |

## Assets

| Asset | Source | License | Where |
|---|---|---|---|
| Fonts: Newsreader, Outfit, IBM Plex Mono | The app's own files (`app/fonts/`) | SIL OFL 1.1 (`app/fonts/OFL.txt`) | copied to `public/fonts/` at prepare time |
| UI sounds (11 files) | Kenney, "Interface Sounds" and "UI Audio", https://kenney.nl/assets/interface-sounds and https://kenney.nl/assets/ui-audio | CC0 1.0 (`LICENSES/CC0-1.0.txt`, `LICENSES/KENNEY_*_License.txt`) | `audio/sfx/` |
| Music | None. A silent placeholder; the student adds a track from the YouTube Audio Library as `audio/music.wav`, which is never committed. | the track's own terms; record them in REVIEW.md | n/a |
| Narration | Scratch: macOS `say` (built in), marked on screen as scratch. Final: the student's own recording, `audio/voice.wav`, never committed. | n/a | n/a |
| Laptop and phone | Drawn in code (`src/components/Devices.tsx`), generic shapes, no brand marks | project code | n/a |
| Remotion | npm, pinned 4.0.531 | Remotion free license for individuals (`LICENSES/REMOTION.md`) | n/a |
