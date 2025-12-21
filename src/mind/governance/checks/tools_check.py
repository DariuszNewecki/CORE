# src/mind/governance/checks/tools_check.py
# ID: model.mind.governance.checks.tools_check
"""
Constitutional check for Tool Definition rules.

Uses RuleEnforcementCheck template to verify:
- tools.explicit_return_contract
- tools.type_mapping_strictness

Ref: .intent/charter/standards/architecture/tool_definition_standard.json
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, ClassVar

from mind.governance.checks.rule_enforcement_check import RuleEnforcementCheck
from mind.governance.enforcement_methods import EnforcementMethod
from shared.logger import getLogger
from shared.models import AuditFinding


logger = getLogger(__name__)

TOOL_POLICY_FILE = Path(
    ".intent/charter/standards/architecture/tool_definition_standard.json"
)
TOOL_GENERATOR = Path("src/will/tools/tool_generator.py")


def _parse_module(path: Path, *, filename: str) -> ast.AST | None:
    try:
        content = path.read_text(encoding="utf-8")
        return ast.parse(content, filename=filename)
    except (SyntaxError, UnicodeDecodeError) as exc:
        logger.debug("Failed to parse %s: %s", filename, exc)
        return None
    except Exception as exc:
        logger.debug("Failed to read %s: %s", filename, exc)
        return None


def _find_function(tree: ast.AST, name: str) -> ast.FunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _node_text(node: ast.AST) -> str:
    # Keep resilient across Python versions; ast.unparse exists in 3.9+.
    if hasattr(ast, "unparse"):
        try:
            return ast.unparse(node)
        except Exception:
            return ""
    return ""


# ID: return-contract-enforcement
# ID: 6040f6d3-2067-476c-9b2b-418601321560
class ReturnContractEnforcement(EnforcementMethod):
    """
    Verifies that tool generation describes ActionResult schema (ok/data/error),
    not only a generic "string" return.
    """

    # ID: 108c08db-b15b-4d91-b4d0-832074e4d5b2
    def verify(self, context, rule_data: dict[str, Any]) -> list[AuditFinding]:
        findings: list[AuditFinding] = []

        rel_path = str(TOOL_GENERATOR).replace("\\", "/")
        tool_gen_path = context.repo_path / TOOL_GENERATOR
        if not tool_gen_path.exists():
            findings.append(
                self._create_finding(
                    "Tool generator missing: src/will/tools/tool_generator.py",
                    file_path=rel_path,
                )
            )
            return findings

        tree = _parse_module(tool_gen_path, filename=rel_path)
        if tree is None:
            # Parsing failures are surfaced elsewhere; keep this check deterministic.
            return findings

        fn = _find_function(tree, "generate_tool_definition")
        if fn is None:
            findings.append(
                self._create_finding(
                    "Tool generator missing generate_tool_definition function",
                    file_path=rel_path,
                )
            )
            return findings

        docstring = ast.get_docstring(fn) or ""
        body_text = _node_text(fn)

        # We keep detection conservative: require explicit mention of the contract
        # or clear presence of the keys being produced.
        has_contract_hint = (
            "ActionResult" in docstring
            or "{ok" in docstring.replace(" ", "").lower()
            or ("ok" in docstring.lower() and "data" in docstring.lower())
        )

        has_keys_in_code = ('"ok"' in body_text or "'ok'" in body_text) and (
            '"data"' in body_text or "'data'" in body_text
        )

        if not (has_contract_hint or has_keys_in_code):
            findings.append(
                self._create_finding(
                    "Tool generator does not describe ActionResult schema in returns - "
                    "LLMs need to know they receive {ok, data, error} structure",
                    file_path=rel_path,
                    line_number=getattr(fn, "lineno", 1),
                )
            )

        return findings


# ID: type-mapping-strictness-enforcement
# ID: 6b4d0b4a-40a5-42d0-bf62-937f28941e23
class TypeMappingStrictnessEnforcement(EnforcementMethod):
    """
    Verifies that python_type_to_json_type uses specific JSON Schema types (not generic "string").
    Requires mappings for: int->integer, float->number, bool->boolean at minimum.
    """

    # ID: 1332852f-b52d-4566-bbfc-d5c9a0ff7ede
    def verify(self, context, rule_data: dict[str, Any]) -> list[AuditFinding]:
        findings: list[AuditFinding] = []

        rel_path = str(TOOL_GENERATOR).replace("\\", "/")
        tool_gen_path = context.repo_path / TOOL_GENERATOR
        if not tool_gen_path.exists():
            findings.append(
                self._create_finding(
                    "Tool generator missing: src/will/tools/tool_generator.py",
                    file_path=rel_path,
                )
            )
            return findings

        tree = _parse_module(tool_gen_path, filename=rel_path)
        if tree is None:
            return findings

        fn = _find_function(tree, "python_type_to_json_type")
        if fn is None:
            findings.append(
                self._create_finding(
                    "Tool generator missing python_type_to_json_type function",
                    file_path=rel_path,
                )
            )
            return findings

        body_text = _node_text(fn)
        required = {
            "integer": ('"integer"' in body_text) or ("'integer'" in body_text),
            "number": ('"number"' in body_text) or ("'number'" in body_text),
            "boolean": ('"boolean"' in body_text) or ("'boolean'" in body_text),
        }
        missing = [k for k, ok in required.items() if not ok]

        if missing:
            findings.append(
                self._create_finding(
                    "Type mapping not strict enough - missing mappings for: "
                    f"{', '.join(missing)}. All Python primitives must map to specific JSON Schema types.",
                    file_path=rel_path,
                    line_number=getattr(fn, "lineno", 1),
                )
            )

        return findings


# ID: tools-check
# ID: 64e5b1a0-ebf7-43d3-9e40-66b8395c784b
class ToolsCheck(RuleEnforcementCheck):
    """
    Verifies that Tool Definition standards are enforced.

    Ref: .intent/charter/standards/architecture/tool_definition_standard.json
    """

    policy_rule_ids: ClassVar[list[str]] = [
        "tools.explicit_return_contract",
        "tools.type_mapping_strictness",
    ]
    id: ClassVar[str] = "tools"

    policy_file: ClassVar[Path] = TOOL_POLICY_FILE

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        ReturnContractEnforcement(rule_id="tools.explicit_return_contract"),
        TypeMappingStrictnessEnforcement(rule_id="tools.type_mapping_strictness"),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
