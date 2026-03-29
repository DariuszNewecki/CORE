# src/shared/self_healing/remediation_interpretation/file_role_detector.py

from __future__ import annotations

import ast
from collections.abc import Iterable

from shared.self_healing.remediation_interpretation.models import (
    FileRole,
    NormalizedFinding,
)


# ID: 6c7a5f21-60b5-4f52-8d5e-bc1ef6e52c9a
class FileRoleDetector:
    """
    Deterministically infer a file's architectural role from path and source.

    This service is deliberately heuristic and deterministic:
    - no LLM
    - no file I/O
    - no repo crawling
    - no runtime imports of the target module

    It is intended to answer:
    "What kind of thing is this file architecturally?"

    Current outputs:
    - layer: mind / will / body / shared / unknown
    - role_id:
        - worker.sensor
        - worker.actor
        - worker
        - service
        - route
        - repository
        - model
        - cli
        - test
        - utility
        - unknown
    """

    # ID: 1f1e09f8-45d1-4874-8b73-4f1f02853f5f
    def detect(
        self,
        file_path: str,
        source_code: str,
        findings: list[NormalizedFinding] | None = None,
    ) -> FileRole:
        """
        Detect the file role using path-first and AST-assisted heuristics.
        """
        evidence: list[str] = []

        layer, layer_evidence, layer_confidence = self._detect_layer(file_path)
        evidence.extend(layer_evidence)

        tree = self._parse_ast(source_code)
        ast_evidence: list[str] = []

        path_role, path_role_score, path_role_evidence = self._detect_role_from_path(
            file_path
        )
        evidence.extend(path_role_evidence)

        (
            source_role,
            source_role_score,
            source_role_evidence,
        ) = self._detect_role_from_ast(tree)
        ast_evidence.extend(source_role_evidence)

        (
            finding_role,
            finding_role_score,
            finding_role_evidence,
        ) = self._detect_role_from_findings(findings or [])
        evidence.extend(finding_role_evidence)

        if ast_evidence:
            evidence.extend(ast_evidence)

        role_id, role_confidence, role_evidence = self._merge_role_signals(
            path_role=path_role,
            path_role_score=path_role_score,
            source_role=source_role,
            source_role_score=source_role_score,
            finding_role=finding_role,
            finding_role_score=finding_role_score,
        )
        evidence.extend(role_evidence)

        confidence = self._combine_confidence(layer_confidence, role_confidence)

        return FileRole(
            role_id=role_id,
            layer=layer,
            confidence=confidence,
            evidence=self._dedupe_preserve_order(evidence),
        )

    # ------------------------------------------------------------------
    # Layer detection
    # ------------------------------------------------------------------

    # ID: a585a240-b3e0-450f-a4cf-9d761fcf4514
    def _detect_layer(self, file_path: str) -> tuple[str, list[str], float]:
        """Infer constitutional layer from path."""
        normalized = file_path.replace("\\", "/").strip("/")
        evidence: list[str] = []

        if "/src/mind/" in f"/{normalized}/" or normalized.startswith("src/mind/"):
            evidence.append("Path indicates layer 'mind'.")
            return "mind", evidence, 0.98

        if "/src/will/" in f"/{normalized}/" or normalized.startswith("src/will/"):
            evidence.append("Path indicates layer 'will'.")
            return "will", evidence, 0.98

        if "/src/body/" in f"/{normalized}/" or normalized.startswith("src/body/"):
            evidence.append("Path indicates layer 'body'.")
            return "body", evidence, 0.98

        if "/src/shared/" in f"/{normalized}/" or normalized.startswith("src/shared/"):
            evidence.append("Path indicates layer 'shared'.")
            return "shared", evidence, 0.98

        if normalized.startswith("tests/") or "/tests/" in f"/{normalized}/":
            evidence.append("Path indicates test code outside constitutional layers.")
            return "unknown", evidence, 0.75

        evidence.append(
            "No constitutional layer could be inferred confidently from path."
        )
        return "unknown", evidence, 0.40

    # ------------------------------------------------------------------
    # Role detection
    # ------------------------------------------------------------------

    # ID: c7f28094-1879-4a67-b337-4db7c5cd68f6
    def _detect_role_from_path(self, file_path: str) -> tuple[str, float, list[str]]:
        """Infer role from naming and directory conventions."""
        normalized = file_path.replace("\\", "/").strip("/")
        evidence: list[str] = []

        lower_name = normalized.rsplit("/", 1)[-1].lower()

        if normalized.startswith("tests/") or "/tests/" in f"/{normalized}/":
            evidence.append("Path indicates test file.")
            return "test", 0.98, evidence

        if "/workers/" in f"/{normalized}/" or lower_name.endswith("_worker.py"):
            evidence.append("Path indicates worker.")
            return "worker", 0.80, evidence

        if "/services/" in f"/{normalized}/" or lower_name.endswith("_service.py"):
            evidence.append("Path indicates service.")
            return "service", 0.86, evidence

        if "/routes/" in f"/{normalized}/" or lower_name == "routes.py":
            evidence.append("Path indicates route/controller module.")
            return "route", 0.92, evidence

        if "/repositories/" in f"/{normalized}/" or lower_name.endswith(
            "_repository.py"
        ):
            evidence.append("Path indicates repository.")
            return "repository", 0.90, evidence

        if "/models/" in f"/{normalized}/" or lower_name == "models.py":
            evidence.append("Path indicates model module.")
            return "model", 0.88, evidence

        if "/cli/" in f"/{normalized}/" or lower_name in {"cli.py", "main.py"}:
            evidence.append("Path indicates CLI module.")
            return "cli", 0.85, evidence

        if lower_name.startswith("test_") or lower_name.endswith("_test.py"):
            evidence.append("Filename indicates test file.")
            return "test", 0.95, evidence

        evidence.append("Path did not yield a strong role signal.")
        return "unknown", 0.35, evidence

    # ID: 95daeeff-f9cf-4c84-bdcc-2ae3a24e6941
    def _detect_role_from_ast(
        self, tree: ast.AST | None
    ) -> tuple[str, float, list[str]]:
        """Infer role from parsed syntax structure."""
        if tree is None:
            return (
                "unknown",
                0.20,
                ["AST parsing unavailable; source-based role detection degraded."],
            )

        classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]
        functions = [
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        evidence: list[str] = []

        worker_classification = self._classify_worker_role(classes)
        if worker_classification is not None:
            role_id, score, worker_evidence = worker_classification
            evidence.extend(worker_evidence)
            return role_id, score, evidence

        if self._has_route_decorators(tree):
            evidence.append("Detected route decorators in module.")
            return "route", 0.95, evidence

        if self._looks_like_repository(classes, functions):
            evidence.append("Detected repository-like data access patterns.")
            return "repository", 0.82, evidence

        if self._looks_like_service(classes, functions):
            evidence.append("Detected service-like orchestration patterns.")
            return "service", 0.78, evidence

        if self._looks_like_model_module(classes):
            evidence.append("Detected model-heavy module structure.")
            return "model", 0.76, evidence

        if self._looks_like_cli(tree, functions):
            evidence.append("Detected CLI-style command entry patterns.")
            return "cli", 0.80, evidence

        if self._looks_like_utility_module(classes, functions):
            evidence.append("Detected utility-style module with stateless helpers.")
            return "utility", 0.65, evidence

        evidence.append("AST did not yield a strong role signal.")
        return "unknown", 0.30, evidence

    # ID: 8af3f93c-07f9-4454-a9f5-c5c70d8debf6
    def _detect_role_from_findings(
        self,
        findings: list[NormalizedFinding],
    ) -> tuple[str, float, list[str]]:
        """
        Infer limited role hints from rule IDs or messages.

        This is intentionally weak. Findings should refine interpretation,
        not dominate it.
        """
        evidence: list[str] = []
        rule_ids = {item.rule_id for item in findings}

        if any("route" in rule_id for rule_id in rule_ids):
            evidence.append("Findings reference route-related rules.")
            return "route", 0.40, evidence

        if any("repository" in rule_id for rule_id in rule_ids):
            evidence.append("Findings reference repository-related rules.")
            return "repository", 0.40, evidence

        if any("worker" in rule_id for rule_id in rule_ids):
            evidence.append("Findings reference worker-related rules.")
            return "worker", 0.40, evidence

        return "unknown", 0.10, evidence

    # ------------------------------------------------------------------
    # AST helpers
    # ------------------------------------------------------------------

    # ID: 8ad2e3e1-1f4e-48cf-bf33-f05e8ef2ae4b
    def _parse_ast(self, source_code: str) -> ast.AST | None:
        """Parse Python source into AST, returning None on failure."""
        try:
            return ast.parse(source_code)
        except SyntaxError:
            return None

    # ID: 7b1d7bdf-1134-4af9-bf84-5f0f51220a57
    def _classify_worker_role(
        self,
        classes: list[ast.ClassDef],
    ) -> tuple[str, float, list[str]] | None:
        """Detect worker class and attempt sensor/actor specialization."""
        for class_node in classes:
            base_names = self._get_base_names(class_node)
            class_name = class_node.name.lower()

            if "Worker" in base_names or class_name.endswith("worker"):
                evidence = [
                    f"Class '{class_node.name}' appears to inherit Worker semantics."
                ]

                docstring = ast.get_docstring(class_node) or ""
                doc_l = docstring.lower()

                if self._looks_like_sensor_worker(doc_l, class_name):
                    evidence.append("Docstring or class name suggests sensing role.")
                    return "worker.sensor", 0.97, evidence

                if self._looks_like_actor_worker(doc_l, class_name):
                    evidence.append("Docstring or class name suggests acting role.")
                    return "worker.actor", 0.97, evidence

                evidence.append("Worker detected but subtype is unclear.")
                return "worker", 0.82, evidence

        return None

    # ID: 45c2d93e-c4fc-4a24-a45b-e7180f8f7e81
    def _looks_like_sensor_worker(self, doc_l: str, class_name: str) -> bool:
        """Return True if evidence suggests a sensing worker."""
        if "sensing worker" in doc_l:
            return True
        if "sensor" in class_name:
            return True
        return "responsibility: run" in doc_l and "post" in doc_l

    # ID: f9ac560d-9d3f-4747-ac5f-9dcbf05d39b2
    def _looks_like_actor_worker(self, doc_l: str, class_name: str) -> bool:
        """Return True if evidence suggests an acting worker."""
        if "acting worker" in doc_l:
            return True
        if any(term in class_name for term in {"remediator", "executor", "applier"}):
            return True
        return any(term in doc_l for term in {"apply", "crate", "commit"})

    # ID: 5601d513-24d8-4bc0-8610-4a18a4df5743
    def _has_route_decorators(self, tree: ast.AST) -> bool:
        """Return True if common route decorators are present."""
        route_names = {"get", "post", "put", "patch", "delete", "router"}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for decorator in node.decorator_list:
                    name = self._decorator_name(decorator)
                    if not name:
                        continue
                    parts = name.split(".")
                    if any(part in route_names for part in parts):
                        return True
        return False

    # ID: 3bd3ca07-0cf7-49f5-9cc7-a3088cb74944
    def _looks_like_repository(
        self,
        classes: list[ast.ClassDef],
        functions: list[ast.FunctionDef | ast.AsyncFunctionDef],
    ) -> bool:
        """Heuristic for repository/data access modules."""
        if any("repository" in item.name.lower() for item in classes):
            return True

        db_terms = {"session", "db", "execute", "query", "commit", "select", "insert"}
        return self._functions_reference_names(functions, db_terms, threshold=2)

    # ID: b0d87414-3f37-4b4a-9a56-a97d8de8ec05
    def _looks_like_service(
        self,
        classes: list[ast.ClassDef],
        functions: list[ast.FunctionDef | ast.AsyncFunctionDef],
    ) -> bool:
        """Heuristic for service/orchestration modules."""
        if any("service" in item.name.lower() for item in classes):
            return True

        orchestration_terms = {
            "execute",
            "build",
            "process",
            "validate",
            "apply",
            "dispatch",
            "assemble",
        }
        return self._functions_reference_names(
            functions,
            orchestration_terms,
            threshold=3,
        )

    # ID: 6090840c-a81c-43d5-b52b-c285a4a9ef6f
    def _looks_like_model_module(self, classes: list[ast.ClassDef]) -> bool:
        """Heuristic for model/dataclass/schema heavy modules."""
        for class_node in classes:
            base_names = self._get_base_names(class_node)
            decorator_names = {
                self._decorator_name(item) for item in class_node.decorator_list
            }
            if "BaseModel" in base_names or "DeclarativeBase" in base_names:
                return True
            if "dataclass" in decorator_names:
                return True
        return False

    # ID: b107112d-2049-42b9-bce5-6c6f8b74146b
    def _looks_like_cli(
        self,
        tree: ast.AST,
        functions: list[ast.FunctionDef | ast.AsyncFunctionDef],
    ) -> bool:
        """Heuristic for CLI modules."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = self._call_name(node)
                if name and ("typer" in name.lower() or "argparse" in name.lower()):
                    return True

        return any(item.name.lower() == "main" for item in functions)

    # ID: 68041663-f155-42f1-8638-cc0232f785f2
    def _looks_like_utility_module(
        self,
        classes: list[ast.ClassDef],
        functions: list[ast.FunctionDef | ast.AsyncFunctionDef],
    ) -> bool:
        """Heuristic for helper/utility modules."""
        if classes:
            return False
        return len(functions) >= 2

    # ID: 0c8b93e0-12be-4ca7-82b8-c08d2c43d513
    def _functions_reference_names(
        self,
        functions: list[ast.FunctionDef | ast.AsyncFunctionDef],
        target_names: set[str],
        threshold: int,
    ) -> bool:
        """Return True if enough target names appear in function bodies."""
        matched: set[str] = set()

        for function_node in functions:
            for node in ast.walk(function_node):
                if isinstance(node, ast.Name) and node.id.lower() in target_names:
                    matched.add(node.id.lower())
                elif (
                    isinstance(node, ast.Attribute)
                    and node.attr.lower() in target_names
                ):
                    matched.add(node.attr.lower())

            if len(matched) >= threshold:
                return True

        return False

    # ID: 3bfb78bf-6400-4669-82d1-5a0c119ac1a1
    def _get_base_names(self, class_node: ast.ClassDef) -> set[str]:
        """Extract simple base class names from a class definition."""
        names: set[str] = set()
        for base in class_node.bases:
            if isinstance(base, ast.Name):
                names.add(base.id)
            elif isinstance(base, ast.Attribute):
                names.add(base.attr)
        return names

    # ID: ef4663c0-d24a-4eed-9c5b-63a2d861fca8
    def _decorator_name(self, node: ast.expr) -> str:
        """Render best-effort decorator name."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parts: list[str] = []
            current: ast.expr | None = node
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            return ".".join(reversed(parts))
        if isinstance(node, ast.Call):
            return self._decorator_name(node.func)
        return ""

    # ID: 7a86d818-4e42-48f9-a7b7-44fd27cc8101
    def _call_name(self, node: ast.Call) -> str:
        """Render best-effort callable name."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        if isinstance(node.func, ast.Attribute):
            return self._decorator_name(node.func)
        return ""

    # ------------------------------------------------------------------
    # Signal merge
    # ------------------------------------------------------------------

    # ID: 3b46f856-1ff2-4640-885d-e39b35b2de09
    def _merge_role_signals(
        self,
        path_role: str,
        path_role_score: float,
        source_role: str,
        source_role_score: float,
        finding_role: str,
        finding_role_score: float,
    ) -> tuple[str, float, list[str]]:
        """
        Merge role signals conservatively.

        Priority:
        1. strong AST/source role
        2. strong path role
        3. finding hint if it reinforces something
        """
        evidence: list[str] = []

        if source_role != "unknown" and source_role_score >= 0.90:
            evidence.append(f"Selected role '{source_role}' from strong AST evidence.")
            return source_role, source_role_score, evidence

        if (
            path_role != "unknown"
            and source_role != "unknown"
            and self._roles_compatible(path_role, source_role)
        ):
            merged_score = min(0.99, max(path_role_score, source_role_score) + 0.08)
            evidence.append(
                f"Path role '{path_role}' and AST role '{source_role}' are compatible."
            )
            return (
                self._prefer_more_specific_role(path_role, source_role),
                merged_score,
                evidence,
            )

        if path_role != "unknown" and path_role_score >= 0.88:
            evidence.append(f"Selected role '{path_role}' from strong path evidence.")
            return path_role, path_role_score, evidence

        if source_role != "unknown":
            evidence.append(f"Selected role '{source_role}' from AST evidence.")
            return source_role, source_role_score, evidence

        if path_role != "unknown":
            evidence.append(f"Selected role '{path_role}' from path evidence.")
            return path_role, path_role_score, evidence

        if finding_role != "unknown":
            evidence.append(f"Selected weak role hint '{finding_role}' from findings.")
            return finding_role, finding_role_score, evidence

        evidence.append("No strong role signal found; defaulting to 'unknown'.")
        return "unknown", 0.25, evidence

    # ID: 6d6b4c69-4ebe-4547-95b6-9bb4d78f62d9
    def _roles_compatible(self, left: str, right: str) -> bool:
        """Check whether two role signals are compatible."""
        if left == right:
            return True
        compatible_pairs = {
            ("worker", "worker.sensor"),
            ("worker", "worker.actor"),
            ("worker.sensor", "worker"),
            ("worker.actor", "worker"),
        }
        return (left, right) in compatible_pairs

    # ID: 356bd3ed-d3e7-4b11-a48d-44be07867734
    def _prefer_more_specific_role(self, left: str, right: str) -> str:
        """Prefer more specific role between two compatible roles."""
        specificity_order = {
            "worker.sensor": 3,
            "worker.actor": 3,
            "worker": 2,
            "route": 2,
            "repository": 2,
            "service": 2,
            "model": 2,
            "cli": 2,
            "test": 2,
            "utility": 1,
            "unknown": 0,
        }
        if specificity_order.get(left, 0) >= specificity_order.get(right, 0):
            return left
        return right

    # ID: 03d8e95a-a28f-4b7d-8fc2-55eed2b98d0c
    def _combine_confidence(
        self,
        layer_confidence: float,
        role_confidence: float,
    ) -> float:
        """Combine layer and role confidence into a bounded result."""
        confidence = (layer_confidence * 0.45) + (role_confidence * 0.55)
        return round(max(0.0, min(1.0, confidence)), 3)

    # ID: 4167da2e-4af6-4999-8a8a-48327766b423
    def _dedupe_preserve_order(self, items: Iterable[str]) -> list[str]:
        """Deduplicate evidence entries while preserving order."""
        seen: set[str] = set()
        output: list[str] = []
        for item in items:
            if item not in seen:
                seen.add(item)
                output.append(item)
        return output
