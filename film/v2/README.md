# Film v2: how to finish it

The cut follows `film/SCRIPT_V2 (1).md` and `film/SLIDES_V2 (2).md`, with the
corrections in `CHANGES.md`. It is built from `script/v2/lines.json` (the
words) and `script/v2/beats.json` (the picture). `scripts/v2/build.mjs` voices each line,
lays the lines onto the beats, and writes the timeline, the audio, captions,
line sheets (`../LINES/`) and `../RULES_CHECK.md`. The picture is
`src/v2/FilmV2.tsx`; the tap trace that opens and closes the film is
`src/v2/Trace.tsx` (the app's map, one camera move each way); the demo shots
are short windows of the v1 film, time-remapped to the lines, so they reuse
its captures, camera moves and cursor. The build also synthesises the sound
(tap, rising tone, low hits, music pad) and checks pacing: no dead air over
half a second outside the open, the turn and the end card, and no held shot
over 4 s outside the traces and the turn. Review stills:
`node scripts/v2/stills.mjs <dir> FilmV2 <seconds>...`.

## 1. Names and roles

`film/team/team.json` has the four names and the script's titles (Lead
Developer, Data and Research Lead, Product Designer, Outreach and
Accessibility Lead). Change a title to what that person actually did, then
`node scripts/prepare.mjs`.

## 2. Voices

Each person records the lines in their sheet (`film/LINES/P1.md` to `P4.md`)
and saves the best take as `film/audio/vo/<file name>.wav` (or `.m4a`), for
example `film/audio/vo/tap1.wav`. Lines marked ALL: one file of everyone
saying it together, named as in the sheet. Any line without a file keeps its
scratch voice, and the film keeps its "scratch" label.

## 3. Final render (about 15 to 25 minutes on this laptop)

```
cd film
node scripts/prepare.mjs                 # names, numbers
node scripts/v2/build.mjs --final        # re-times to the real reads; fails on any missing requirement
node scripts/render.mjs v2master         # 1920x1080, 60 fps
node scripts/render.mjs v2exports        # 30 fps upload, and one with English captions burned in
node scripts/render.mjs v2vertical       # the cold open and intros, 1080x1920
```

Outputs are in `film/out/v2/`: master, upload, captioned upload, vertical,
`captions_en.srt` and `captions_es.srt`. The Spanish captions are a draft,
for a fluent reader to check before publishing.

**If the reads run long:** the build re-times every section to the real
lines. If the total passes 2:58, it fails and says so. Cut slide or demo
seconds first, in `beats.json` (`min`) or by shortening a line in
`lines.json`, never a required item.

**What the build checks** (`RULES_CHECK.md`): every participant named, spoken
and on screen; the app name; the purpose sentence, spoken and shown
verbatim; the audience; the tools and languages, spoken and on screen, with
the open-source and AI-use line; real app captures; the length between 1:00
and 2:58.
