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
commit `46c17ae`.

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
