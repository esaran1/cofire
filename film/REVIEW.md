# Film v2: self-review

The brief asked for three viewings of the full render at real speed. I can't
watch a video in real time, so each pass below was done on the rendered
master instead:

- **Picture:** stills at every beat (and at each slide framing and each cold
  open step), read as a viewer would see them.
- **Cuts and stillness:** ffmpeg scene detection (at a coarse and a fine
  threshold), black detection and freeze detection over the whole file.
- **Sound:** silence detection and EBU R128 loudness on the mix, and a check
  that the music track is silent during the turn.
- **Rules:** the build's own checklist (`RULES_CHECK.md`), which fails the
  build if any required item is missing.

The team should still watch it once at real speed before submitting, ideally
on a phone.

## Pass 1: as a congressional staffer (is it clear, credible, and about the district?)

| Found | Changed |
|---|---|
| The audience scene's backdrop was a phone capture blown up to full width: a huge, blurry Spanish banner fought the text. | Purpose and audience now cut between landscape app captures (map, watershed card, weeks-like-this, brief, Spanish card, record), under a darker scrim. |
| The turn's last line wrapped to leave "number." alone on a line. | Balanced wrapping. |
| The close map's labels "Dillon" and "Upper South Platte" overlapped; Larimer and Pueblo showed the spruce highlight instead of their real drought colours. | Upper South Platte is labelled under its area; every area now shows its real Oct. 20 categories. |
| The tunnel label sat on top of the Dillon Reservoir pin. | Moved along the tunnel and below the route line. |
| The drought legend read "Oct 20" with no year. | "U.S. Drought Monitor, week of Oct 20, 2026". |
| The third number's caption broke to leave "fires" alone. | Wider measure. |

## Pass 2: as a software engineer checking the technical claims

| Found | Changed |
|---|---|
| Slide 1's footer said "AI-assisted *parts* of the build", which understates `AI_USAGE.md` (most modules are attributed to an AI coding agent). Caught before the master render. | "AI-assisted development is disclosed in AI_USAGE.md." Narration: "We used AI coding tools, and our repo documents exactly where." |
| Slide 2 listed SNOTEL (a research arm that did not ship) and Denver Water (cited, not a data feed); "checksum" implied verification that `safe_fetch.py` does not do; "at 4 km" is not exact for 1/24-degree cells. | Sources: U.S. Drought Monitor, gridMET fire danger, Colorado EnviroScreen, USGS watershed boundaries. "Every file logged with its checksum". "1,245 map cells". |
| Slide 3: four model cards, "calibrated", "since 2007". | Three cards (LightGBM, physics-informed ConvLSTM, their ensemble); "approach", because what ships is a Markov transition model for drought plus persistence models for fire danger; "from 2007 to 2021"; no "calibrated". |
| Slide 4: "tested on it exactly once". | "counted every look" (three looks, each counted). |
| The demo line said "within a month"; the app's number is at the four-week horizon. | "four weeks later". |
| The end card credited Denver Water as data. | "Data: U.S. Drought Monitor, gridMET. Sources: Denver Water." |

Every number on screen is checked by the Guard on every frame (it fails the
render on any digit that did not come from `public/data/film.json`).

## Pass 3: only the required items

`RULES_CHECK.md`, final timestamps in the report. All pass: four participants
named (spoken and in lower thirds, and on the end card), the app's name, the
purpose spoken and on screen verbatim, the audience, tools and languages
spoken and on screen, AI use disclosed on screen, functionality in real app
captures, duration 2:54.3 (cap 2:58).

## Cuts, stillness and sound (from the measurements)

| Found | Changed |
|---|---|
| Slide framings ran 4.13 s, 4.17 s, 6.5 s and 4.57 s in four places (fine-threshold scene detection). | A punch-in added to each (MapLibre tile, the AI line, the method card, the locked 2026 segment). The re-render measured slide 3 at 4.40 s still; its framings are now evenly spaced, and that one slide was re-rendered and spliced in at its own beat cuts (`scripts/v2/segment.mjs`). Re-measured: the longest slide shot is 3.83 s. Outside the two traces and the turn, every shot is 4 s or shorter (the purpose and audience plates cut under a dark scrim, too faint for the detector; checked frame by frame). |
| The cold open's camera stopped 1.2 s before the cut to the team (a frozen frame). | The pull-back now runs to the cut. |
| The clock beat and the turn read as frozen frames (1 to 3.9 s). | A slow push on each: the stillness is held, not frozen. The turn is still one line on black. Re-measured: no frozen stretch of 1 s or more anywhere; the only black is the 0.7 s before the turn's first line. |
| Caption cues overlapped the next cue in 2 places (EN) and 3 (ES); English peaked at 22.4 characters a second. | Cues end before the next begins and may use the pause after their line. English now peaks at 19.5 cps. Spanish peaks at 22.6 cps on the purpose sentence, which runs straight into the audience line; flagged for the Spanish reviewer. |
| Two hung ffmpeg processes from an earlier build, and a duplicate render, were taking CPU. | Killed; `ff()` now times out after 5 minutes instead of hanging. |

