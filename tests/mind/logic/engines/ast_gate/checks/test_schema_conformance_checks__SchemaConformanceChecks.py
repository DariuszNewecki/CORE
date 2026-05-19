"""Tests for SchemaConformanceChecks — ADR-056 D6 / issue #368.

Covers extract_class_annotated_fields' ClassVar-filtering behaviour and the
full check_schema_contract_fields path against a mixed-field fixture class.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

from mind.logic.engines.ast_gate.checks.schema_conformance_checks import (
    SchemaConformanceChecks,
)


def _parse_class(code: str, class_name: str = "Target") -> ast.ClassDef:
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node
    raise AssertionError(f"class {class_name} not found in fixture")


class TestExtractClassAnnotatedFieldsClassVarFiltering:
    def test_regular_annotated_field_extracted(self):
        node = _parse_class("class Target:\n    x: int\n    y: str = 'a'\n")
        assert SchemaConformanceChecks.extract_class_annotated_fields(node) == {
            "x": 2,
            "y": 3,
        }

    def test_classvar_subscript_with_name_skipped(self):
        node = _parse_class(
            "class Target:\n"
            "    x: int\n"
            "    __tablename__: ClassVar[str] = 'tbl'\n"
        )
        assert SchemaConformanceChecks.extract_class_annotated_fields(node) == {
            "x": 2,
        }

    def test_classvar_subscript_with_attribute_skipped(self):
        node = _parse_class(
            "class Target:\n"
            "    x: int\n"
            "    __table_args__: typing.ClassVar[dict] = {}\n"
        )
        assert SchemaConformanceChecks.extract_class_annotated_fields(node) == {
            "x": 2,
        }

    def test_bare_classvar_name_skipped(self):
        node = _parse_class(
            "class Target:\n    x: int\n    flag: ClassVar = True\n"
        )
        assert SchemaConformanceChecks.extract_class_annotated_fields(node) == {
            "x": 2,
        }

    def test_bare_typing_classvar_attribute_skipped(self):
        node = _parse_class(
            "class Target:\n    x: int\n    flag: typing.ClassVar = True\n"
        )
        assert SchemaConformanceChecks.extract_class_annotated_fields(node) == {
            "x": 2,
        }

    def test_subscript_non_classvar_still_extracted(self):
        node = _parse_class(
            "class Target:\n    items: list[int] = []\n    pair: tuple[int, str] = (1, 'a')\n"
        )
        assert SchemaConformanceChecks.extract_class_annotated_fields(node) == {
            "items": 2,
            "pair": 3,
        }

    def test_nested_class_fields_ignored(self):
        node = _parse_class(
            "class Target:\n"
            "    x: int\n"
            "    class Inner:\n"
            "        y: str\n"
        )
        assert SchemaConformanceChecks.extract_class_annotated_fields(node) == {
            "x": 2,
        }


class TestCheckSchemaContractFieldsWithClassVar:
    def test_classvar_fields_do_not_emit_undeclared_findings(self, tmp_path: Path):
        contract = {
            "$schema": "META/data_contract.schema.json",
            "kind": "data_contract",
            "metadata": {
                "id": "contracts.test",
                "title": "Test",
                "version": "1.0.0",
                "authority": "constitution",
                "status": "active",
            },
            "governed_classes": ["BlackboardEntry"],
            "required": ["worker_uuid", "subject"],
            "properties": {
                "worker_uuid": {"type": "string"},
                "subject": {"type": "string"},
            },
        }
        contract_path = tmp_path / "BlackboardEntry.json"
        contract_path.write_text(json.dumps(contract), encoding="utf-8")

        source = (
            "from typing import Any, ClassVar\n"
            "\n"
            "class BlackboardEntry:\n"
            "    __tablename__: ClassVar[str] = 'blackboard_entries'\n"
            "    __table_args__: ClassVar[dict[str, Any]] = {'schema': 'core'}\n"
            "    worker_uuid: str\n"
            "    subject: str\n"
        )
        tree = ast.parse(source)

        findings = SchemaConformanceChecks.check_schema_contract_fields(
            tree, contract_path, "src/shared/models/blackboard.py"
        )
        assert findings == []

    def test_missing_required_field_still_reported_when_classvar_present(
        self, tmp_path: Path
    ):
        contract = {
            "governed_classes": ["BlackboardEntry"],
            "required": ["worker_uuid", "subject", "payload"],
            "properties": {
                "worker_uuid": {"type": "string"},
                "subject": {"type": "string"},
                "payload": {"type": "object"},
            },
        }
        contract_path = tmp_path / "BlackboardEntry.json"
        contract_path.write_text(json.dumps(contract), encoding="utf-8")

        source = (
            "from typing import ClassVar\n"
            "\n"
            "class BlackboardEntry:\n"
            "    __tablename__: ClassVar[str] = 'blackboard_entries'\n"
            "    worker_uuid: str\n"
            "    subject: str\n"
        )
        tree = ast.parse(source)

        findings = SchemaConformanceChecks.check_schema_contract_fields(
            tree, contract_path, "src/shared/models/blackboard.py"
        )
        assert len(findings) == 1
        assert "missing required field 'payload'" in findings[0]
        assert "__tablename__" not in " ".join(findings)
