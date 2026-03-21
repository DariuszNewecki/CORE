# src/will/self_healing/remediation_interpretation/file_context_assembler.py

from __future__ import annotations

import ast
from typing import Any

from will.self_healing.remediation_interpretation.models import (
    FileRole,
    NormalizedFinding,
)


# ID: 4db6b5c0-8e47-4d07-a56f-4f854d6fc1d1
class FileContextAssembler:
    """
    Deterministically assemble architectural context for a violating file.

    This service is intentionally bounded and deterministic:
    - no LLM
    - no Qdrant
    - no repo crawling
    - no direct file reads

    It turns the current file, its normalized findings, and its already-known
    role into a concise context package that later services can use for:
    - responsibility extraction
    - strategy selection
    - ReasoningBrief construction

    The goal is not to build "all possible context". The goal is to build
    enough governed context to support architectural interpretation before any
    proposal generation occurs.
    """

    # ID: 4a9d9b7d-5f28-460b-a2cc-c52d3c7db95d
    def assemble(
        self,
        file_path: str,
        source_code: str,
        findings: list[NormalizedFinding],
        file_role: FileRole,
    ) -> dict[str, Any]:
        """
        Build a bounded deterministic file-context package.
        """
        tree = self._parse_ast(source_code)
        imports = self._extract_imports(tree)
        top_level_symbols = self._extract_top_level_symbols(tree)
        docstring = self._extract_module_docstring(tree)

        class_names = [
            item["name"] for item in top_level_symbols if item["symbol_type"] == "class"
        ]
        function_names = [
            item["name"]
            for item in top_level_symbols
            if item["symbol_type"] in {"function", "async_function"}
        ]

        file_metrics = self._build_file_metrics(
            source_code=source_code,
            imports=imports,
            class_names=class_names,
            function_names=function_names,
            findings=findings,
        )

        violation_summary = self._build_violation_summary(findings)
        role_constraints = self._infer_role_constraints(file_role=file_role)
        structural_signals = self._build_structural_signals(
            file_path=file_path,
            file_role=file_role,
            imports=imports,
            class_names=class_names,
            function_names=function_names,
            docstring=docstring,
        )

        return {
            "file_path": file_path,
            "file_role": {
                "role_id": file_role.role_id,
                "layer": file_role.layer,
                "confidence": file_role.confidence,
                "evidence": list(file_role.evidence),
            },
            "module_docstring": docstring,
            "imports": imports,
            "top_level_symbols": top_level_symbols,
            "file_metrics": file_metrics,
            "violation_summary": violation_summary,
            "role_constraints": role_constraints,
            "structural_signals": structural_signals,
        }

    # ------------------------------------------------------------------
    # AST parsing
    # ------------------------------------------------------------------

    # ID: d0f6bb94-7d45-4c24-bad1-cae8ca87a4b8
    def _parse_ast(self, source_code: str) -> ast.AST | None:
        """Parse source code into AST, returning None on syntax failure."""
        try:
            return ast.parse(source_code)
        except SyntaxError:
            return None

    # ID: d66b40c4-3d9f-4280-b4d8-1e632cab08ab
    def _extract_module_docstring(self, tree: ast.AST | None) -> str:
        """Extract module docstring if available."""
        if tree is None:
            return ""
        return (ast.get_docstring(tree) or "").strip()

    # ID: 5ab8f0c7-a2ec-45b4-8d89-d53727fca7a3
    def _extract_imports(self, tree: ast.AST | None) -> list[dict[str, Any]]:
        """
        Extract import information from the module.

        Output format is intentionally explicit and JSON-serializable.
        """
        if tree is None:
            return []

        imports: list[dict[str, Any]] = []

        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(
                        {
                            "kind": "import",
                            "module": alias.name,
                            "name": alias.name,
                            "alias": alias.asname,
                        }
                    )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append(
                        {
                            "kind": "from",
                            "module": module,
                            "name": alias.name,
                            "alias": alias.asname,
                            "level": node.level,
                        }
                    )

        return imports

    # ID: 265fbbef-8452-48fb-b78a-c0e8d4431328
    def _extract_top_level_symbols(
        self,
        tree: ast.AST | None,
    ) -> list[dict[str, Any]]:
        """
        Extract top-level classes and functions with lightweight metadata.
        """
        if tree is None:
            return []

        symbols: list[dict[str, Any]] = []

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                symbols.append(
                    {
                        "name": node.name,
                        "symbol_type": "class",
                        "line_start": getattr(node, "lineno", None),
                        "line_end": getattr(node, "end_lineno", None),
                        "bases": sorted(self._get_base_names(node)),
                        "method_count": sum(
                            1
                            for child in node.body
                            if isinstance(
                                child,
                                (
                                    ast.FunctionDef,
                                    ast.AsyncFunctionDef,
                                ),
                            )
                        ),
                    }
                )
            elif isinstance(node, ast.FunctionDef):
                symbols.append(
                    {
                        "name": node.name,
                        "symbol_type": "function",
                        "line_start": getattr(node, "lineno", None),
                        "line_end": getattr(node, "end_lineno", None),
                        "is_async": False,
                    }
                )
            elif isinstance(node, ast.AsyncFunctionDef):
                symbols.append(
                    {
                        "name": node.name,
                        "symbol_type": "async_function",
                        "line_start": getattr(node, "lineno", None),
                        "line_end": getattr(node, "end_lineno", None),
                        "is_async": True,
                    }
                )

        return symbols

    # ------------------------------------------------------------------
    # Metrics and summaries
    # ------------------------------------------------------------------

    # ID: c3516cc8-c909-4f85-bde7-2de8fdb064e3
    def _build_file_metrics(
        self,
        source_code: str,
        imports: list[dict[str, Any]],
        class_names: list[str],
        function_names: list[str],
        findings: list[NormalizedFinding],
    ) -> dict[str, Any]:
        """Build lightweight file metrics for planning."""
        lines = source_code.splitlines()
        non_empty_lines = [line for line in lines if line.strip()]
        finding_rules = sorted({item.rule_id for item in findings})

        return {
            "line_count": len(lines),
            "non_empty_line_count": len(non_empty_lines),
            "import_count": len(imports),
            "class_count": len(class_names),
            "function_count": len(function_names),
            "finding_count": len(findings),
            "distinct_rule_count": len(finding_rules),
            "distinct_rules": finding_rules,
        }

    # ID: 36725221-1ba8-4f18-8cdf-5f112ca4d5cb
    def _build_violation_summary(
        self,
        findings: list[NormalizedFinding],
    ) -> dict[str, Any]:
        """Summarize findings in deterministic grouped form."""
        rules: dict[str, int] = {}
        severities: dict[str, int] = {}
        messages: list[str] = []

        for item in findings:
            rules[item.rule_id] = rules.get(item.rule_id, 0) + 1
            severities[item.severity] = severities.get(item.severity, 0) + 1
            if item.message and item.message not in messages:
                messages.append(item.message)

        return {
            "rules": dict(sorted(rules.items())),
            "severities": dict(sorted(severities.items())),
            "messages": messages,
        }

    # ID: e1fca64f-3403-48f9-bfed-7255432f6952
    def _infer_role_constraints(self, file_role: FileRole) -> list[str]:
        """
        Infer architectural constraints from the detected role.

        These are not rule-engine outputs. They are deterministic planning
        guardrails for later strategy selection.
        """
        constraints: list[str] = []

        if file_role.layer != "unknown":
            constraints.append(
                f"Preserve constitutional layer placement within "
                f"'{file_role.layer}'."
            )

        if file_role.role_id == "worker.sensor":
            constraints.append(
                "Preserve sensing-only character; do not introduce acting behavior."
            )
            constraints.append(
                "Do not introduce mutation or proposal-generation " "responsibilities."
            )
        elif file_role.role_id == "worker.actor":
            constraints.append(
                "Preserve acting responsibility while reducing local complexity."
            )
            constraints.append("Do not move orchestration into sensing surfaces.")
        elif file_role.role_id == "service":
            constraints.append(
                "Preserve service orchestration role; avoid UI or route leakage."
            )
        elif file_role.role_id == "route":
            constraints.append(
                "Preserve routing/controller role; avoid heavy business logic "
                "accumulation."
            )
        elif file_role.role_id == "repository":
            constraints.append("Preserve repository/data-access boundary.")
        elif file_role.role_id == "model":
            constraints.append(
                "Preserve declarative model focus; avoid orchestration creep."
            )
        elif file_role.role_id == "cli":
            constraints.append(
                "Preserve command-entry role; avoid hidden domain logic "
                "accumulation."
            )

        return constraints

    # ID: c95d963d-1c66-44f1-bd53-d9f93d904217
    def _build_structural_signals(
        self,
        file_path: str,
        file_role: FileRole,
        imports: list[dict[str, Any]],
        class_names: list[str],
        function_names: list[str],
        docstring: str,
    ) -> list[str]:
        """Build explicit structural signals useful for later interpretation."""
        signals: list[str] = []

        if docstring:
            signals.append("Module defines an explicit docstring contract.")

        if class_names and function_names:
            signals.append("Module mixes top-level classes and top-level functions.")

        if len(class_names) > 1:
            signals.append("Module contains multiple top-level classes.")

        if len(function_names) >= 5:
            signals.append("Module exposes many top-level functions.")

        imported_modules = {
            item.get("module", "") for item in imports if item.get("module")
        }
        if len(imported_modules) >= 8:
            signals.append("Module imports from many distinct modules.")

        normalized_path = file_path.replace("\\", "/").strip("/")
        if "/workers/" in f"/{normalized_path}/" and file_role.role_id.startswith(
            "worker"
        ):
            signals.append("Worker file path and worker role are aligned.")

        if file_role.layer == "will" and file_role.role_id.startswith("worker"):
            signals.append(
                "This module appears to participate in governance or "
                "orchestration flow."
            )

        if file_role.layer == "body" and file_role.role_id.startswith("worker"):
            signals.append(
                "This module appears to participate in acting/execution flow."
            )

        return signals

    # ------------------------------------------------------------------
    # AST utilities
    # ------------------------------------------------------------------

    # ID: cdc55f75-24e8-4f78-8d42-f98c0aab345e
    def _get_base_names(self, class_node: ast.ClassDef) -> set[str]:
        """Extract simple base class names from class definition."""
        names: set[str] = set()

        for base in class_node.bases:
            if isinstance(base, ast.Name):
                names.add(base.id)
            elif isinstance(base, ast.Attribute):
                names.add(base.attr)

        return names
