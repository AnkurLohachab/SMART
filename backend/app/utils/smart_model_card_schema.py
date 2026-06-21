"""JSON Schema export for smart-model-card."""

from __future__ import annotations

from typing import Dict, Any


def get_model_card_json_schema() -> Dict[str, Any]:
    """Return a JSON Schema describing the model card payload."""
    from smart_model_card import get_model_card_json_schema as _pkg_schema
    return _pkg_schema()
