# tests/body/atomic/test_machinery_floor_action_risk_coverage.py
"""Regression gate for #685 — machinery floor action_risk.yaml must cover all
registered actions.

A missing entry causes a ConstitutionalError bootstrap crash on any core-admin
invocation from an onboarded external repo directory. This test catches floor/
registry drift before it reaches an adopter.
"""

from __future__ import annotations

from pathlib import Path

import yaml

import body.atomic  # noqa: F401 — side effect: populates action_registry
from body.atomic.registry import action_registry


_FLOOR_ACTION_RISK = (
    Path(__file__).parents[3]
    / "src"
    / "shared"
    / "_machinery_floor"
    / "enforcement"
    / "config"
    / "action_risk.yaml"
)


# ID: a0ee8aba-49c3-4d4d-a826-4bba0cd90ef6
def test_floor_action_risk_covers_all_registered_actions() -> None:
    doc = yaml.safe_load(_FLOOR_ACTION_RISK.read_text(encoding="utf-8"))
    floor_actions: set[str] = set(doc.get("actions", {}).keys())
    registered_ids = {a.action_id for a in action_registry.list_all()}
    missing = registered_ids - floor_actions

    assert not missing, (
        f"Machinery floor action_risk.yaml is missing {len(missing)} registered "
        f"action(s): {sorted(missing)}. "
        f"Add them to src/shared/_machinery_floor/enforcement/config/action_risk.yaml."
    )


# ID: 12a7d6c0-7705-4ccd-a73a-8fc3f62d4c83
def test_floor_action_risk_yaml_is_parseable() -> None:
    doc = yaml.safe_load(_FLOOR_ACTION_RISK.read_text(encoding="utf-8"))
    assert isinstance(doc, dict), "floor action_risk.yaml did not parse to a dict"
    assert "actions" in doc, "floor action_risk.yaml missing top-level 'actions' key"
    assert len(doc["actions"]) > 0, "floor action_risk.yaml has an empty actions block"
