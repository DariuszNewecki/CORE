# tests/mind/logic/engines/cli_gate/checks/standard_verbs/test_standard_verbs_check.py

"""Unit tests for StandardVerbsCheck.

Key regression: the check must examine the FINAL segment of the command
name (the action) not parts[1]. For depth-3 paths like
'coherence.seed.import', parts[1] is the sub-resource ('seed'); the
action is parts[-1] ('import').
"""

from __future__ import annotations

from mind.logic.engines.cli_gate.checks.standard_verbs import StandardVerbsCheck


ALLOWED = {"list", "get", "create", "delete", "import", "export", "bootstrap"}
PARAMS = {"allowed_verbs": list(ALLOWED)}


def _cmd(name: str, file_path: str = "src/cli/resources/foo.py") -> dict:
    return {"name": name, "file_path": file_path}


# ID: dcd726c0-50bf-4e6e-853f-745e063c93f0
def test_depth2_allowed_verb_no_finding():
    check = StandardVerbsCheck()
    findings = check.verify([_cmd("workers.list")], PARAMS)
    assert findings == []


# ID: 97a7168a-3ccc-487b-9e72-207f3473b591
def test_depth2_non_standard_verb_raises_finding():
    check = StandardVerbsCheck()
    findings = check.verify([_cmd("workers.blackboard")], PARAMS)
    assert len(findings) == 1
    assert "blackboard" in findings[0].message
    assert findings[0].context["action"] == "blackboard"


# ID: 44ec7424-c93b-43c7-9bfe-953616e391ba
def test_depth3_action_is_final_segment_not_subresource():
    """Regression: depth-3 'coherence.seed.import' must flag nothing —
    'import' is allowed; 'seed' is the sub-resource and must not be checked."""
    check = StandardVerbsCheck()
    findings = check.verify([_cmd("coherence.seed.import")], PARAMS)
    assert findings == [], f"unexpected findings: {[f.message for f in findings]}"


# ID: 279ccefe-9e8f-4469-9679-4120ed0fdcbb
def test_depth3_all_seed_subcommands_cleared():
    commands = [
        _cmd("coherence.seed.import"),
        _cmd("coherence.seed.export"),
        _cmd("coherence.seed.bootstrap"),
    ]
    check = StandardVerbsCheck()
    findings = check.verify(commands, PARAMS)
    assert findings == []


# ID: 8a472e2a-5c83-4f41-833b-482410e440de
def test_depth3_non_standard_final_segment_still_flags():
    """depth-3 path where the action itself is non-standard should still fire."""
    check = StandardVerbsCheck()
    findings = check.verify([_cmd("dev.campaign.accept")], PARAMS)
    assert len(findings) == 1
    assert findings[0].context["action"] == "accept"
    assert "accept" in findings[0].message


# ID: 133ddefc-e68a-4539-8637-f9c60746d2ff
def test_empty_commands_returns_empty():
    check = StandardVerbsCheck()
    assert check.verify([], PARAMS) == []


# ID: 6b69c81f-775c-4b1d-9f67-044ba1a9b6e9
def test_empty_allowed_verbs_returns_empty():
    check = StandardVerbsCheck()
    assert check.verify([_cmd("workers.purge")], {"allowed_verbs": []}) == []


# ID: 20242901-2ac2-4e68-9a8f-7d737930f8db
def test_command_with_single_segment_skipped():
    check = StandardVerbsCheck()
    assert check.verify([_cmd("orphan")], PARAMS) == []


# ID: d7b16bc9-06fd-41c8-93fa-ea1e57f313cb
def test_finding_contains_full_command_name():
    check = StandardVerbsCheck()
    findings = check.verify([_cmd("lane.propose")], PARAMS)
    assert len(findings) == 1
    assert findings[0].context["command_name"] == "lane.propose"


# ID: de928967-813a-41e5-b024-c905273bb2de
def test_multiple_commands_only_non_standard_flagged():
    commands = [
        _cmd("workers.list"),
        _cmd("workers.blackboard"),
        _cmd("coherence.seed.import"),
        _cmd("lane.claim"),
    ]
    check = StandardVerbsCheck()
    findings = check.verify(commands, PARAMS)
    flagged = {f.context["command_name"] for f in findings}
    assert flagged == {"workers.blackboard", "lane.claim"}
