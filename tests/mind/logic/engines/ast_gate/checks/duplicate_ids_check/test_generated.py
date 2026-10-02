from __future__ import annotations

from unittest.mock import MagicMock

from mind.logic.engines.ast_gate.checks.duplicate_ids_check import check_duplicate_ids


# ID: 7f016e38-a972-4c80-8c20-39f999b14990
def test_check_duplicate_ids():
    uuid_val = "12345678-1234-1234-1234-123456789abc"

    file_a = MagicMock()
    file_a.__str__ = MagicMock(return_value="src/a.py")
    file_a.read_text.return_value = f"def foo():\n    x = 1  # ID: {uuid_val}\n"

    file_b = MagicMock()
    file_b.__str__ = MagicMock(return_value="src/b.py")
    file_b.read_text.return_value = f"def bar():\n    y = 2  # ID: {uuid_val}\n"

    context = MagicMock()
    context.get_files.return_value = [file_a, file_b]

    findings = check_duplicate_ids(context, {})

    assert len(findings) == 1
    finding = findings[0]
    assert finding.check_id == "linkage.duplicate_ids"
    assert uuid_val in finding.message
    assert len(finding.context["duplicates"]) == 2
