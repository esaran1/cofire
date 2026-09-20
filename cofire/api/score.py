"""Score Beat-the-Model picks against realized values when they exist."""

from __future__ import annotations

from sqlmodel import Session, select

from cofire.api import PredictionRow, engine, load_index


def run() -> None:
    index = load_index()
    with Session(engine) as session:
        rows = session.exec(select(PredictionRow)).all()
        print(f"unscored picks={len(rows)} cells_in_index={len(index.get('cells', []))}")
        # Realized scoring happens once USDM/ERC for the valid date are in the index.
        # v0.2 reports counts only; exact-match and Brier attach when labels land.


if __name__ == "__main__":
    run()
