"""Re-export SHAP helpers (student-facing name)."""

from cofire.model.explain import cache_why, explain_row, grouped_shap, shap_for_booster

__all__ = ["cache_why", "explain_row", "grouped_shap", "shap_for_booster"]
