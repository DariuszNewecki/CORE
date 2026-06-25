# tests/body/atomic/test_machinery_floor_action_risk_coverage.py
"""Regression gate for #685 — machinery floor action_risk.yaml must cover all
registered actions, and the starter-intent must mirror the floor's key set.

A missing entry causes a ConstitutionalError bootstrap crash on any core-admin
invocation from an onboarded external repo directory. This test catches both
floor/registry drift and floor/starter drift before they reach an adopter.
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

_STARTER_ACTION_RISK = (
    Path(__file__).parents[3]
    / "examples"
    / "starter-intent"
    / ".intent"
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


# ID: 3e8c21f0-a94b-4b17-bf6a-1c72d5e09a8b
def test_starter_action_risk_covers_floor() -> None:
    """starter-intent must contain every key the floor declares.

    The starter is what ``project onboard`` copies for source-tree installs.
    If a new action is added to the floor but not the starter, every adopter
    running from a source tree gets a bootstrap crash (ConstitutionalError).
    """
    floor_doc = yaml.safe_load(_FLOOR_ACTION_RISK.read_text(encoding="utf-8"))
    starter_doc = yaml.safe_load(_STARTER_ACTION_RISK.read_text(encoding="utf-8"))
    floor_keys: set[str] = set(floor_doc.get("actions", {}).keys())
    starter_keys: set[str] = set(starter_doc.get("actions", {}).keys())
    missing = floor_keys - starter_keys

    assert not missing, (
        f"starter-intent action_risk.yaml is missing {len(missing)} action(s) "
        f"that the machinery floor declares: {sorted(missing)}. "
        f"Add them to examples/starter-intent/.intent/enforcement/config/action_risk.yaml."
    )
