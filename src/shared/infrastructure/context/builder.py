# src/shared/infrastructure/context/builder.py
"""
ContextBuilder - Sensory-aware context assembly.

Responsible for building ContextPackage data and converting it into a context
payload suitable for downstream modules. Supports LimbWorkspace for "Future
Truth" context extraction.
"""

from __future__ import annotations

import ast
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from features.introspection.knowledge_graph_service import KnowledgeGraphBuilder
from shared.config import settings
from shared.infrastructure.knowledge.knowledge_service import KnowledgeService
from shared.logger import getLogger

from .serializers import ContextSerializer


if TYPE_CHECKING:
    from shared.infrastructure.context.limb_workspace import LimbWorkspace

logger = getLogger(__name__)


# ID: 7ac392a5-996c-45e5-ad32-e31ce9911f14
class ScopeTracker(ast.NodeVisitor):
    """
    AST visitor that collects symbol data for a source module.

    Preserved from current implementation to maintain robustness.
    """

    def __init__(self, source: str) -> None:
        self.source = source
        self.stack: list[str] = []
        self.symbols: list[dict[str, Any]] = []

    # ID: 9f700523-8a3e-42d4-a2ce-980ae6371b5b
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._add_symbol(node)
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    # ID: 9135af2c-29d8-4c30-a087-a82d22b72cc5
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._add_symbol(node)
        self.generic_visit(node)

    # ID: 33a3b223-54d9-4a62-b12b-fda2f2239b6f
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._add_symbol(node)
        self.generic_visit(node)

    def _add_symbol(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
    ) -> None:
        if self.stack:
            qualname = f"{'.'.join(self.stack)}.{node.name}"
        else:
            qualname = node.name

        try:
            segment = ast.get_source_segment(self.source, node)
            signature = segment.split("\n")[0] if segment else f"def {node.name}(...)"
            lines = self.source.splitlines()
            end_lineno = getattr(node, "end_lineno", node.lineno) or node.lineno
            code = "\n".join(lines[node.lineno - 1 : end_lineno])
        except Exception as exc:
            logger.debug(
                "ScopeTracker: failed to extract code for %s: %s", node.name, exc
            )
            signature = f"def {node.name}(...)"
            code = "# Code extraction failed"

        docstring = ast.get_docstring(node) or ""
        self.symbols.append(
            {
                "name": node.name,
                "qualname": qualname,
                "signature": signature,
                "code": code,
                "docstring": docstring,
            }
        )


