# tests/body/atomic/test_machinery_floor_action_risk_coverage.py
"""Regression gate for #685 — machinery floor action_risk.yaml must cover all
registered actions.

A missing entry causes a ConstitutionalError bootstrap crash on any core-admin
invocation from an onboarded external repo directory.  After ADR-108 D3 the
starter-intent no longer carries enforcement/config/ (floor-only content), so
the floor/starter drift check is retired — the floor is the sole source.
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


# ID: ecad44ff-1021-41b6-a06e-131c10f387f0
def test_floor_capability_taxonomy_loads_against_floor_action_risk(
    tmp_path: Path,
) -> None:
    """#957: every capability in the floor's operational_capabilities.yaml has
    an action_risk.yaml entry with the same risk (ADR-078 D3). Seven were
    missing, so in every adopter project the taxonomy failed to load and
    IntentGuard's capability chokepoint tier disabled itself."""
    import shutil

    from shared.infrastructure.intent.operational_capabilities import (
        load_operational_capabilities,
    )

    floor = _FLOOR_ACTION_RISK.parents[2]
    shutil.copytree(
        floor,
        tmp_path / ".intent",
        ignore=shutil.ignore_patterns("__pycache__", "__init__.py"),
    )
    capabilities = load_operational_capabilities(tmp_path)
    assert len(capabilities) > 0
