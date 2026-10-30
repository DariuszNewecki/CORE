from __future__ import annotations

from unittest.mock import MagicMock

from will.self_healing.remediation_interpretation.file_context_assembler import (
    FileContextAssembler,
)


# ID: 9cbaa1d3-016b-4bad-9f91-a277906560bd
def test_FileContextAssembler_assemble() -> None:
    assembler = FileContextAssembler()

    file_path = "example.py"
    source_code = (
        '"""Example module docstring."""\n'
        "import os\n\n"
        "class Foo:\n"
        "    pass\n\n"
        "def bar():\n"
        "    return 1\n"
    )

    finding = MagicMock()
    finding.severity = "high"
    finding.rule_id = "R001"
    finding.message = "something"
    finding.line = 3

    file_role = MagicMock()
    file_role.role_id = "source"
    file_role.layer = "domain"
    file_role.confidence = 0.9
    file_role.evidence = ["extension:.py"]

    assembler._parse_ast = MagicMock(return_value=MagicMock())
    assembler._extract_imports = MagicMock(return_value=["os"])
    assembler._extract_top_level_symbols = MagicMock(
        return_value=[
            {"name": "Foo", "symbol_type": "class"},
            {"name": "bar", "symbol_type": "function"},
        ]
    )
    assembler._extract_module_docstring = MagicMock(
        return_value="Example module docstring."
    )
    assembler._build_file_metrics = MagicMock(return_value={"loc": 7})
    assembler._build_violation_summary = MagicMock(return_value={"count": 1})
    assembler._infer_role_constraints = MagicMock(return_value={"allowed": True})
    assembler._build_structural_signals = MagicMock(return_value={"signals": []})

    result = assembler.assemble(
        file_path=file_path,
        source_code=source_code,
        findings=[finding],
        file_role=file_role,
    )

    assert result["file_path"] == file_path
    assert result["file_role"] == {
        "role_id": "source",
        "layer": "domain",
        "confidence": 0.9,
        "evidence": ["extension:.py"],
    }
    assert result["module_docstring"] == "Example module docstring."
    assert result["imports"] == ["os"]
    assert result["top_level_symbols"] == [
        {"name": "Foo", "symbol_type": "class"},
        {"name": "bar", "symbol_type": "function"},
    ]
    assert result["file_metrics"] == {"loc": 7}
    assert result["violation_summary"] == {"count": 1}
    assert result["role_constraints"] == {"allowed": True}
    assert result["structural_signals"] == {"signals": []}

    assembler._build_file_metrics.assert_called_once()
    assembler._build_violation_summary.assert_called_once_with([finding])
    assembler._infer_role_constraints.assert_called_once_with(file_role=file_role)
    assembler._build_structural_signals.assert_called_once()





# ID: 01c97492-00ee-4d88-808d-0c0c949ac589
def test_FileContextAssembler():
    source_code = '''"""Module docstring."""

import os
from typing import Any


# ID: d394d74d-b5f0-4d23-9276-f7591c855c62
class Foo:
    # ID: a5104189-ba2a-43ba-8ba9-0609048843d4
    def bar(self):
        return 1


# ID: b81f8adc-bddf-405d-aaac-bd184136030a
def baz():
    return 2
'''

    finding = MagicMock()
    finding.rule_id = "R1"
    finding.severity = "high"
    finding.message = "some issue"

    file_role = MagicMock()
    file_role.role_id = "service"
    file_role.layer = "will"
    file_role.confidence = 0.9
    file_role.evidence = ["evidence1"]

    assembler = FileContextAssembler()
    result = assembler.assemble(
        file_path="src/will/x.py",
        source_code=source_code,
        findings=[finding],
        file_role=file_role,
    )

    assert result["file_path"] == "src/will/x.py"
    assert result["module_docstring"] == "Module docstring."
    assert result["file_role"]["role_id"] == "service"
    assert result["file_role"]["layer"] == "will"
    assert result["file_role"]["confidence"] == 0.9
    assert result["file_role"]["evidence"] == ["evidence1"]

    assert any(i["module"] == "os" for i in result["imports"])
    assert any(i["module"] == "typing" for i in result["imports"])

    symbol_names = {s["name"] for s in result["top_level_symbols"]}
    assert "Foo" in symbol_names
    assert "baz" in symbol_names

    metrics = result["file_metrics"]
    assert metrics["class_count"] == 1
    assert metrics["function_count"] == 1
    assert metrics["finding_count"] == 1
    assert metrics["distinct_rules"] == ["R1"]

    violations = result["violation_summary"]
    assert violations["rules"] == {"R1": 1}
    assert violations["severities"] == {"high": 1}
    assert "some issue" in violations["messages"]

    constraints = result["role_constraints"]
    assert any("layer" in c for c in constraints)
    assert any("service" in c.lower() for c in constraints)

    assert isinstance(result["structural_signals"], list)
