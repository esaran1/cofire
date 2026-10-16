# COFIRE demo film

A 2:51 product film for COFIRE, built in code with
[Remotion](https://remotion.dev) and rendered entirely on this machine:
- no cloud rendering;
- no accounts;
- no AI voice or video;
- nothing uploaded.

- **Story and words:** `SCRIPT.md` (the narration is a draft for the
  student).
- **Shot list:** `STORYBOARD.md`, generated from `script/timeline.json`.
- **Sources:** `SOURCES.md`.
- **Licenses:** `LICENSES/`.
- **Review checklist and results:** `REVIEW.md`.
- **Recording the voice:** `RECORDING_GUIDE.md`.

## Run it

From the repository root, the production static build must exist first
(`BASE_PATH=/cofire ./scripts/build_static.sh`); it carries the basemap.
Then, in `film/`:

    npm ci --ignore-scripts      # pinned Remotion and friends (film/package-lock.json)
    npm run prepare:data         # public/data/film.json from facts.json and artifacts
    npm run capture              # every app capture, from the production build (one command)
    npm run check                # the film's checks (use check:draft before the open-data page exists)
    npm run audio                # narration (scratch or yours), sounds, ducked music, -14 LUFS, captions
    npm run render:animatic      # low-resolution animatic with the scratch voice
    npm run film                 # everything: prepare, check, audio, animatic, master, exports, vertical

Outputs land in `out/`, which is not committed:

| File | What |
|---|---|
| `cofire_master_1920x1080_60fps.mp4` | the master |
| `cofire_upload_1920x1080_30fps.mp4` | the upload export |
| `cofire_upload_1920x1080_30fps_captions_en.mp4` | upload with English captions burned in |
| `cofire_vertical_1080x1920_30fps_45s.mp4` | the first 45 seconds, vertical |
| `captions_en.srt`, `captions_es.srt` | captions (the Spanish is a draft for review) |
| `cofire_animatic_640x360_15fps_scratch.mp4` | the animatic |
| `cofire_prompter_1280x720.mp4` | a silent prompter for recording (`npm run render:prompter`) |
| `render_report.json` | render times, durations, sizes, checksums, loudness |

## How it is built

- **Numbers are traced.** Every number on screen comes from `field()`
  (`src/trace.ts`), which reads `public/data/film.json`. That file is built
  by `scripts/prepare.mjs` from `app/lib/facts.json` and the project's
  artifacts, and each entry names its source. After every frame,
  `src/Guard.tsx` reads all the text on screen and fails the render if any
  run of digits was not handed out by a field. The narration and captions
  use `{field}` references and refuse typed digits (`scripts/lib.mjs`).
- **The product is real.**
  - `capture/capture.mjs` drives the production static build with
    Playwright, served locally by `capture/serve.py` with range requests
    and gzip, as GitHub Pages serves it.
  - Every other request is aborted, and the clock is fixed.
  - Stills are 1920x1080 at twice the resolution. Phones are 390x844 at
    three times.
  - Motion clips are lossless PNG frames at 60 fps.
  - Pointer paths and clicks are recorded, and the synthetic cursor follows
    them.
- **The maps are real.** Parts 1 and 2 are MapLibre with the app's own
  style and self-hosted basemap, drawn frame by frame in software WebGL.
  The drought cells come from the bundles the app published.
- **The browser is local.** Remotion renders with the Chrome for Testing
  headless shell that Playwright had already installed (`scripts/browser.mjs`);
  nothing is downloaded.
- **Renders are split.** The master renders in five parts (`P1` to `P5`),
  each under 60 minutes, and the parts are joined without re-encoding. An
  idle watchdog cancels a stalled render.
- **Sound is mixed in ffmpeg.**
  - Narration: your `audio/voice.wav`, or a scratch track from macOS `say`.
  - Kenney CC0 UI sounds at the recorded clicks.
  - Music: your `audio/music.wav`, or a silent placeholder, with the ducking
    in `audio/ducking.json` applied.
  - Two-pass loudnorm to -14 LUFS, verified with ebur128.

## Changing it

- **Words:** edit `script/narration.json`, then run `npm run docs`.
- **Timing:** edit `script/timeline.json` (shots), and the narration start
  times in `script/narration.json`, then run `npm run docs` and `npm run check`.
- **Address on the end card:** set `site_url` in `config.json` (it is
  derived from the git remote until the repository moves).
- **Preview:** `npm run studio` opens Remotion Studio locally. The map
  scenes need `python3 capture/serve.py` running.
