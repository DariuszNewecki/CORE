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
