"""Summarise Beat-the-Model picks: how many are scored and how many points.

Scoring happens on read (`cofire.api.score_pick`): a pick is scored once its
target week is in the forecast record. Only players are scored; the model's
call is never compared with 2026 outcomes, because 2026 is the sealed year.
"""

from __future__ import annotations

from sqlmodel import Session, select

from cofire.api import PredictionRow, _cells_by_key, engine, score_pick


def run() -> None:
    cells = _cells_by_key()
    with Session(engine) as session:
        picks = [r.model_dump() for r in session.exec(select(PredictionRow)).all()]
    scored = [s for s in (score_pick(p, cells) for p in picks) if s["status"] == "scored"]
    points = sum(int(s["points"]) for s in scored)
    print(f"picks={len(picks)} scored={len(scored)} pending={len(picks) - len(scored)} points={points}")


if __name__ == "__main__":
    run()
