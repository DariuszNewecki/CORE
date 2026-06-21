# tests/body/atomic/test_action_risk_overlay.py
"""
ADR-120 D1 — apply_risk_config overlays both impact_level and artifact_type
from action_risk.yaml entries (string format and dict format).
"""

from __future__ import annotations

import pytest

from body.atomic.registry import (
    ActionCategory,
    ActionDefinition,
    ActionRegistry,
    ConstitutionalError,
)
from shared.action_types import ActionResult


# ── Helpers ──────────────────────────────────────────────────────────────────

# ID: d2a9f0b6-e9e2-4b5b-b394-0938bf019e77
async def _stub_executor(**_kwargs: object) -> ActionResult:
    return ActionResult(action_id="stub", ok=True, data={}, duration_sec=0.0)


# ID: 771bb41d-7cad-4b7d-86e8-c03e54080845
def _make_registry(*action_ids: str) -> ActionRegistry:
    registry = ActionRegistry()
    for aid in action_ids:
        registry.register(
            ActionDefinition(
                action_id=aid,
                description="stub",
                category=ActionCategory.CHECK,
                policies=[],
                executor=_stub_executor,
            )
        )
    return registry


# ── Tests ─────────────────────────────────────────────────────────────────────

# ID: a7b12440-5b69-40f7-8167-7e52c6b501ee
def test_apply_risk_config_flat_string_format() -> None:
    """Old flat-string entries overlay impact_level; artifact_type stays empty."""
    registry = _make_registry("fix.a", "fix.b")
    registry.apply_risk_config({"fix.a": "safe", "fix.b": "moderate"})

    assert registry.get("fix.a").impact_level == "safe"
    assert registry.get("fix.a").artifact_type == ()
    assert registry.get("fix.b").impact_level == "moderate"
    assert registry.get("fix.b").artifact_type == ()


# ID: 8e01fc57-ba4f-4fdf-9f31-b2e19a939f0e
def test_apply_risk_config_dict_format_overlays_both_fields() -> None:
    """New dict entries overlay both impact_level and artifact_type (ADR-120 D1)."""
    registry = _make_registry("fix.format", "fix.imports")
    registry.apply_risk_config(
        {
            "fix.format": {"impact_level": "safe", "artifact_types": ["python"]},
            "fix.imports": {"impact_level": "safe", "artifact_types": ["python"]},
        }
    )

    assert registry.get("fix.format").impact_level == "safe"
    assert registry.get("fix.format").artifact_type == ("python",)
    assert registry.get("fix.imports").impact_level == "safe"
    assert registry.get("fix.imports").artifact_type == ("python",)


# ID: e76e3d0e-b0c6-4b6a-bb9e-20a2bc8d5134
def test_apply_risk_config_mixed_format() -> None:
    """Mixed old and new format in the same mapping works correctly."""
    registry = _make_registry("infra.action", "fix.code")
    registry.apply_risk_config(
        {
            "infra.action": "moderate",
            "fix.code": {"impact_level": "safe", "artifact_types": ["python"]},
        }
    )

    assert registry.get("infra.action").impact_level == "moderate"
    assert registry.get("infra.action").artifact_type == ()
    assert registry.get("fix.code").impact_level == "safe"
    assert registry.get("fix.code").artifact_type == ("python",)


# ID: 1cc5aa00-4cde-41aa-b9b6-62e50de5ea2f
def test_apply_risk_config_missing_action_raises_constitutional_error() -> None:
    """Registered action missing from the mapping raises ConstitutionalError."""
    registry = _make_registry("fix.a", "fix.b")
    with pytest.raises(ConstitutionalError, match=r"fix\.b"):
        registry.apply_risk_config({"fix.a": "safe"})


# ID: 90ae779d-8d60-4831-9d06-ebd7aa752d6e
def test_apply_risk_config_empty_artifact_types_list() -> None:
    """dict entry with artifact_types: [] results in empty tuple (unconstrained)."""
    registry = _make_registry("infra.sync")
    registry.apply_risk_config(
        {"infra.sync": {"impact_level": "moderate", "artifact_types": []}}
    )

    assert registry.get("infra.sync").impact_level == "moderate"
    assert registry.get("infra.sync").artifact_type == ()


# ID: 8c403ddd-8879-4081-8a82-35a9a7d70744
def test_apply_risk_config_multi_artifact_type() -> None:
    """dict entry with multiple artifact_types is stored as a tuple."""
    registry = _make_registry("fix.multi")
    registry.apply_risk_config(
        {"fix.multi": {"impact_level": "safe", "artifact_types": ["python", "test"]}}
    )

    assert registry.get("fix.multi").artifact_type == ("python", "test")
