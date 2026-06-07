from __future__ import annotations

from shared.infrastructure.context.shadow_audit_diff import ShadowAuditDiff


def _finding(
    check_id: str,
    file_path: str | None,
    line_number: int | None,
    *,
    severity: str = "blocking",
    message: str = "violation detected",
) -> dict:
    return {
        "check_id": check_id,
        "severity": severity,
        "message": message,
        "file_path": file_path,
        "line_number": line_number,
        "context": {},
    }


def test_empty_inputs_produce_empty_diff() -> None:
    diff = ShadowAuditDiff([], [])
    assert diff.new_findings() == []
    assert diff.resolved_findings() == []
    assert diff.unchanged_findings() == []
    assert diff.is_clean()


def test_identical_findings_count_as_unchanged_not_new_or_resolved() -> None:
    f = _finding("rule.a", "src/foo.py", 10)
    diff = ShadowAuditDiff([f], [f])
    assert diff.new_findings() == []
    assert diff.resolved_findings() == []
    assert len(diff.unchanged_findings()) == 1


def test_finding_only_in_shadow_surfaces_in_new_findings() -> None:
    disk: list[dict] = []
    shadow = [_finding("rule.a", "src/foo.py", 10)]
    diff = ShadowAuditDiff(disk, shadow)
    new = diff.new_findings()
    assert len(new) == 1
    assert new[0].check_id == "rule.a"
    assert new[0].file_path == "src/foo.py"
    assert new[0].line_number == 10
    assert not diff.is_clean()


def test_finding_only_in_disk_surfaces_in_resolved() -> None:
    disk = [_finding("rule.a", "src/foo.py", 10)]
    shadow: list[dict] = []
    diff = ShadowAuditDiff(disk, shadow)
    resolved = diff.resolved_findings()
    assert len(resolved) == 1
    assert resolved[0].check_id == "rule.a"
    assert diff.is_clean()  # no new findings is "clean" even if nothing was resolved


def test_findings_at_different_locations_are_independent() -> None:
    # Same rule, different line — two distinct findings
    disk = [_finding("rule.a", "src/foo.py", 10)]
    shadow = [
        _finding("rule.a", "src/foo.py", 10),
        _finding("rule.a", "src/foo.py", 20),
    ]
    diff = ShadowAuditDiff(disk, shadow)
    assert len(diff.new_findings()) == 1
    assert diff.new_findings()[0].line_number == 20
    assert len(diff.unchanged_findings()) == 1


def test_same_rule_different_file_yields_distinct_keys() -> None:
    disk = [_finding("rule.a", "src/foo.py", 10)]
    shadow = [_finding("rule.a", "src/bar.py", 10)]
    diff = ShadowAuditDiff(disk, shadow)
    assert len(diff.new_findings()) == 1
    assert len(diff.resolved_findings()) == 1
    assert diff.new_findings()[0].file_path == "src/bar.py"


def test_message_drift_does_not_split_findings_at_same_location() -> None:
    # Same check_id + file + line but different message wording — still
    # the same finding, not a new one.
    disk = [_finding("rule.a", "src/foo.py", 10, message="x")]
    shadow = [_finding("rule.a", "src/foo.py", 10, message="y")]
    diff = ShadowAuditDiff(disk, shadow)
    assert diff.new_findings() == []
    assert len(diff.unchanged_findings()) == 1


def test_findings_with_none_line_collapse_per_rule_and_file() -> None:
    # Context-level findings (line=None) at the same rule+file collapse
    disk = [_finding("rule.ctx", "src/foo.py", None)]
    shadow = [_finding("rule.ctx", "src/foo.py", None)]
    diff = ShadowAuditDiff(disk, shadow)
    assert len(diff.unchanged_findings()) == 1
    assert diff.new_findings() == []


def test_is_clean_true_when_no_new_findings_regardless_of_resolved() -> None:
    # Resolving a finding without introducing new ones is "clean."
    disk = [_finding("rule.a", "src/foo.py", 10)]
    shadow: list[dict] = []
    assert ShadowAuditDiff(disk, shadow).is_clean()


def test_is_clean_false_when_any_new_finding_present() -> None:
    disk: list[dict] = []
    shadow = [_finding("rule.a", "src/foo.py", 10)]
    assert not ShadowAuditDiff(disk, shadow).is_clean()


def test_results_are_deterministically_sorted() -> None:
    disk: list[dict] = []
    shadow = [
        _finding("rule.z", "src/z.py", 1),
        _finding("rule.a", "src/a.py", 1),
        _finding("rule.m", "src/m.py", 1),
    ]
    diff = ShadowAuditDiff(disk, shadow)
    ids = [r.check_id for r in diff.new_findings()]
    assert ids == sorted(ids)
