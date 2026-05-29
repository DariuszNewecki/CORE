# tests/shared/infrastructure/test_phase_failure_mode_canonical_alignment.py

"""
Failure-mode canonical-alignment drift guard (ADR-074 D10).

Asserts that the four surfaces declaring failure-mode response-strategy
vocabulary stay in lock-step:

  1. .intent/META/enums.json#/definitions/failure_mode  (canonical)
  2. .intent/phases/*.yaml failure_modes map values     (governance data)
  3. src/will/orchestration/workflow_orchestrator.py    (runtime consumer)
  4. src/mind/coherence/checks/specgap.py               (CCC consumer)

Drift in any direction fails noisily so the closed-enum discipline
(principle 2 / [[feedback_enum_subset_canonicalize_and_fail_closed]])
holds across the consumer fan-out.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from shared.infrastructure.intent.canonical_enums import (
    get_enum_members,
    reload_enums_cache,
)


_REPO_ROOT = Path(__file__).resolve().parents[3]
_PHASES_DIR = _REPO_ROOT / ".intent" / "phases"
_ORCHESTRATOR = (
    _REPO_ROOT / "src" / "will" / "orchestration" / "workflow_orchestrator.py"
)


def setup_function(_func) -> None:
    """Force a fresh read of enums.json for every test."""
    reload_enums_cache()


def _phase_yaml_paths() -> list[Path]:
    return sorted(_PHASES_DIR.glob("*.yaml"))


def test_failure_mode_enum_is_declared_and_non_empty() -> None:
    """enums.json must declare failure_mode with a non-empty closed enum."""
    members = get_enum_members("failure_mode")
    assert members, "enums.json#/definitions/failure_mode is empty or missing."
    assert "block" in members, (
        "failure_mode enum is missing 'block'. ADR-074 D3 declares block as a "
        "v1 canonical strategy."
    )
    assert "clarify" in members, (
        "failure_mode enum is missing 'clarify'. ADR-074 D3 declares clarify as "
        "a v1 canonical strategy for INTERPRET ambiguity per UR-03."
    )


def test_every_phase_yaml_uses_failure_modes_map() -> None:
    """All phase YAMLs declare failure_modes (map), not failure_mode (scalar)."""
    for path in _phase_yaml_paths():
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        assert "failure_mode" not in data, (
            f"{path.name} still declares legacy scalar `failure_mode`. "
            f"Migrate to `failure_modes:` map per ADR-074 D2."
        )
        modes = data.get("failure_modes")
        assert isinstance(modes, dict) and modes, (
            f"{path.name} is missing or has empty `failure_modes:` map. "
            f"ADR-074 D2 requires a non-empty mapping from failure-class to "
            f"response-strategy."
        )


def test_phase_yaml_failure_mode_values_are_canonical() -> None:
    """Every response-strategy value in any phase YAML must be a failure_mode enum member."""
    canonical = get_enum_members("failure_mode")
    for path in _phase_yaml_paths():
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        modes = data.get("failure_modes") or {}
        for failure_class, strategy in modes.items():
            assert strategy in canonical, (
                f"{path.name} declares failure_modes.{failure_class}={strategy!r} "
                f"which is not in canonical failure_mode enum "
                f"({sorted(canonical)}). Either add the value to "
                f".intent/META/enums.json#/definitions/failure_mode or "
                f"correct the phase YAML."
            )


def test_interpret_declares_both_ur_03_classes() -> None:
    """interpret.yaml must declare ambiguity AND contradiction per UR-03."""
    data = (
        yaml.safe_load((_PHASES_DIR / "interpret.yaml").read_text(encoding="utf-8"))
        or {}
    )
    modes = data.get("failure_modes") or {}
    assert modes.get("ambiguity") == "clarify", (
        "interpret.yaml must declare `ambiguity: clarify` per ADR-074 D1/D2 "
        "(UR-03: 'For gaps and ambiguities: CORE asks')."
    )
    assert modes.get("contradiction") == "block", (
        "interpret.yaml must declare `contradiction: block` per ADR-074 D1/D2 "
        "(UR-03: 'For contradictions: CORE stops')."
    )


def test_orchestrator_recognizes_every_canonical_strategy() -> None:
    """workflow_orchestrator.py must reference every failure_mode enum member by literal.

    The orchestrator's decision rule (ADR-074 D7) branches on response-strategy
    literals. If the canonical enum gains a member that the orchestrator does
    not handle, that strategy silently falls through — the latent governance
    bug this ADR closes for `clarify` would reappear for the new member.
    """
    source = _ORCHESTRATOR.read_text(encoding="utf-8")
    for member in get_enum_members("failure_mode"):
        literal = f'"{member}"'
        assert literal in source, (
            f"workflow_orchestrator.py does not reference failure_mode literal "
            f"{literal}. Either the orchestrator is missing a strategy branch "
            f"or the canonical enum has gained a member that needs handling "
            f"(ADR-074 D7 / D10)."
        )


def test_block_strategy_matches_halt_class_action_verb() -> None:
    """The `block` strategy value must literally match a halt-class action verb.

    Per ADR-074 D9, SPECGAP's coverage check matches map values against the
    normative-marker action-verb register. `block` is the v1 halt-class
    strategy; if it stops matching the register, every UR-03 SPECGAP guard
    for sibling phases regresses to false-positive.
    """
    register_path = (
        _REPO_ROOT / ".intent" / "enforcement" / "config" / "normative_markers.yaml"
    )
    register = yaml.safe_load(register_path.read_text(encoding="utf-8")) or {}
    action_verbs = {v.lower() for v in register.get("action_verbs", [])}
    assert "block" in action_verbs, (
        "normative_markers.yaml#action_verbs has lost `block`. SPECGAP's "
        "coverage check will no longer recognize the `block` strategy as "
        "addressing UR-03 halt-class signals (ADR-074 D9)."
    )
