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

## Film v2 (2026-10-25): outside numbers

Each was checked at its source on 2026-10-25. On screen it is shown rounded
down (never up), with a source line under it. App numbers in v2 come from
`facts.json` and the bundles through `public/data/film.json`, as in v1.

| Shown | Film says | Source, quoted | URL | Retrieved |
|---|---|---|---|---|
| Cold open, first number | **61%** of Colorado in drought | U.S. Drought Monitor state statistics, Colorado, map of 2026-10-20 (valid Oct 20 to 26): D1 to D4 = 61.05% (D0 to D4 = 83.50%) | https://usdmdataservices.unl.edu/api/StateStatistics/GetDroughtSeverityStatisticsByAreaPercent?aoi=08&startdate=10/15/2026&enddate=10/25/2026&statisticsType=1 | 2026-10-25 |
| Cold open, second number | About **80%** of Denver's drinking water passes through one reservoir | Denver Water, "Strontia Springs: the little reservoir that could" (TAP Staff, 2017-09-09): "about 80 percent of Denver's drinking water passes through Strontia Springs Reservoir." | https://www.denverwater.org/tap/strontia-springs-the-little-reservoir-that-could | 2026-10-25 |
| Cold open, third number | More than **1,000,000** cubic yards of mud in it, after two fires | Denver Water, "The legacy of Colorado's largest wildfire" (Sabrina Hall, 2017-06-16): the Buffalo Creek (1996) and Hayman (2002) fires, followed by rainstorms, "resulted in more than 1 million cubic yards of sediment accumulating in Strontia Springs Reservoir." | https://www.denverwater.org/tap/legacy-colorados-largest-wildfire | 2026-10-25 |
| Cold open, P2 over the trace (source line on screen) | "About half of that water starts here, on the other side of the mountains" | Denver Water, "Where does your water come from?" (2021-06-29): "Denver Water collects around 50% of its drinking water from tributaries of the Colorado River on the west side of the Continental Divide." | https://www.denverwater.org/tap/where-does-your-water-come | 2026-10-25 |

The watershed colours in the trace are the app's own published week
(U.S. Drought Monitor for Oct. 20, 2026, through `public/data/film.json`), and
the route (garden cell, Strontia Springs, the tunnel's east end, Dillon) is
drawn schematically, as the film says on screen.

**Cut, could not be verified:**
- **"94% of Colorado in drought".** The latest map is 61.05% (D1 to D4).
  Colorado was last at 94% or more in June 2026 (96.56% on Jun 23). The
  D0-to-D4 share peaked at 93.81% in September, which cannot be rounded up to
  94.
- **"235,000 acres burned this year".** No Colorado year-to-date figure was
  found from NIFC, the Rocky Mountain Coordination Center or the state's
  Division of Fire Prevention and Control. The 235,000 traces to an unsourced
  Wikipedia infobox. NIFC's daily situation report gives only a five-state
  Rocky Mountain Area total, which is not Colorado.
- **Replacement.** The next verified number, the Strontia Springs share,
  took its place.
