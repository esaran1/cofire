# AI usage

This file says who did what in this repository. The first two sections were
written by the AI agent from what the repository itself records. The third is
for the student, in their own words, and is deliberately left blank.

## Who directed the research

The repository owner directed the project. They set its goals and scope (the
district, the areas, the questions to answer), and gave the agent written
instructions for each stage. Those instructions fixed what to build, the rules
the work had to follow, and when to stop and report. The rules included
sealing the 2026 holdout, freezing the model code, a download budget,
leak-free evaluation, pre-stated tests and agreement rules, and disclosing
errors. The agent carried the instructions out and reported results, faults
and blockers back. Decisions left open by the instructions were made by the
agent and recorded, with reasons, in `docs/DECISIONS.md`. Decisions that
needed the owner were brought to the owner, and the work stopped until they
answered. Examples: whether to refit after the missing 2022-12-27 drought map
was found, whether to adopt gridMET's revised 2026 data, and repository
visibility.

The student's own account of which ideas, questions and judgements were
theirs belongs in the section below. This section does not claim to know it.

## What the AI agent generated

**Effectively all of the files in this repository were written by an AI
coding agent** (Anthropic's Claude, through Claude Code). That covers the data
pipeline, the models and their evaluation, the statistical tests, the shipping
layer, the API, the web app, the tests, the lint scripts, the workflows, the
figures and screenshots, and the documentation, including the decision logs,
preregistrations, corrections and this file.

The evidence is the git history:

- 96 of the 100 commits carry a `Co-Authored-By: Claude` trailer.
- 3 are the automated weekly refresh (`cofire-refresh`), which runs code the
  agent wrote.
- 1, the initial scaffold (`a3f212d`), has no trailer. The `AI_USAGE.md` in
  that same commit lists every file it added as agent-generated.

Earlier versions of this file marked four files as "intended for hand-rewrite
by the student": `cofire/model/features.py`, `cofire/model/train.py`,
`cofire/model/conformal.py` and `cofire/model/models/pi_convlstm.py`. Git
history shows no hand rewrite of them: every commit that touches them is
agent-attributed or is the scaffold. The model tree has been frozen since
commit `1d3b2c5`.

Some agent-generated work was later found wrong and corrected in the open,
with records kept rather than rewritten:

- the look-3 interval results (`docs/CORRECTION_LOOK3.md`);
- training-label leaks (`docs/LEAK_SWEEP.md`);
- a drought map missing from the 2022 archive and a missing map in the latest
  2026 issue (`STATUS.md`, `docs/DECISIONS.md`).

### v1.2 modules (all agent-generated)

| Module | What it does | Author |
|---|---|---|
| `cofire/v12/common.py` | v1.2 folds, embargo, the look-counter guard | AI agent |
| `cofire/v12/preds.py` | configuration A's held-out and nested out-of-fold predictions | AI agent |
| `cofire/v12/recal.py` | stage 1 recalibration variants | AI agent |
| `cofire/v12/gate.py` | stage 1 variants through the delayed-feedback gate | AI agent |
| `cofire/v12/stage1.py` | stage 1 runner and report | AI agent |
| `cofire/v12/snotel.py` | stage 2 SNOTEL April 1 fetch and station rule | AI agent |
| `cofire/v12/stage2.py` | stage 2 climate level model and report | AI agent |
| `cofire/v12/stage3.py` | stage 3 cross-domain pooling and report | AI agent |
| `cofire/v12/evaluate.py` | shared scoring, paired test, adoption rule | AI agent |
| `cofire/v12/forward.py` | stage 5 published forecasts and manifest | AI agent |
| `cofire/ship/gridmet_reach.py` | measures gridMET's revision reach | AI agent |
| `app/app/scoreboard/page.tsx` | the forecast record page | AI agent |
| `cofire/v12/stage4.py` | stage 4 lag-aware interval evaluation | AI agent |
| `cofire/v12/live.py` | adopted arms, live parameters, survivor recheck | AI agent |
| `cofire/v12/facts.py` | v1.2 results for the app, from the artifacts | AI agent |
| `cofire/v12/brief_static.py` | the precomputed latest brief | AI agent |
| `app/components/V12Results.tsx` | v1.2 section of the Method page | AI agent |
| `app/components/Offline.tsx`, `app/public/sw.js` | offline viewing | AI agent |
| `app/scripts/copy-maplibre-worker.mjs` | serves MapLibre 6's worker | AI agent |
| Spanish text in `app/lib/i18n/` for every page | draft translation, pending human review | AI agent |

### v1.3 modules and film assets (all agent-generated)

| Module or asset | What it does | Author |
|---|---|---|
| `cofire/v13/explain.py`, `artifacts/v13/explain/` | the tables behind frequency sentences, weeks like this one, why did this change | AI agent |
| `app/lib/explain.ts`, `app/components/Explain.tsx` | frequency sentence, icon array, weeks like this one, change decomposition | AI agent |
| `app/fonts/` (files and `OFL.txt` header) | the app's OFL fonts, self-hosted so the build fetches nothing | AI agent (fonts by their authors, SIL OFL) |
| `app/lib/basemap.ts` waterways fix | rivers drawn as lines, not filled wedges | AI agent |
| `app/lib/seal.json` | the unseal date as data, for the app, the film and the unseal script | AI agent (date decided by the owner) |
| `scripts/ledger_tool.py` | records a tool download in the ledger | AI agent |
| `cofire/v13/open_data.py`, `/open` API route | open data: CSV, GeoJSON, JSON and the index, CC BY 4.0 | AI agent |
| `app/app/data/page.tsx` and its strings | the open data page and data dictionary (Spanish draft, pending review) | AI agent |
| `research/README.md`, `tests/test_shipped_path.py` | which arms do not ship and why; the boundary and docstring checks | AI agent |
| Docstrings on the shipped path (96) | added without code changes | AI agent |
| `scripts/architecture.py`, `docs/architecture.svg`, README "For reviewers" | the architecture diagram and reviewer guide | AI agent |
| `docs/PREREGISTRATION_UNSEAL.md` | the unseal scoring plan, a draft for the owner to review before 2027-01-12 | AI agent (draft) |
| `scripts/unseal_2026.py`, `tests/test_unseal_2026.py` | the executable unseal and its refusal tests (not run) | AI agent |
| `scripts/serve_static.py`, `app/e2e/static/`, `app/playwright.static.config.ts`, `.github/workflows/smoke.yml` | local static server, daily smoke run, axe checks | AI agent |
| `vercel.json`, `scripts/vercel_build.sh`, `scripts/check_deploy.py` | the Vercel services (web, api), the web build, headers, and the post-deploy checks | AI agent |
| `cofire/deploy/`, `cofire/ship/cells.py`, `scripts/check_api_slim.py`, `tests/test_deploy.py`; the `pipeline` extra in `pyproject.toml` | the API's Vercel entry point, cells read from a URL, the slim-dependency check | AI agent |
| `app/lib/motion.ts`; the colour system in `app/tailwind.config.ts` and the 2026-10-22 interface pass | hydration-safe reduced motion; spruce accent, ink selection, data-only ember and ochre; layout and mobile fixes | AI agent |
| `app/components/landing/Flourish.tsx`, the photo reveal in `app/app/landing/page.tsx`, `.spotlight` in `globals.css` | homepage motion: photo frame reveal, word-by-word thesis, rolling labels, tile spotlight (ideas from Skiper UI, written from scratch) | AI agent |
| `film/` Remotion project (`src/`, `scripts/`, `capture/`) | the demo film: scenes, captures, number tracing, audio mix, captions, renders | AI agent |
| `film/SCRIPT.md`, `film/script/narration.json` | the narration, a draft for the student to rewrite and record | AI agent (draft) |
| `film/STORYBOARD.md`, `film/SOURCES.md`, `film/REVIEW.md`, `film/RECORDING_GUIDE.md` | the film's storyboard, sources, review checklist, recording guide | AI agent |
| `film/LICENSES/REMOTION.md` | the Remotion free-license determination | AI agent |
| `film/audio/sfx/` | 11 UI sounds chosen from Kenney's CC0 packs | AI agent selected (sounds by Kenney, CC0) |
| `film/audio/ducking.json` | the music ducking automation | AI agent |
| Scratch narration (generated, not committed) | macOS `say` reading the draft, marked as scratch on screen | AI agent |
| Spanish captions (`film/out/captions_es.srt`, generated) | draft translation, pending human review | AI agent |

## What the student wrote or decided

_To be completed by the student. This section is intentionally left blank.
The agent has not filled it in, and nothing above should be read as
describing the student's own contributions._

Suggested prompts, to be answered or removed:

- Which files, passages or figures did you write or edit by hand?
- Which research questions, designs, rules or tests were your idea?
- Which of the agent's results did you check yourself, and how?
- Where did you change the agent's course, and why?
- What did you learn that you could now do without the agent?