Sound, measured on the mix: -14.0 LUFS integrated, -1.4 dBFS true peak,
5.6 LU loudness range. Silences over half a second: only in the scored open
(the hard cut on "This year, here looked like this", before the first hit, and
the breath before the hard cut to the team), inside the turn (including the
0.7 s held after its last word before the music returns), and the final fade.
The music track measures silent for the whole turn.

## Final outputs, measured

| File | Length | Picture | Loudness | Stillness and black |
|---|---|---|---|---|
| `cofire_v2_master_1920x1080_60fps.mp4` | 2:54.3 | 1920x1080, 60 fps | -14.0 LUFS, -1.4 dBFS peak | No freeze of 1 s or more at 480 px; black only before the turn's first line (0.7 s) and between its two lines (0.2 s). |
| `cofire_v2_upload_1920x1080_30fps.mp4` | 2:54.3 | 1920x1080, 30 fps | -14.0 LUFS, -1.4 dBFS | As the master. |
| `cofire_v2_upload_1920x1080_30fps_captions_en.mp4` | 2:54.3 | 1920x1080, 30 fps, English burned in | -14.0 LUFS, -1.4 dBFS | As the master. |
| `cofire_v2_vertical_1080x1920_30fps.mp4` | 0:45.0 | 1080x1920, 30 fps | -13.9 LUFS, -1.4 dBFS | The cold open and the team. |

A coarser scan (320 px, 15 fps) flags 1.0 to 1.6 s "freezes" at the turn's
slow push, the last second of the open's pull-back, and the vertical's first
1.6 s (the drop forming on black). Each is a deliberate slow move, under a
pixel a frame at that size; the full-size scan finds none.

## Left as they are, and why

- **The open (27.5 s) and the close (12.5 s) are single shots.** The open is
  the backward trace the brief exempts; the close is the same move forward.
- **The turn is 12.6 s on black.** Exempt by the brief.
- **The demo's first beat plays its three v1 shots at 1.35x speed** to fit the
  line; the cursor and camera moves still read.
- **66 in the demo** is the app's own figure as the captured card shows it
  (65.5%, rounded by the app).

---

# Film v1 review (2026-10-16, kept as it was)

(Original title: "COFIRE demo film: review".)

The checklist from the brief, completed on 2026-10-16 against the first cut
rendered that day, and gone through again the same day against the second
cut (see "Second pass").
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

## Second pass: the second half rebuilt (2026-10-16)

The first cut's opening held up, but from the trust section on, several shots
were plain cards or app pages shown too small to read. Each was rebuilt and
then checked again, frame by frame:

- **"Why trust it?"** now sits over a slow field of faint points, not a
  flat dark frame.
- **Held out, frozen, counted.** One diagram replaces the separate freeze
  card and look counter.
  - A bar of the years shows training, validation and calibration, then
    2026, which glows and locks.
  - The two seal cards (the commit, and the test's fingerprint) settle
    under it.
  - The camera pushes in on 2026 while its three looks are marked, and ends
    on the date it is scored in full.
- **The leak** is now a diagram of the mistake itself.
  - A red arc reaches from today to the week being forecast and pulls that
    week's outcome back.
  - When the narration turns to "in real time", the arc is struck out.
    Arcs from past weeks bring in only outcomes already known.
- **Weekly refresh:** the fire-spread layer, which changes visibly from
  week to week, crossfades between issues.
- **Forecast record, seal notice, open data:** each page is framed on its
  content column, close enough to read the dates, fingerprints and the
  notice.
  - The record shot opens on the table and the seal shot opens on the
    notice, so the two no longer begin on the same view.
- **Ending:** the film closes as it opened, on the live map. It pulls back
  from the three areas to all five, then fades into the end card.
- **Map edges:** where the bundled tiles stop, the map now fades into the
  background rather than ending at a hard edge, in the opening and the
  finale.
- **Pick and fly-in:**
  - The laptop stays centered.
  - The screen eases from the full app to the place menu, so the change
    from Upper South Platte to Denver can be read.
  - The fly-in starts from that same view.
- **Brief:** the printed sheet is larger and slides up into frame.

## Outputs and render times (second cut, 2026-10-16)

| File | Length | Size |
|---|---|---|
| `out/cofire_master_1920x1080_60fps.mp4` | 2:49.6 | about 200 MB |
| `out/cofire_upload_1920x1080_30fps.mp4` | 2:49.6 | about 104 MB |
| `out/cofire_upload_1920x1080_30fps_captions_en.mp4` | 2:49.6 | about 95 MB |
| `out/cofire_vertical_1080x1920_30fps_45s.mp4` | 0:45.0 | about 52 MB |
| `out/captions_en.srt`, `out/captions_es.srt` | 35 and 42 cues | |
| `out/cofire_animatic_640x360_15fps_scratch.mp4` | 2:49.6 | about 10 MB |

**Render times** on one MacBook, CPU only, five tabs, software WebGL
(`out/render_report.json` has each run):

| Render | Time |
|---|---|
| P1 (cold open) | 1.3 min |
| P2 (map act) | 3.7 min |
| P3 (product) | 6.5 min |
| P4 (trust) | 3.8 min |
| P5 (close) | 2.0 min |
| **Master total** | **about 17 min** |
| Exports (30 fps, captions) | 1.3 min |
| Vertical | 3.8 min |
| Animatic | 2.4 min |
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