# ID: e90e2005-1f52-47e2-a456-46bdd1532a44
class ContextBuilder:
    """
    Assembles governed context packets.

    Uses LimbWorkspace when present to provide "Future Truth" sensation.
    """

    def __init__(
        self,
        db_provider: Any,
        vector_provider: Any,
        ast_provider: Any,
        config: dict[str, Any] | None,
        workspace: LimbWorkspace | None = None,
    ) -> None:
        self.db = db_provider
        self.vectors = vector_provider
        self.ast = ast_provider
        self.config = config or {}
        self.workspace = workspace
        self.version = "0.2.1"
        self.policy = self._load_policy()
        self._knowledge_graph: dict[str, Any] = {"symbols": {}}

    def _load_policy(self) -> dict[str, Any]:
        policy_path = settings.REPO_PATH / ".intent/context/policy.yaml"
        fallback_path = Path(".intent/context/policy.yaml")
        for candidate in (policy_path, fallback_path):
            if candidate.exists():
                try:
                    with candidate.open(encoding="utf-8") as handle:
                        return yaml.safe_load(handle) or {}
                except Exception as exc:
                    logger.error(
                        "ContextBuilder: failed to load policy %s: %s", candidate, exc
                    )
                    break
        return {}

    # ID: load_current_truth
    async def _load_knowledge_graph(self) -> dict[str, Any]:
        """
        Determine the current knowledge graph "truth".

        Uses a shadow graph when a workspace is present; otherwise uses the
        historical database source.
        """
        if self.workspace:
            logger.info("ContextBuilder: sensing future truth via shadow graph")
            builder = KnowledgeGraphBuilder(
                settings.REPO_PATH, workspace=self.workspace
            )
            return builder.build()

        try:
            knowledge_service = KnowledgeService(settings.REPO_PATH)
            return await knowledge_service.get_graph()
        except Exception as exc:
            logger.error("ContextBuilder: failed to sense historical truth: %s", exc)
            return {"symbols": {}}

    # ID: be34f105-e983-4c0e-9e20-79603db377a3
    async def build_for_task(self, task_spec: dict[str, Any]) -> dict[str, Any]:
        start_time = datetime.now(UTC)

        self._knowledge_graph = await self._load_knowledge_graph()

        packet_id = str(uuid.uuid4())
        created_at = start_time.isoformat()
        scope_spec = task_spec.get("scope", {})

        target_file = task_spec.get("target_file", "")
        target_module = ""
        if target_file:
            target_module = (
                target_file.replace("src/", "", 1).replace(".py", "").replace("/", ".")
            )

        packet = {
            "header": {
                "packet_id": packet_id,
                "task_id": task_spec["task_id"],
                "task_type": task_spec["task_type"],
                "created_at": created_at,
                "builder_version": self.version,
                "privacy": task_spec.get("privacy", "local_only"),
                "sensation_mode": "SHADOW" if self.workspace else "HISTORICAL",
            },
            "problem": {
                "summary": task_spec.get("summary", ""),
                "target_file": target_file,
                "target_module": target_module,
                "intent_ref": task_spec.get("intent_ref"),
                "acceptance": task_spec.get("acceptance", []),
            },
            "scope": {
                "include": scope_spec.get("include", []),
                "exclude": scope_spec.get("exclude", []),
                "globs": scope_spec.get("globs", []),
                "roots": scope_spec.get("roots", []),
                "traversal_depth": scope_spec.get("traversal_depth", 0),
            },
            "constraints": self._build_constraints(task_spec),
            "context": [],
            "invariants": self._default_invariants(),
            "policy": {"redactions_applied": [], "remote_allowed": False, "notes": ""},
            "provenance": {
                "inputs": {},
                "build_stats": {},
                "cache_key": "",
                "packet_hash": "",
            },
        }

        context_items = await self._collect_context(packet, task_spec)
        context_items = self._apply_constraints(context_items, packet["constraints"])

        for item in context_items:
            item["tokens_est"] = self._estimate_item_tokens(item)

        packet["context"] = context_items
        duration_ms = int((datetime.now(UTC) - start_time).total_seconds() * 1000)
        packet["provenance"]["build_stats"] = {
            "duration_ms": duration_ms,
            "items_collected": len(context_items),
            "tokens_total": sum(item.get("tokens_est", 0) for item in context_items),
        }
        packet["provenance"]["cache_key"] = ContextSerializer.compute_cache_key(
            task_spec
        )

        return packet

    async def _collect_context(
        self, packet: dict[str, Any], task_spec: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Collect context items using deterministic scaling."""
        items: list[dict[str, Any]] = []
        scope = packet["scope"]
        constraints = packet["constraints"]

        target_symbol = task_spec.get("target_symbol")
        is_surgical = bool(target_symbol)

        if is_surgical:
            adequate_db_limit = 5
            adequate_vec_limit = 3
        else:
            adequate_db_limit = constraints["max_items"] // 2
            adequate_vec_limit = constraints["max_items"] // 3

        if self.db:
            seed_items = await self.db.get_symbols_for_scope(scope, adequate_db_limit)
            items.extend(seed_items)

        if self.vectors and task_spec.get("summary"):
            vec_items = await self.vectors.search_similar(
                task_spec["summary"], top_k=adequate_vec_limit
            )
            items.extend(vec_items)

        traversal_depth = scope.get("traversal_depth", 0)
        if traversal_depth > 0 and self._knowledge_graph.get("symbols") and items:
            related_items = self._traverse_graph(
                list(items),
                traversal_depth,
                constraints["max_items"] - len(items),
            )
            items.extend(related_items)

        forced_items = await self._force_add_code_item(task_spec)
        if forced_items:
            items = forced_items + items

        seen_keys: set[tuple[Any, Any, Any]] = set()
        unique_items: list[dict[str, Any]] = []
        for item in items:
            key = (item.get("name"), item.get("path"), item.get("item_type"))
            if key not in seen_keys:
                seen_keys.add(key)
                unique_items.append(item)

        return unique_items

    def _traverse_graph(
        self, seed_items: list[dict[str, Any]], depth: int, limit: int
    ) -> list[dict[str, Any]]:
        if not self._knowledge_graph.get("symbols"):
            return []
        all_symbols = self._knowledge_graph["symbols"]
        related_symbol_keys: set[str] = set()
        queue = {
            item.get("metadata", {}).get("symbol_path")
            for item in seed_items
            if item.get("metadata", {}).get("symbol_path")
        }

        for _ in range(depth):
            if not queue or len(related_symbol_keys) >= limit:
                break
            next_queue: set[str] = set()
            for symbol_key in queue:
                symbol_data = all_symbols.get(symbol_key)
                if symbol_data:
                    for callee_name in symbol_data.get("calls", []):
                        if callee_name not in related_symbol_keys:
                            related_symbol_keys.add(callee_name)
                            next_queue.add(callee_name)
                for caller_key, caller_data in all_symbols.items():
                    if symbol_key and symbol_key.split("::")[-1] in caller_data.get(
                        "calls", []
                    ):
                        if caller_key not in related_symbol_keys:
                            related_symbol_keys.add(caller_key)
                            next_queue.add(caller_key)
            queue = next_queue

        related_items: list[dict[str, Any]] = []
        for key in list(related_symbol_keys)[:limit]:
            symbol_data = all_symbols.get(key)
            if symbol_data:
                related_items.append(self._format_symbol_as_context_item(symbol_data))
        return related_items

    # ID: format_symbol_with_sensation
    def _format_symbol_as_context_item(
        self, symbol_data: dict[str, Any]
    ) -> dict[str, Any]:
        symbol_path = symbol_data.get("symbol_path", "")
        name = symbol_data.get("name", "")

        file_path_raw = symbol_path.split("::")[0] if "::" in symbol_path else None
        content = None
        signature = str(symbol_data.get("parameters", []))

        if file_path_raw and name:
            try:
                if self.workspace:
                    source = self.workspace.read_text(file_path_raw)
                else:
                    source = (settings.REPO_PATH / file_path_raw).read_text(
                        encoding="utf-8"
                    )

                visitor = ScopeTracker(source)
                visitor.visit(ast.parse(source))
                for sym in visitor.symbols:
                    if sym["name"] == name or sym.get("qualname") == name:
                        content = sym["code"]
                        signature = sym["signature"]
                        break
            except Exception as exc:
                logger.warning(
                    "ContextBuilder: sensation failure for %s: %s", file_path_raw, exc
                )

        return {
            "name": name,
            "path": file_path_raw,
            "item_type": "code" if content else "symbol",
            "content": content,
            "signature": signature,
            "summary": symbol_data.get("intent") or symbol_data.get("docstring", ""),
            "source": (
                "shadow_graph_traversal" if self.workspace else "db_graph_traversal"
            ),
        }

    async def _force_add_code_item(
        self, task_spec: dict[str, Any]
    ) -> list[dict[str, Any]]:
        target_file_str = task_spec.get("target_file")
        target_symbol = task_spec.get("target_symbol")

        if not target_file_str or not target_symbol:
            return []

        try:
            if self.workspace:
                source = self.workspace.read_text(target_file_str)
            else:
                source = (settings.REPO_PATH / target_file_str).read_text(
                    encoding="utf-8"
                )

            visitor = ScopeTracker(source)
            visitor.visit(ast.parse(source))

            for sym in visitor.symbols:
                if sym["name"] == target_symbol or sym.get("qualname") == target_symbol:
                    return [
                        {
                            "name": sym["name"],
                            "path": target_file_str,
                            "item_type": "code",
                            "content": sym["code"],
                            "summary": (
                                sym["docstring"][:200] if sym["docstring"] else ""
                            ),
                            "source": "shadow_ast" if self.workspace else "builtin_ast",
                            "signature": sym.get("signature", ""),
                        }
                    ]
        except Exception as exc:
            logger.warning("ContextBuilder: failed to force add code item: %s", exc)
        return []

    def _apply_constraints(
        self, items: list[dict[str, Any]], constraints: dict[str, Any]
    ) -> list[dict[str, Any]]:
        max_items = constraints.get("max_items", 50)
        max_tokens = constraints.get("max_tokens", 100000)
        if len(items) > max_items:
            items = items[:max_items]
        total = 0
        filtered: list[dict[str, Any]] = []
        for item in items:
            tok = self._estimate_item_tokens(item)
            if total + tok > max_tokens:
                break
            filtered.append(item)
            total += tok
        return filtered

    def _estimate_item_tokens(self, item: dict[str, Any]) -> int:
        text = " ".join([item.get("content", ""), item.get("summary", "")])
        return ContextSerializer.estimate_tokens(text)

    def _build_constraints(self, task_spec: dict[str, Any]) -> dict[str, Any]:
        constraints = task_spec.get("constraints", {})
        return {
            "max_tokens": constraints.get("max_tokens", 100000),
            "max_items": constraints.get("max_items", 50),
        }

    def _default_invariants(self) -> list[str]:
        return ["All symbols must have signatures", "All paths must be relative"]
