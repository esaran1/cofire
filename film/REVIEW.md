# COFIRE demo film: review

The checklist from the brief, completed on 2026-10-16 against the first cut
rendered that day.
- **Evidence:** measured from the rendered files by `scripts/review.mjs`
  (`out/review.json`, with contact sheets in `out/review/`). Each result says
  how it was checked.
- **Do it again after recording:** go through this whole list once more with
  the student's voice and chosen music in (see the last section).

| Check | Result | How it was checked |
|---|---|---|
| The first 3 seconds would make a stranger keep watching | **Pass, with a note** | Frame 0 is already the drought map moving week by week: every cell colored, a live count of squares in severe drought or worse (302 rising), and "2026, week by week." rising in at 0.6 s. There is no logo, and no title card before the data. It works on the motion, so judge it at full speed; a still of frame 0 is sparse. |
| No shot over 6 s except the magic moment | **Pass** | `check.mjs` and `review.mjs` over `script/timeline.json`: 40 shots; the longest is the magic moment (`product.tap`, 6.7 s); none other is over 6 s. |
| No spinner, console, error, placeholder or debug UI in any frame | **Pass, with one deliberate label** | Every capture fails if the page shows "Loading", "Error", "NaN" or "undefined", or logs a console error (`capture/capture.mjs`). The film fails to render if the open-data page was not captured. ffmpeg found no black frames and no frozen stretches in the upload or the vertical cut. The one deliberate label: "Scratch voice (macOS say): draft" sits in the top-right corner until `audio/voice.wav` exists. |
| On-screen text readable on a phone at 30 fps | **Pass** | The render guard fails on any text under 18 px (`src/Guard.tsx`); only the map credit and the scratch label are that small. Source lines are 25 px; labels and figures are 26 to 300 px. App text is shown zoomed: the frequency sentence fills about half the frame width. The vertical cut was checked on its contact sheet. |
| Every number traced | **Pass** | The render guard reads all on-screen text after every frame and fails on any run of digits not handed out by a field of `public/data/film.json`, each of which names its source file and key. It caught "sha256" typed into a label before the first cut. Captions use the same rule (`scripts/lib.mjs` `fill`). The fields behind every number are in `STORYBOARD.md`. |
| Every source listed | **Pass** | `SOURCES.md`; `check.mjs` fails if an outside source the film shows is not listed there. There are two outside facts, both Denver Water pages, both shown with a source line, and both quoted word for word as of 2026-10-15. |
| Every asset licensed and recorded | **Pass** | Fonts: the app's OFL files. Sounds: 11 Kenney files, CC0 (`LICENSES/`), downloads recorded in `data/ledger.json`. Remotion: free individual license (`LICENSES/REMOTION.md`). There is no music and no outside footage. The laptop and phone are drawn in code. `check.mjs` refuses any sound file that is not a recorded Kenney file, and refuses a committed voice or music file. |
| Duration in bounds | **Pass** | Master, upload and captioned upload: 2:49.6 (target 2:30 to 2:55; render fails over 3:00). Vertical: 0:45.0. |
| Watched end to end at real speed; every stutter, rough cut or dead air fixed | **Partly: the student must finish this** | The agent cannot watch video in real time. It did review the animatic and the cut frame by frame (contact sheets every 2 s, full-resolution stills of every shot) and measured the sound (narration gaps, loudness) and the picture (black and frozen frames). It fixed what that found (list below). Pauses between lines (3 to 4 s) are meant to be filled by music; until `audio/music.wav` is added they are silence. Watch the final version at full speed, on a phone and on a laptop, before publishing. |

## Fixed during review

- **Pacing:** the brief and phone beat left 6.3 s without narration. The
  phone shot was cut to 2.5 s, and everything after it moved 1.4 s earlier.
- **Timing:** line 23 ("January 12, 2027") ran past its slot, because spoken
  dates are long. Its slot was lengthened.
- **Readability:**
  - The Denver Water quote was hard to read over bright cells; it now sits
    on a dark scrim.
  - The "It looked perfect." title overlapped the chart heading; the heading
    now fades out first.
  - Secondary labels were raised to 25 to 30 px.
- **Framing:** area labels were clipped at the frame edge (in the vertical
  cut, "…uth Platte"). They now stay inside the frame.
- **Captions:**
  - The box was only 40% opaque, so captions were hard to read over the
    app's light screens; it is now about 85% opaque.
  - Spanish captions ran at up to 24.6 characters a second because they
    followed the English voice's timing. They now use each line's whole
    slot. Both languages are at most 19 characters a second, with no caption
    shorter than about a second.
- **Dead picture:** the leak diagram held still for two stretches of about
  3 s (the freeze detector caught them). It now has a slow push-in.
- **Number tracing:** "sha256" typed into a label failed the number trace;
  that card now says "fingerprint".

## Outputs and render times (2026-10-16)

| File | Length | Size |
|---|---|---|
| `out/cofire_master_1920x1080_60fps.mp4` | 2:49.6 | about 198 MB |
| `out/cofire_upload_1920x1080_30fps.mp4` | 2:49.6 | about 102 MB |
| `out/cofire_upload_1920x1080_30fps_captions_en.mp4` | 2:49.6 | about 93 MB |
| `out/cofire_vertical_1080x1920_30fps_45s.mp4` | 0:45.0 | about 52 MB |
| `out/captions_en.srt`, `out/captions_es.srt` | 35 and 42 cues | |
| `out/cofire_animatic_640x360_15fps_scratch.mp4` | 2:49.6 | about 10 MB |

**Render times** on one MacBook, CPU only, five tabs, software WebGL
(`out/render_report.json` has each run):

| Render | Time |
|---|---|
| P1 (cold open) | 1.3 min |
| P2 (map act) | 4.6 min |
| P3 (product) | 6.2 min |
| P4 (trust) | 3.3 to 3.6 min |
| P5 (close) | 1.5 min |
| **Master total** | **about 17 min** |
| Exports (30 fps, captions) | 1.3 min |
| Vertical | 3.6 min |
| Animatic | 2.7 min |
| Captures (one command) | 3.8 min |

No render came close to the 60-minute cap.

**Loudness** (EBU R128, measured on the files):
- master: -14.0 LUFS integrated, -1.2 dBTP true peak;
- vertical: -13.9 LUFS, -1.2 dBTP.

## After the student records

1. Put the voice in `audio/voice.wav` and the music in `audio/music.wav`
   (`RECORDING_GUIDE.md`). Write the music's title, artist and license here:
   - Music: _not yet chosen_
2. `npm run film`, then `node scripts/review.mjs`.
3. Go through this checklist again. Watch the whole film at full speed on a
   phone and a laptop, and fix anything that stutters, cuts roughly or goes
   quiet too long.
4. The Spanish captions are a draft; have a fluent reader check
   `out/captions_es.srt`, as for the app's Spanish.
5. Set `site_url` in `config.json` once the repository has moved, so the end
   card shows the right address.
