# Recording the narration

For the student. Everything here is free and stays on your own computer.

## 1. Make the words yours

- `SCRIPT.md` has the draft. Rewrite every line in your own words.
- Keep the facts. Change everything else.
- Put your final words in `script/narration.json`: one entry per line, at
  the same start times.
- Never type a number. Write `{n_survivors}`, `{holdout}` and so on; the
  table in `SCRIPT.md` lists every field. The captions and checks fill them
  in from the data.
- Run `npm run docs` to refresh `SCRIPT.md` and `STORYBOARD.md`.
- Run `npm run check` to confirm nothing typed a digit and the script is
  about 330 words or fewer.

If you change a line's length a lot, it may not fit before the next line
starts. `npm run audio` reports any scratch line that runs over; give that
line more room by moving the next start time in `script/narration.json`.

## 2. The room and the mic

- **Room:** small and soft beats big and bare. A closet full of clothes or a
  bedroom with the curtains closed works well. Turn off fans, the fridge
  (if you can hear it), and notifications.
- **Mic:** a phone's voice memo app is fine. A USB mic is better if you have
  one.
- **Distance:** about a hand's width (15 to 20 cm) from your mouth, slightly
  off to the side, so breaths don't pop.
- **Level:** do a test line at your normal speaking volume. The loudest
  words should reach about three quarters of the meter, and nothing should
  hit the top (clipping can't be fixed later).
- **Format:** WAV if your recorder offers it, otherwise the phone's default
  (m4a). 48 kHz is ideal; 44.1 kHz is fine.
- **Water:** keep a glass nearby, and pause and drink between parts.

## 3. Record in time with the film

Render the prompter once:

    npm run render:prompter

This makes `out/cofire_prompter_1280x720.mp4`. It is silent. It shows:
- the current line large;
- a count-in before each line;
- a bar showing how much time the line has;
- the next line;
- the film playing small in the corner.

Play it on a screen in front of you. Start your recorder, then start the
video, and read each line when its count-in ends. One continuous take is
easiest to line up. If you stumble, keep going: either redo that line at
the end and edit it in, or do another full take.

Read like you're explaining it to a friend, not like an ad. Leave a real
pause after "It looked perfect." That silence is the turn.

## 4. Drop the files in

- **Your voice:** save it as `film/audio/voice.wav`, one file whose 0:00 is
  the film's 0:00. If your take starts early, trim the front so your first
  word lands at the first line's time (0:03).
  - To convert a phone recording:
    `ffmpeg -i recording.m4a -ar 48000 -ac 1 film/audio/voice.wav`
  - To trim, say, 1.2 s from the start:
    `ffmpeg -ss 1.2 -i recording.m4a -ar 48000 -ac 1 film/audio/voice.wav`
- **Music:** pick a track from the YouTube Audio Library.
  - Note its title, artist and license, and copy them into `REVIEW.md`.
  - Save it as `film/audio/music.wav`.
  - It does not have to be the film's exact length. It is trimmed, faded,
    and ducked under your voice automatically (`audio/ducking.json`).

Neither file is committed to the repository (both are in `.gitignore`).

## 5. Render

One command does everything, from data to finished files:

    npm run film

It:
- prepares the data;
- checks everything;
- mixes your voice and music to -14 LUFS;
- writes the captions;
- renders the master in parts, then the 30 fps upload, the captioned upload
  and the vertical cut.

Expect roughly an hour on a laptop; `out/render_report.json` records the
time for each part. With `voice.wav` present, the "scratch voice" label
disappears from the picture.

## 6. If the captions drift from your voice

The captions follow each line's start time. If your reading runs early or
late in places, you can retime them from your own recording, still locally:

- Build `whisper.cpp` from its official GitHub source.
- Download a model from the official ggml repository and check its sha256
  before use.
- Run it on `audio/voice.wav` to get word timings, and move each line's
  `start` in `script/narration.json` to match.

Nothing is uploaded at any point. This step is optional. If you do it,
record the tool and model, with their sizes and checksums, in the ledger.

## 7. Then watch it

Go through `REVIEW.md` again with your voice and music in. Watch the whole
thing at full speed, on a phone and on a laptop, before you post it.
