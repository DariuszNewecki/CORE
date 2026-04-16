# src/shared/infrastructure/context/builder.py

"""
ContextBuilder - doctrine-aligned context packet assembly.

Build contract:
    request -> providers -> packet -> redactor -> validator -> serializer
"""

from __future__ import annotations

import ast
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from shared.config import settings
from shared.infrastructure.intent.intent_repository import get_intent_repository
from shared.infrastructure.knowledge.knowledge_service import KnowledgeService
from shared.logger import getLogger

from .models import ContextBuildRequest
from .serializers import ContextSerializer


if TYPE_CHECKING:
    from shared.infrastructure.context.limb_workspace import LimbWorkspace

    from .providers.ast import ASTProvider
    from .providers.db import DBProvider
    from .providers.vectors import VectorProvider

logger = getLogger(__name__)


LAYER_POLICY_IDS: dict[str, list[str]] = {
    "mind": ["layer_separation", "privileged_boundaries"],
    "body": ["layer_separation", "privileged_boundaries"],
    "will": ["layer_separation", "privileged_boundaries", "autonomy"],
    "shared": ["layer_separation"],
}

_LAYER_PATH_PREFIXES: tuple[tuple[str, str], ...] = (
    ("src/mind/", "mind"),
    ("src/body/", "body"),
    ("src/will/", "will"),
    ("src/shared/", "shared"),
)

_LAYER_CONSTRAINT_WARNING = (
    "All blocking rules listed above are enforced regardless of role inference "
    "confidence. Cross-layer imports are a constitutional violation detectable "
    "from path alone."
)


# ID: 3a7f04c1-6d2b-4e89-ae12-5d9b3a8e1c42
def _derive_layer_from_path(path: str) -> str | None:
    for prefix, layer in _LAYER_PATH_PREFIXES:
        if path.startswith(prefix):
            return layer
    return None


# ID: ba433808-889c-4dc7-b247-5b0cfdc46bfc
class ScopeTracker(ast.NodeVisitor):
    """AST visitor that collects symbol metadata and source slices."""

    def __init__(self, source: str) -> None:
        self.source = source
        self.stack: list[str] = []
        self.symbols: list[dict[str, Any]] = []

    # ID: 3dc8f21e-b43f-4d87-bf00-95c07dc3724f
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._add_symbol(node)
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    # ID: 058b0ed9-0be1-494e-9e65-5f5d2764253a
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._add_symbol(node)
        self.generic_visit(node)

    # ID: e9bbdd0e-6f26-46ab-804d-168f504968a8
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._add_symbol(node)
        self.generic_visit(node)

    def _add_symbol(self, node: Any) -> None:
        qualname = f"{'.'.join(self.stack)}.{node.name}" if self.stack else node.name
        try:
            lines = self.source.splitlines()
            end = getattr(node, "end_lineno", node.lineno) or node.lineno
            code = "\n".join(lines[node.lineno - 1 : end])
            sig = code.split("\n")[0]
        except Exception as e:
            logger.debug("Symbol extraction failed for %s: %s", node.name, e)
            sig = f"def {node.name}(...):"
            code = "# extraction failed"

        self.symbols.append(
            {
                "name": node.name,
                "qualname": qualname,
                "signature": sig,
                "code": code,
                "docstring": ast.get_docstring(node) or "",
            }
        )


