"""The fixture overlay carries exactly the policy dependencies of the audit
path a seeded external run exercises -- enumerated from the code, not by hand.

Governor ruling 2026-09-15: policies belong in the fixture overlay, never the
machinery floor (ADR-119 excludes ``rules/`` from the floor), and only the
mechanically enumerated transitive policy dependencies of the exercised
audit path -- never CORE's rules wholesale. This test IS the enumeration:
the actions the ``code_modification`` audit sub-phases execute through
``ActionExecutor``, each action's registered ``policies``, each policy's
document, and each document's outward reference (``$schema``). A widened
path fails here before it fails live.
"""

from __future__ import annotations

import json
from pathlib import Path

from body.atomic import check_actions  # noqa: F401  -- registers check.imports
from body.atomic.registry import action_registry
from shared.infrastructure.intent.machinery_floor_integrity import floor_manifest


_HERE = Path(__file__).resolve().parent
REPO_ROOT = _HERE.parents[2]
OVERLAY_DIR = _HERE / "intent_overlay"

# The actions the audit phase's sub-phases hand to ActionExecutor for a
# code_modification run (AuditPhase._WORKFLOW_ROUTING default:
# canary_validation + style_check). canary_validation_phase executes
# check.imports; style_check_phase runs validate_code_async -- no action.
# Extend this when a sub-phase gains an ActionExecutor call.
AUDIT_PATH_ACTIONS: tuple[str, ...] = ("check.imports",)


def _overlay_and_floor_paths() -> set[str]:
    overlay = {
        p.relative_to(OVERLAY_DIR).as_posix()
        for p in OVERLAY_DIR.rglob("*")
        if p.is_file()
    }
    return overlay | set(floor_manifest())


def _policy_paths(action_id: str) -> list[str]:
    definition = action_registry.get(action_id)
    assert definition is not None, f"{action_id} is not registered"
    return [f"{policy_id}.json" for policy_id in definition.policies]


def test_every_audit_path_policy_is_delivered_by_the_overlay() -> None:
    present = _overlay_and_floor_paths()
    for action_id in AUDIT_PATH_ACTIONS:
        for rel in _policy_paths(action_id):
            assert rel in present, (
                f"{action_id} declares policy {rel!r}; the execution copy "
                "(floor + fixture overlay) does not carry it, so ActionExecutor "
                "refuses the action before it runs"
            )
            assert rel not in set(floor_manifest()), (
                f"{rel} must be overlay content: ADR-119 keeps rules/ out of the floor"
            )
            overlay_doc = OVERLAY_DIR / rel
            canonical = REPO_ROOT / ".intent" / rel
            assert overlay_doc.read_bytes() == canonical.read_bytes(), (
                f"{rel} must be byte-identical to CORE's own document"
            )
            # transitive: the document's outward references resolve in the copy
            doc = json.loads(overlay_doc.read_text("utf-8"))
            schema_ref = doc.get("$schema")
            if schema_ref:
                assert schema_ref in present, f"{rel} references {schema_ref}"


def test_overlay_rules_are_only_the_enumerated_dependencies() -> None:
    """No indiscriminate copying: every rules/ document in the overlay is a
    policy some documented consumer of the trial apparatus declares."""
    needed = {rel for a in AUDIT_PATH_ACTIONS for rel in _policy_paths(a)}
    # Prior rulings (materialize.py inventory): purity.json (fixture-owned
    # authority, 2026-09-05), capability_taxonomy_governance.json
    # (project.cognitive_roles / seed.external_run_resources, seeding unit),
    # proposal_lifecycle.json (claim.proposal, ruling 2026-09-07).
    needed |= {
        "rules/code/purity.json",
        "rules/ai/capability_taxonomy_governance.json",
        "rules/will/proposal_lifecycle.json",
    }
    overlay_rules = {
        p.relative_to(OVERLAY_DIR).as_posix()
        for p in (OVERLAY_DIR / "rules").rglob("*.json")
    }
    assert overlay_rules == needed, (
        f"unexplained overlay rules: {sorted(overlay_rules - needed)}; "
        f"missing: {sorted(needed - overlay_rules)}"
    )
