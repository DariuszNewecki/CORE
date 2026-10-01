from __future__ import annotations

import json
from pathlib import Path

from mind.logic.engines.ast_gate.checks.schema_conformance_checks import (
    SchemaConformanceChecks,
)


# ID: c0eb0125-0499-4f66-a304-3c46e937dc65
def test_SchemaConformanceChecks_extract_governed_classes(tmp_path: Path) -> None:
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(
        json.dumps({"governed_classes": ["Foo", "Bar", "Baz"]}),
        encoding="utf-8",
    )

    result = SchemaConformanceChecks.extract_governed_classes(contract_path)

    assert result == ["Foo", "Bar", "Baz"]


import ast


# ID: d2d711f7-8dc0-436d-91ba-66e906246747
def test_SchemaConformanceChecks_extract_class_annotated_fields() -> None:
    source = (
        "class Sample:\n"
        "    __tablename__: ClassVar[str] = 'sample'\n"
        "    name: str\n"
        "    count: int = 0\n"
        "    def method(self) -> None:\n"
        "        local: int = 5\n"
    )
    tree = ast.parse(source)
    class_node = tree.body[0]
    assert isinstance(class_node, ast.ClassDef)

    result = SchemaConformanceChecks.extract_class_annotated_fields(class_node)

    assert result == {"name": 3, "count": 4}




# ID: 9429209a-c816-46d6-ae5a-148d43ea4572
def test_SchemaConformanceChecks(tmp_path: Path) -> None:
    from mind.logic.engines.ast_gate.checks.schema_conformance_checks import (
        SchemaConformanceChecks,
    )

    # Happy path for _is_class_var
    classvar_ann = ast.parse("x: ClassVar[int]").body[0].annotation
    assert SchemaConformanceChecks._is_class_var(classvar_ann) is True
    typing_classvar_ann = ast.parse("x: typing.ClassVar[int]").body[0].annotation
    assert SchemaConformanceChecks._is_class_var(typing_classvar_ann) is True
    plain_ann = ast.parse("x: int").body[0].annotation
    assert SchemaConformanceChecks._is_class_var(plain_ann) is False

    # Happy path for extract_class_annotated_fields
    module = ast.parse(
        "class Foo:\n"
        "    a: int\n"
        "    b: str\n"
        "    __tablename__: ClassVar[str]\n"
        "    class Nested:\n"
        "        c: int\n"
    )
    foo_node = module.body[0]
    fields = SchemaConformanceChecks.extract_class_annotated_fields(foo_node)
    assert set(fields.keys()) == {"a", "b"}
    assert fields["a"] == 2
    assert fields["b"] == 3

    # Happy path for check_schema_contract_fields
    tree = ast.parse("class MyClass:\n    extra: int\n    name: str\n")
    contract_path = tmp_path / "my_contract.json"
    contract = {
        "governed_classes": ["MyClass"],
        "properties": {"name": {"type": "string"}},
        "required": ["name", "missing_req"],
    }
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    findings = SchemaConformanceChecks.check_schema_contract_fields(
        tree, contract_path, "src/my_file.py"
    )
    finding_text = "\n".join(findings)
    assert "extra" in finding_text
    assert "missing_req" in finding_text

    # Missing contract -> INFO finding
    missing_path = tmp_path / "absent_contract.json"
    info_findings = SchemaConformanceChecks.check_schema_contract_fields(
        tree, missing_path, "src/my_file.py"
    )
    assert len(info_findings) == 1
    assert "[INFO]" in info_findings[0]

    # Happy path for extract_governed_classes
    assert SchemaConformanceChecks.extract_governed_classes(contract_path) == [
        "MyClass"
    ]
    assert SchemaConformanceChecks.extract_governed_classes(missing_path) == []

    # Invalid JSON degrades to []
    bad_path = tmp_path / "bad.json"
    bad_path.write_text("{not json", encoding="utf-8")
    assert SchemaConformanceChecks.extract_governed_classes(bad_path) == []
