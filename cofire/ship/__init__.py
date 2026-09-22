"""Shipping layer: export, rendering rules, facts and demo data.

Separate from `cofire/model/` because that tree is frozen at `FREEZE_COMMIT`
and `tests/test_frozen_model.py` asserts nothing in it changes. Everything here
reads the frozen model and the artifacts it produced; nothing here fits,
chooses, or scores anything.
"""