# ID: abd1a2cf-7a1c-4902-aea7-68573ef9599a
class ContextBuilder:
    """Assembles doctrine-aligned context packets."""

    def __init__(
        self,
        db_provider: DBProvider | None,
        vector_provider: VectorProvider | None,
        ast_provider: ASTProvider | None,
        config: dict[str, Any] | None,
        workspace: LimbWorkspace | None = None,
    ) -> None:
        self.db = db_provider
        self.vectors = vector_provider
        self.ast = ast_provider
        self.config = config or {}
        self.workspace = workspace
        self.intent = get_intent_repository()

    # ID: df6f0a5d-f792-45e3-917c-557ad15ae199
    async def build(self, request: ContextBuildRequest) -> dict[str, Any]:
        start = datetime.now(UTC)
        graph = await self._load_truth()
        selected_providers = self._select_providers(request)

        header = self._build_header(request)
        constitution = (
            self._build_constitution_context(request)
            if request.include_constitution
            else {}
        )
        policy = self._build_policy_context(request)
        constraints = self._build_constraints(request, constitution, policy)

        evidence: list[dict[str, Any]] = []
        if "ast" in selected_providers:
            evidence.extend(await self._gather_ast_evidence(request, graph))
        if "vectors" in selected_providers:
            evidence.extend(await self._gather_vector_evidence(request))
        if "db" in selected_providers:
            evidence.extend(await self._gather_db_evidence(request))

        evidence = self._finalize_evidence(evidence, request)

        runtime = self._build_runtime_context(request, selected_providers)

        provenance = {
            "cache_key": ContextSerializer.compute_cache_key(
                {
                    "goal": request.goal,
                    "trigger": request.trigger,
                    "phase": request.phase,
                    "workflow_id": request.workflow_id,
                    "stage_id": request.stage_id,
                    "target_files": list(request.target_files),
                    "target_symbols": list(request.target_symbols),
                    "target_paths": list(request.target_paths),
                    "include_constitution": request.include_constitution,
                    "include_policy": request.include_policy,
                    "include_symbols": request.include_symbols,
                    "include_vectors": request.include_vectors,
                    "include_runtime": request.include_runtime,
                }
            ),
            "providers": selected_providers,
            "build_stats": {
                "duration_ms": int((datetime.now(UTC) - start).total_seconds() * 1000),
                "evidence_total": len(evidence),
                "tokens_total": sum(item.get("tokens_est", 0) for item in evidence),
            },
        }

        return {
            "layer_constraints": self._build_layer_constraints(request),
            "header": header,
            "phase": request.phase,
            "constitution": constitution,
            "policy": policy,
            "constraints": constraints,
            "evidence": evidence,
            "runtime": runtime,
            "provenance": provenance,
        }

    def _build_layer_constraints(
        self,
        request: ContextBuildRequest,
    ) -> dict[str, Any]:
        empty: dict[str, Any] = {"layer": None, "rules": [], "warning": ""}

        if not request.target_files:
            return empty

        layer = _derive_layer_from_path(request.target_files[0])
        if layer is None:
            return empty

        policy_ids = LAYER_POLICY_IDS.get(layer)
        if not policy_ids:
            return empty

        try:
            candidate_rules = self.intent.find_rules(policy_ids=policy_ids)
        except Exception as e:
            logger.debug("Layer rule lookup failed for %s: %s", layer, e)
            return empty

        blocking_rules = [
            {
                "id": rule.get("id") or rule.get("rule_id") or "",
                "statement": rule.get("statement", ""),
                "enforcement": rule.get("enforcement", ""),
            }
            for rule in candidate_rules
            if str(rule.get("authority", "")).lower() == "constitution"
        ]

        if not blocking_rules:
            return {"layer": layer, "rules": [], "warning": ""}

        return {
            "layer": layer,
            "rules": blocking_rules,
            "warning": _LAYER_CONSTRAINT_WARNING,
        }

    async def _load_truth(self) -> dict[str, Any]:
        try:
            return await KnowledgeService(
                settings.REPO_PATH,
                workspace=self.workspace,
            ).get_graph()
        except Exception as e:
            logger.warning("Knowledge graph unavailable: %s", e)
            return {"symbols": {}}

    def _select_providers(self, request: ContextBuildRequest) -> list[str]:
        selected: list[str] = []

        ast_needed = bool(
            request.include_symbols
            or request.target_files
            or request.target_paths
            or request.target_symbols
            or self.workspace is not None
        )
        if ast_needed:
            selected.append("ast")

        if request.include_vectors and self.vectors:
            selected.append("vectors")

        if self.db and not self.workspace:
            selected.append("db")

        return selected

    def _build_header(self, request: ContextBuildRequest) -> dict[str, Any]:
        return {
            "packet_id": str(uuid.uuid4()),
            "created_at": datetime.now(UTC).isoformat(),
            "builder_version": "1.1.0",
            "privacy": "local_only",
            "mode": "SHADOW" if self.workspace else "HISTORICAL",
            "goal": request.goal,
            "trigger": request.trigger,
        }

    def _build_constitution_context(
        self,
        request: ContextBuildRequest,
    ) -> dict[str, Any]:
        workflow: dict[str, Any] = {}
        phase: dict[str, Any] = {}

        if request.workflow_id:
            try:
                workflow = self.intent.load_workflow(request.workflow_id)
            except Exception as e:
                logger.debug(
                    "Workflow constitution unavailable for %s: %s",
                    request.workflow_id,
                    e,
                )

        try:
            phase = self.intent.load_phase(request.phase)
        except Exception as e:
            logger.debug("Phase constitution unavailable for %s: %s", request.phase, e)

        policy_ids: list[str] = []
        if request.workflow_id:
            policy_ids.append(f"workflows/definitions/{request.workflow_id}")
            policy_ids.append(request.workflow_id)
        policy_ids.append(f"phases/{request.phase}")
        policy_ids.append(request.phase)

        rules = self.intent.find_rules(
            phase=request.phase,
            authority="constitution",
            policy_ids=policy_ids,
        )

        return {
            "workflow": workflow,
            "phase": phase,
            "rules": rules,
        }

    def _build_policy_context(self, request: ContextBuildRequest) -> dict[str, Any]:
        if not request.include_policy:
            return {}

        stage: dict[str, Any] = {}
        workflow_policy: dict[str, Any] = {}

        policy_ids: list[str] = []

        if request.stage_id:
            stage_candidates = [
                f"workflows/stages/{request.stage_id}",
                request.stage_id,
            ]
            for candidate in stage_candidates:
                try:
                    stage = self.intent.load_policy(candidate)
                    policy_ids.append(candidate)
                    break
                except Exception:
                    continue

        if request.workflow_id:
            workflow_candidates = [
                f"workflows/{request.workflow_id}",
                f"workflows/definitions/{request.workflow_id}",
                request.workflow_id,
            ]
            for candidate in workflow_candidates:
                try:
                    workflow_policy = self.intent.load_policy(candidate)
                    policy_ids.append(candidate)
                    break
                except Exception:
                    continue

        rules = self.intent.find_rules(
            phase=request.phase,
            authority="policy",
            policy_ids=policy_ids or None,
        )

        return {
            "workflow": workflow_policy,
            "stage": stage,
            "rules": rules,
        }

    def _build_constraints(
        self,
        request: ContextBuildRequest,
        constitution: dict[str, Any],
        policy: dict[str, Any],
    ) -> dict[str, Any]:
        all_rules: list[dict[str, Any]] = []
        all_rules.extend(constitution.get("rules", []))
        all_rules.extend(policy.get("rules", []))

        applicable_rules = [
            rule
            for rule in all_rules
            if str(rule.get("phase", request.phase)).lower() == request.phase.lower()
        ]

        return {
            "phase": request.phase,
            "applicable_rules": applicable_rules,
            "rule_count": len(applicable_rules),
            "authorities_present": sorted(
                {
                    str(rule.get("authority", "unknown"))
                    for rule in applicable_rules
                    if rule.get("authority")
                }
            ),
        }

    async def _gather_ast_evidence(
        self,
        request: ContextBuildRequest,
        graph: dict[str, Any],
    ) -> list[dict[str, Any]]:
        evidence: list[dict[str, Any]] = []

        candidate_files = self._resolve_candidate_files(request, graph)
        requested_symbols = set(request.target_symbols)

        for rel_path in sorted(candidate_files):
            source = self._read_source(rel_path)
            if not source:
                continue

            tracker = ScopeTracker(source)
            try:
                tracker.visit(ast.parse(source))
            except Exception as e:
                logger.debug("AST parse failed for %s: %s", rel_path, e)
                continue

            for symbol in tracker.symbols:
                if requested_symbols and not self._symbol_matches(
                    symbol,
                    requested_symbols,
                ):
                    continue

                evidence.append(
                    {
                        "name": symbol["name"],
                        "path": rel_path,
                        "item_type": "code",
                        "content": symbol["code"],
                        "signature": symbol["signature"],
                        "summary": symbol["docstring"],
                        "source": "workspace" if self.workspace else "filesystem",
                        "symbol_path": symbol["qualname"],
                    }
                )

        return evidence

    async def _gather_vector_evidence(
        self,
        request: ContextBuildRequest,
    ) -> list[dict[str, Any]]:
        evidence: list[dict[str, Any]] = []

        if not self.vectors or not request.goal:
            return evidence

        try:
            results = await self.vectors.search_similar(request.goal, top_k=5)
        except Exception as e:
            logger.debug("Vector search failed: %s", e)
            return evidence

        for item in results:
            rel_path = item.get("path", "")
            hydrated = dict(item)
            hydrated.setdefault("item_type", "semantic_match")
            hydrated.setdefault("source", "vector_search")

            if rel_path:
                hydrated = self._extract_code_for_item(hydrated)

            evidence.append(hydrated)

        return evidence

    async def _gather_db_evidence(
        self,
        request: ContextBuildRequest,
    ) -> list[dict[str, Any]]:
        evidence: list[dict[str, Any]] = []

        if not self.db:
            return evidence

        scope = {
            "include": (
                list(request.target_files)
                + list(request.target_symbols)
                + list(request.target_paths)
            ),
            "exclude": ["tests/", "migrations/", "__pycache__"],
        }

        try:
            results = await self.db.fetch_symbols_for_scope(scope, 500)
        except Exception as e:
            logger.debug("DB evidence fetch failed: %s", e)
            return evidence

        for item in results:
            hydrated = self._extract_code_for_item(dict(item))
            hydrated.setdefault("source", "database")
            evidence.append(hydrated)

        return evidence

    def _resolve_candidate_files(
        self,
        request: ContextBuildRequest,
        graph: dict[str, Any],
    ) -> set[str]:
        files: set[str] = set()

        for path in request.target_files:
            if path.endswith(".py"):
                files.add(path)

        for path in request.target_paths:
            if path.endswith(".py"):
                files.add(path)

        if request.target_symbols:
            for symbol_data in graph.get("symbols", {}).values():
                file_path = symbol_data.get("file_path")
                name = symbol_data.get("name")
                symbol_path = symbol_data.get("symbol_path")
                if not file_path:
                    continue
                if (
                    name in request.target_symbols
                    or symbol_path in request.target_symbols
                ):
                    files.add(file_path)

        if not files and self.workspace:
            for symbol_data in graph.get("symbols", {}).values():
                file_path = symbol_data.get("file_path")
                if file_path and file_path.endswith(".py"):
                    files.add(file_path)

        return files

    def _read_source(self, rel_path: str) -> str | None:
        try:
            if self.workspace and self.workspace.exists(rel_path):
                return self.workspace.read_text(rel_path)

            abs_path = settings.REPO_PATH / rel_path
            if abs_path.exists():
                return abs_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.debug("Failed reading %s: %s", rel_path, e)

        return None

    def _symbol_matches(
        self,
        symbol: dict[str, Any],
        requested_symbols: set[str],
    ) -> bool:
        return (
            symbol.get("name") in requested_symbols
            or symbol.get("qualname") in requested_symbols
        )

    def _extract_code_for_item(self, item: dict[str, Any]) -> dict[str, Any]:
        path = item.get("path", "")
        name_raw = item.get("name", "")
        if not path or not name_raw:
            return item

        target_name = name_raw.split("::")[-1] if "::" in name_raw else name_raw
        source = self._read_source(path)
        if not source:
            return item

        try:
            tracker = ScopeTracker(source)
            tracker.visit(ast.parse(source))
            for symbol in tracker.symbols:
                if symbol["name"] == target_name or symbol["qualname"] == target_name:
                    item["content"] = symbol["code"]
                    item["signature"] = symbol["signature"]
                    item["item_type"] = "code"
                    item["symbol_path"] = symbol["qualname"]
                    break
        except Exception as e:
            logger.debug("Content extraction failed for %s: %s", target_name, e)

        return item

    def _finalize_evidence(
        self,
        items: list[dict[str, Any]],
        request: ContextBuildRequest,
    ) -> list[dict[str, Any]]:
        best_by_identity: dict[tuple[str, str], dict[str, Any]] = {}

        for item in items:
            identity = (
                item.get("symbol_path") or item.get("name", ""),
                item.get("path", ""),
            )
            if identity == ("", ""):
                continue

            item["tokens_est"] = ContextSerializer.estimate_tokens(
                (item.get("content") or "") + (item.get("summary") or "")
            )
            item["_rank"] = self._score_evidence_item(item, request)

            existing = best_by_identity.get(identity)
            if existing is None or item["_rank"] > existing["_rank"]:
                best_by_identity[identity] = item

        ranked = sorted(
            best_by_identity.values(),
            key=lambda item: (
                -int(item.get("_rank", 0)),
                item.get("path", ""),
                item.get("name", ""),
            ),
        )

        for item in ranked:
            item.pop("_rank", None)

        return ranked

    def _score_evidence_item(
        self,
        item: dict[str, Any],
        request: ContextBuildRequest,
    ) -> int:
        score = 0
        path = str(item.get("path", ""))
        name = str(item.get("name", ""))
        symbol_path = str(item.get("symbol_path", ""))
        source = str(item.get("source", ""))
        has_content = bool(item.get("content"))

        if path in request.target_files:
            score += 100
        if path in request.target_paths:
            score += 80
        if name in request.target_symbols or symbol_path in request.target_symbols:
            score += 120
        if has_content:
            score += 30

        source_bonus = {
            "filesystem": 25,
            "workspace": 25,
            "database": 15,
            "vector_search": 5,
        }
        score += source_bonus.get(source, 0)

        return score

    def _build_runtime_context(
        self,
        request: ContextBuildRequest,
        selected_providers: list[str],
    ) -> dict[str, Any]:
        if not request.include_runtime:
            return {}

        return {
            "trigger": request.trigger,
            "phase": request.phase,
            "workspace_active": self.workspace is not None,
            "workflow_id": request.workflow_id,
            "stage_id": request.stage_id,
            "target_files": list(request.target_files),
            "target_symbols": list(request.target_symbols),
            "target_paths": list(request.target_paths),
            "providers_selected": selected_providers,
        }
