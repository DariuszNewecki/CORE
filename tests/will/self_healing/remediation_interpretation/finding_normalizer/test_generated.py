from __future__ import annotations

from unittest.mock import MagicMock

from will.self_healing.remediation_interpretation.finding_normalizer import (
    FindingNormalizer,
)


# ID: 7ff5a7c5-be93-40b3-8439-33658e2f9090
def test_FindingNormalizer_normalize() -> None:
    normalizer = FindingNormalizer()

    normalized_a = MagicMock(name="normalized_a")
    normalized_b = MagicMock(name="normalized_b")
    normalized_c = MagicMock(name="normalized_c")

    normalizer.normalize_one = MagicMock(
        side_effect=[normalized_b, normalized_a, normalized_c]
    )
    normalizer._sort_key = MagicMock(
        side_effect=lambda item: {
            normalized_a: 1,
            normalized_b: 2,
            normalized_c: 3,
        }[item]
    )

    findings = [{"raw": "b"}, {"raw": "a"}, {"raw": "c"}]
    result = normalizer.normalize(findings)

    assert result == [normalized_a, normalized_b, normalized_c]
    assert normalizer.normalize_one.call_count == 3
    assert [
        call.args[0] for call in normalizer.normalize_one.call_args_list
    ] == findings


from unittest.mock import patch


# ID: 592a0f9b-cf52-4240-a053-0ca93d38d7a9
def test_FindingNormalizer():
    findings = [
        {
            "id": "finding-2",
            "subject": "python::py.flake8.E501::b.py",
            "payload": {
                "rule": "py.flake8.E501",
                "file_path": "b.py",
                "line_number": "10",
                "message": "line too long",
                "severity": "warn",
                "dry_run": True,
            },
        },
        {
            "id": "finding-1",
            "subject": "python::py.flake8.E501::a.py",
            "payload": {
                "rule": "py.flake8.E501",
                "rule_namespace": "py.flake8",
                "file_path": "a.py",
                "line_number": 3,
                "message": "line too long",
                "severity": "error",
                "dry_run": False,
                "context": {"extra": "value"},
            },
        },
    ]

    with patch(
        "shared.infrastructure.intent.audit_namespaces.is_audit_violation_subject",
        return_value=True,
    ):
        normalizer = FindingNormalizer()
        result = normalizer.normalize(findings)

    assert len(result) == 2
    first, second = result
    assert first.finding_id == "finding-1"
    assert first.file_path == "a.py"
    assert first.line_number == 3
    assert first.rule_id == "py.flake8.E501"
    assert first.rule_namespace == "py.flake8"
    assert first.severity == "error"
    assert first.dry_run is False
    assert first.raw_context == {"extra": "value"}

    assert second.finding_id == "finding-2"
    assert second.file_path == "b.py"
    assert second.line_number == 10
    assert second.severity == "warning"
    assert second.dry_run is True





# ID: fe3ac9ec-4358-4596-b63b-fa630940b84e
def test_FindingNormalizer_normalize_one():
    normalizer = FindingNormalizer()

    finding = {
        "id": "finding-123",
        "subject": "blackboard.finding.rule-abc",
        "payload": {
            "rule": "no-unused-vars",
            "rule_namespace": "lint",
            "file_path": "src/app.py",
            "line_number": 42,
            "message": "unused variable x",
            "severity": "warning",
            "dry_run": False,
        },
    }

    result = normalizer.normalize_one(finding)

    assert result.finding_id == "finding-123"
    assert result.subject == "blackboard.finding.rule-abc"
    assert result.rule_id == "no-unused-vars"
    assert result.rule_namespace == "lint"
    assert result.file_path == "src/app.py"
    assert result.line_number == 42
    assert result.message == "unused variable x"
    assert result.severity == "warning"
    assert result.dry_run is False
    assert result.raw_payload == finding["payload"]
