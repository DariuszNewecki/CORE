# src/mind/logic/engines/ast_gate/checks/schema_conformance_checks.py
"""Schema conformance checks for runtime data contracts (ADR-056 D6)."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from mind.logic.engines.ast_gate.base import ASTHelpers


# ID: 16e61dd9-9080-4e3f-8e26-3d5cf3267b37
class SchemaConformanceChecks:
    """Validate Python class field declarations against governing data contracts."""

    @staticmethod
    # ID: 5fd16fed-90b3-42f6-9bc8-cf7a9d3f6ea3
    def extract_class_annotated_fields(class_node: ast.ClassDef) -> dict[str, int]:
        """Return {field_name: lineno} for AnnAssign targets in the class body.

        Walks the immediate body of class_node only — nested class definitions
        and their fields are not visited.
        """
        fields: dict[str, int] = {}
        for stmt in class_node.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                fields[stmt.target.id] = ASTHelpers.lineno(stmt)
        return fields

    @staticmethod
    # ID: 081259ac-e022-4633-ade6-ea4a2039caf4
    def check_schema_contract_fields(
        tree: ast.AST, contract_path: Path, file_path: str
    ) -> list[str]:
        """Validate that classes named in the contract conform to its field set.

        Compares each governed class's annotated fields against the contract's
        `properties` (declared) and `required` lists. Reports both directions:
        fields present in the class but absent from properties, and required
        fields absent from the class.

        Missing-contract case returns a single INFO finding so callers can
        still distinguish "contract not yet authored" from "no violations" —
        the rule glob may target Wave 1 classes before their schemas land.
        """
        if not contract_path.exists():
            return [
                f"[INFO] {file_path}: contract '{contract_path.name}' not yet "
                f"authored — no enforcement"
            ]

        try:
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return [f"schema contract '{contract_path.name}' is not valid JSON"]

        governed = contract.get("governed_classes") or []
        if not governed:
            return []

        declared_props = set((contract.get("properties") or {}).keys())
        required_fields = set(contract.get("required") or [])

        class_nodes: dict[str, ast.ClassDef] = {
            node.name: node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        }

        findings: list[str] = []
        for class_name in governed:
            class_node = class_nodes.get(class_name)
            if class_node is None:
                continue

            actual_fields = SchemaConformanceChecks.extract_class_annotated_fields(
                class_node
            )
            actual_set = set(actual_fields.keys())

            for field_name in sorted(actual_set - declared_props):
                findings.append(
                    f"Line {actual_fields[field_name]}: class '{class_name}' "
                    f"field '{field_name}' not declared in contract "
                    f"'{contract_path.stem}'"
                )

            for field_name in sorted(required_fields - actual_set):
                findings.append(
                    f"Line {ASTHelpers.lineno(class_node)}: class '{class_name}' "
                    f"missing required field '{field_name}' from contract "
                    f"'{contract_path.stem}'"
                )

        return findings

    @staticmethod
    # ID: 02bf4618-ee21-4b6d-ba82-943f6b3a6574
    def extract_governed_classes(contract_path: Path) -> list[str]:
        """Return the contract's governed_classes list, or [] on any error.

        Tolerant helper for tooling and future checks: a missing file, invalid
        JSON, or missing/non-list governed_classes key all degrade to [].
        check_schema_contract_fields has its own error paths and does not
        delegate here.
        """
        if not contract_path.exists():
            return []
        try:
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        value = contract.get("governed_classes")
        return value if isinstance(value, list) else []
