# tests/body/atomic/test_consolidated_action_risk_meta.py
"""Consolidated action_risk.yaml meta-gate (issue #722).

Three complementary gates:
1. Intent YAML gate — symmetric to the existing floor gate: every registered
   action must appear in .intent/enforcement/config/action_risk.yaml (the live
   runtime source consumed by ActionExecutor at boot).
2. Floor↔intent consistency — both files must agree on impact_level for every
   key they share. Divergence means the floor's installed default differs from
   the project-level override, which is either intentional (document it) or drift.
3. Orphan check — every entry in the floor YAML has a registered action. Orphans
   accumulate when actions are removed without cleaning up the floor config.
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

_INTENT_ACTION_RISK = (
    Path(__file__).parents[3]
    / ".intent"
    / "enforcement"
    / "config"
    / "action_risk.yaml"
)


def _impact_level(value: str | dict) -> str:
    """Normalise both flat-string and dict-format entries to an impact_level string."""
    if isinstance(value, str):
        return value
    return value.get("impact_level", "")


# ID: 882f2cd1-6116-491a-8898-ab55cf821c69
def test_intent_action_risk_covers_all_registered_actions() -> None:
    """Every registered action must appear in .intent/enforcement/config/action_risk.yaml.

    This is the live runtime source consumed by ActionExecutor at boot.
    A missing entry causes a ConstitutionalError crash on executor init.
    Symmetric gate to test_floor_action_risk_covers_all_registered_actions.
    """
    doc = yaml.safe_load(_INTENT_ACTION_RISK.read_text(encoding="utf-8"))
    intent_actions: set[str] = set(doc.get("actions", {}).keys())
    registered_ids = {a.action_id for a in action_registry.list_all()}
    missing = registered_ids - intent_actions

    assert not missing, (
        f".intent/enforcement/config/action_risk.yaml is missing {len(missing)} "
        f"registered action(s): {sorted(missing)}. "
        "Add them to .intent/enforcement/config/action_risk.yaml."
    )


# ID: 4575096b-1762-4140-8eff-d15a3ec3f86e
def test_floor_and_intent_impact_levels_agree() -> None:
    """Floor and intent action_risk.yaml must agree on impact_level for shared keys.

    The floor is the installed default for external (BYOR) consumers; the intent
    is the project-level override. Divergence means an external consumer gets a
    different risk classification than the project itself runs under — a silent
    safety regression. Document intentional divergences with a comment in the
    floor file and add the key to the allowlist below.
    """
    floor_doc = yaml.safe_load(_FLOOR_ACTION_RISK.read_text(encoding="utf-8"))
    intent_doc = yaml.safe_load(_INTENT_ACTION_RISK.read_text(encoding="utf-8"))

    floor_actions: dict[str, str] = {
        k: _impact_level(v) for k, v in floor_doc.get("actions", {}).items()
    }
    intent_actions: dict[str, str] = {
        k: _impact_level(v) for k, v in intent_doc.get("actions", {}).items()
    }

    common_keys = set(floor_actions) & set(intent_actions)
    diverged = {
        k: (floor_actions[k], intent_actions[k])
        for k in sorted(common_keys)
        if floor_actions[k] != intent_actions[k]
    }

    assert not diverged, (
        f"Floor↔intent impact_level divergence on {len(diverged)} action(s): "
        + ", ".join(
            f"{k} (floor={fv!r} intent={iv!r})" for k, (fv, iv) in diverged.items()
        )
        + ". Fix the floor or the intent entry, or document the intentional divergence."
    )


# ID: 1edfd97b-5773-4ca9-9179-0d9a91d3eec7
def test_no_orphan_actions_in_floor() -> None:
    """Every entry in the floor action_risk.yaml has a corresponding registered action.

    Orphan entries accumulate when actions are removed without cleaning up the
    floor config. They are harmless at runtime but indicate stale configuration
    that can mislead future maintainers about which actions are active.
    """
    doc = yaml.safe_load(_FLOOR_ACTION_RISK.read_text(encoding="utf-8"))
    floor_actions: set[str] = set(doc.get("actions", {}).keys())
    registered_ids = {a.action_id for a in action_registry.list_all()}
    orphans = floor_actions - registered_ids

    assert not orphans, (
        f"Floor action_risk.yaml has {len(orphans)} orphan entry(s) with no "
        f"registered action: {sorted(orphans)}. "
        "Remove them from src/shared/_machinery_floor/enforcement/config/action_risk.yaml."
    )
