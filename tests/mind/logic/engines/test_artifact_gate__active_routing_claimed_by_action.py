"""Tests for the active_routing_claimed_by_action check in artifact_gate.

Closes the coherence gap in #580: every ACTIVE entry in
.intent/enforcement/remediation/auto_remediation.yaml must be honored by
the routed action's @register_action(remediates=[…]) declaration. The
check is mind-layer clean — AST-parses src/body/atomic/**/*.py, no body
imports.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mind.logic.engines.artifact_gate import (
    _check_active_routing_claimed_by_action,
)


def _scaffold_repo(
    tmp_path: Path,
    auto_remediation_yaml: str,
    atomic_files: dict[str, str],
) -> Path:
    """Build a minimal repo skeleton the check function expects.

    Layout::

        <tmp_path>/
          .intent/enforcement/remediation/auto_remediation.yaml
          src/body/atomic/{filename}.py for each (filename, content)
    """
    yaml_path = tmp_path / ".intent/enforcement/remediation/auto_remediation.yaml"
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    yaml_path.write_text(auto_remediation_yaml, encoding="utf-8")

    atomic_dir = tmp_path / "src/body/atomic"
    atomic_dir.mkdir(parents=True, exist_ok=True)
    for fname, content in atomic_files.items():
        (atomic_dir / fname).write_text(content, encoding="utf-8")

    return tmp_path


_ACTION_SOURCE_TEMPLATE = '''\
from body.atomic.registry import register_action


@register_action(
    action_id={action_id!r},
    description="x",
    remediates={remediates!r},
)
def {func_name}():
    pass
'''


# ID: 08f9672d-3864-443f-a334-5ceec1cf8fb3
def test_active_entry_with_claimed_rule_passes(tmp_path: Path) -> None:
    """ACTIVE entry whose action's remediates list claims the rule → OK."""
    yaml_doc = (
        "mappings:\n"
        "  rule.alpha:\n"
        "    action: fix.alpha\n"
        "    confidence: 0.90\n"
        "    risk: low\n"
        "    status: ACTIVE\n"
    )
    atomic = {
        "alpha.py": _ACTION_SOURCE_TEMPLATE.format(
            action_id="fix.alpha",
            remediates=["rule.alpha"],
            func_name="action_alpha",
        ),
    }
    repo = _scaffold_repo(tmp_path, yaml_doc, atomic)

    result = _check_active_routing_claimed_by_action(
        repo, "active_routing_claimed_by_action"
    )
    assert result.ok is True
    assert result.violations == []


# ID: 7a3f9233-5ad1-43ce-b1d2-0c26083c0372
def test_active_entry_with_unclaimed_rule_violates(tmp_path: Path) -> None:
    """ACTIVE entry whose action's remediates list does NOT claim the rule
    produces one violation. This is the #580 shape.
    """
    yaml_doc = (
        "mappings:\n"
        "  rule.alpha:\n"
        "    action: fix.alpha\n"
        "    status: ACTIVE\n"
    )
    atomic = {
        "alpha.py": _ACTION_SOURCE_TEMPLATE.format(
            action_id="fix.alpha",
            remediates=["rule.something_else"],
            func_name="action_alpha",
        ),
    }
    repo = _scaffold_repo(tmp_path, yaml_doc, atomic)

    result = _check_active_routing_claimed_by_action(
        repo, "active_routing_claimed_by_action"
    )
    assert result.ok is False
    assert len(result.violations) == 1
    assert "rule.alpha" in result.violations[0]
    assert "fix.alpha" in result.violations[0]
    assert "does not claim" in result.violations[0]


# ID: 77fcaf1e-31d3-426a-ba0c-862baeb86b6c
def test_delegate_entry_with_unclaimed_rule_is_exempt(tmp_path: Path) -> None:
    """DELEGATE entries are placeholders for ADR-066 (must exist but routed
    to governor inbox, not autonomous). They MUST NOT trigger this rule even
    if the action's remediates doesn't claim them — that is the load-bearing
    distinction post-ADR-095.
    """
    yaml_doc = (
        "mappings:\n"
        "  modularity.needs_split:\n"
        "    action: fix.modularity\n"
        "    status: DELEGATE\n"
        "  modularity.class_too_large:\n"
        "    action: fix.modularity\n"
        "    status: DELEGATE\n"
    )
    atomic = {
        "modularity.py": _ACTION_SOURCE_TEMPLATE.format(
            action_id="fix.modularity",
            remediates=[],
            func_name="action_modularity",
        ),
    }
    repo = _scaffold_repo(tmp_path, yaml_doc, atomic)

    result = _check_active_routing_claimed_by_action(
        repo, "active_routing_claimed_by_action"
    )
    assert result.ok is True
    assert result.violations == []


# ID: 20b43295-c010-4cfa-a35f-9b4b57765cd1
def test_pending_entry_with_unclaimed_rule_is_exempt(tmp_path: Path) -> None:
    """PENDING entries (action not yet implemented) are exempt for the same
    reason as DELEGATE — they are placeholders, not autonomous-remediation
    claims.
    """
    yaml_doc = (
        "mappings:\n"
        "  some.future_rule:\n"
        "    action: fix.future\n"
        "    status: PENDING\n"
    )
    # Intentionally no file declaring fix.future — that's the PENDING shape.
    repo = _scaffold_repo(tmp_path, yaml_doc, atomic_files={})

    result = _check_active_routing_claimed_by_action(
        repo, "active_routing_claimed_by_action"
    )
    assert result.ok is True
    assert result.violations == []


# ID: 749371a7-f3f3-4ac9-90f6-d1c17362d798
def test_flow_entry_is_exempt(tmp_path: Path) -> None:
    """Entries dispatching through ``flow:`` (FlowExecutor) instead of an
    atomic action have no ``remediates`` list to check; exempt by design.
    """
    yaml_doc = (
        "mappings:\n"
        "  some.rule:\n"
        "    flow: some.flow_id\n"
        "    status: ACTIVE\n"
    )
    repo = _scaffold_repo(tmp_path, yaml_doc, atomic_files={})

    result = _check_active_routing_claimed_by_action(
        repo, "active_routing_claimed_by_action"
    )
    assert result.ok is True
    assert result.violations == []


def test_active_entry_routing_to_missing_action_violates(tmp_path: Path) -> None:
    """ACTIVE entry routing to an action that has no @register_action
    declaration anywhere in src/body/atomic/ → violation. (Distinct shape
    from 'action exists but doesn't claim this rule' — handled with its
    own message so the operator sees what to fix.)
    """
    yaml_doc = (
        "mappings:\n"
        "  rule.alpha:\n"
        "    action: fix.does_not_exist\n"
        "    status: ACTIVE\n"
    )
    repo = _scaffold_repo(tmp_path, yaml_doc, atomic_files={})

    result = _check_active_routing_claimed_by_action(
        repo, "active_routing_claimed_by_action"
    )
    assert result.ok is False
    assert len(result.violations) == 1
    assert "fix.does_not_exist" in result.violations[0]
    assert "no @register_action" in result.violations[0]


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
