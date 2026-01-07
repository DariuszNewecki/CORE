# src/shared/infrastructure/context/builder.py

"""ContextBuilder - Assembles governed context packets."""

from __future__ import annotations

import ast
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from shared.config import settings
from shared.infrastructure.knowledge.knowledge_service import KnowledgeService
from shared.logger import getLogger

from .serializers import ContextSerializer


logger = getLogger(__name__)


def _parse_python_file(filepath: str) -> list[dict]:
    """
    Parses a Python file and extracts metadata for ALL functions and classes,
    including methods nested within classes, with fully qualified names.
    """
    try:
        with open(filepath, encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source, filename=filepath)
        symbols = []

        # ID: 7ac392a5-996c-45e5-ad32-e31ce9911f14
        class ScopeTracker(ast.NodeVisitor):
            def __init__(self):
                self.stack = []
                self.symbols = []

            # ID: 417ad0a2-1644-4f2b-b24d-15e80f2d89a3
            def visit_ClassDef(self, node):
                self._add_symbol(node)
                self.stack.append(node.name)
                self.generic_visit(node)
                self.stack.pop()

            # ID: be71d623-a2d1-4f47-bbd8-46c2fff089de
            def visit_FunctionDef(self, node):
                self._add_symbol(node)
                self.generic_visit(node)

            # ID: 45746cbb-6f2d-406a-a970-c325e1cad78f
            def visit_AsyncFunctionDef(self, node):
                self._add_symbol(node)
                self.generic_visit(node)

            def _add_symbol(self, node):
                if self.stack:
                    qualname = f"{'.'.join(self.stack)}.{node.name}"
                else:
                    qualname = node.name

                # Extract code segment
                try:
                    signature = ast.get_source_segment(source, node).split("\n")[0]
                    lines = source.splitlines()
                    end_lineno = getattr(node, "end_lineno", node.lineno)
                    code = "\n".join(lines[node.lineno - 1 : end_lineno])
                except Exception:
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

        visitor = ScopeTracker()
        visitor.visit(tree)
        return visitor.symbols
    except Exception as e:
        logger.error("Failed to parse %s: %s", filepath, e)
        return []


# ID: e90e2005-1f52-47e2-a456-46bdd1532a44
class ContextBuilder:
    def __init__(self, db_provider, vector_provider, ast_provider, config):
        self.db = db_provider
        self.vectors = vector_provider
        self.ast = ast_provider
        self.config = config or {}
        self.version = "0.2.0"
        self.policy = self._load_policy()
        # Knowledge graph will be loaded fresh from DB on each build
        self._knowledge_graph = {"symbols": {}}

    def _load_policy(self) -> dict[str, Any]:
        policy_path = Path(".intent/context/policy.yaml")
        if policy_path.exists():
            with open(policy_path, encoding="utf-8") as f:
                return yaml.safe_load(f)
        return {}

    async def _load_knowledge_graph_from_db(self) -> dict[str, Any]:
        """Loads the knowledge graph from database (SSOT)."""
        try:
            # CONSTITUTIONAL FIX: Explicitly passing REPO_PATH
            knowledge_service = KnowledgeService(settings.REPO_PATH)
            graph = await knowledge_service.get_graph()
            logger.info(
                "Loaded knowledge graph with %s symbols from DB",
                len(graph.get("symbols", {})),
            )
            return graph
        except Exception as e:
            logger.error("Failed to load knowledge graph from DB: %s", e)
            return {"symbols": {}}

    # ID: be34f105-e983-4c0e-9e20-79603db377a3
    async def build_for_task(self, task_spec: dict[str, Any]) -> dict[str, Any]:
        start_time = datetime.now(UTC)
        logger.info("Building context for task %s", task_spec.get("task_id"))

        # Load fresh knowledge graph from DB (SSOT)
        self._knowledge_graph = await self._load_knowledge_graph_from_db()

        packet_id = str(uuid.uuid4())
        created_at = start_time.isoformat()
        scope_spec = task_spec.get("scope", {})

        # PROPER CONFIGURATION: Derive canonical import path for the target file
        target_file = task_spec.get("target_file", "")
        target_module = ""
        if target_file:
            # e.g., 'src/shared/utils/common_knowledge.py' -> 'shared.utils.common_knowledge'
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
            },
            "problem": {
                "summary": task_spec.get("summary", ""),
                "target_file": target_file,
                "target_module": target_module,  # <--- NEW: Crucial address for LLM imports
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
            "items_filtered": 0,
            "tokens_total": sum(item.get("tokens_est", 0) for item in context_items),
        }
        packet["provenance"]["cache_key"] = ContextSerializer.compute_cache_key(
            task_spec
        )
        logger.info(
            "Built packet %s with %s items in %sms",
            packet_id,
            len(context_items),
            duration_ms,
        )
        return packet

    async def _collect_context(self, packet: dict, task_spec: dict) -> list[dict]:
        items = []
        scope = packet["scope"]
        max_items = packet["constraints"]["max_items"]
        if self.db:
            seed_items = await self.db.get_symbols_for_scope(scope, max_items // 2)
            items.extend(seed_items)
        if self.vectors and task_spec.get("summary"):
            vec_items = await self.vectors.search_similar(
                task_spec["summary"], top_k=max_items // 3
            )
            items.extend(vec_items)
        traversal_depth = scope.get("traversal_depth", 0)
        if traversal_depth > 0 and self._knowledge_graph.get("symbols") and items:
            logger.info("Traversing knowledge graph to depth %s.", traversal_depth)
            related_items = self._traverse_graph(
                list(items), traversal_depth, max_items - len(items)
            )
            items.extend(related_items)
        forced_items = await self._force_add_code_item(task_spec)
        if forced_items:
            items = forced_items + items
        seen_keys = set()
        unique_items = []
        for item in items:
            key = (item.get("name"), item.get("path"), item.get("item_type"))
            if key not in seen_keys:
                seen_keys.add(key)
                unique_items.append(item)
        return unique_items

    def _traverse_graph(
        self, seed_items: list[dict], depth: int, limit: int
    ) -> list[dict]:
        if not self._knowledge_graph.get("symbols"):
            return []
        all_symbols = self._knowledge_graph["symbols"]
        related_symbol_keys = set()
        queue = {
            item.get("metadata", {}).get("symbol_path")
            for item in seed_items
            if item.get("metadata", {}).get("symbol_path")
        }
        for _ in range(depth):
            if not queue or len(related_symbol_keys) >= limit:
                break
            next_queue = set()
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
        related_items = []
        for key in list(related_symbol_keys)[:limit]:
            symbol_data = all_symbols.get(key) or self._find_symbol_by_qualname(key)
            if symbol_data:
                related_items.append(self._format_symbol_as_context_item(symbol_data))
        logger.info("Found %s related symbols via graph traversal.", len(related_items))
        return related_items

    def _find_symbol_by_qualname(self, qualname: str) -> dict | None:
        """Finds a symbol in the knowledge graph by its qualified name."""
        for symbol in self._knowledge_graph.get("symbols", {}).values():
            symbol_name = symbol.get("name")
            if symbol_name == qualname:
                return symbol
        return None

    def _format_symbol_as_context_item(self, symbol_data: dict) -> dict:
        """Formats a symbol dictionary from the knowledge graph into a context item."""
        symbol_path = symbol_data.get("symbol_path", "")
        name = symbol_data.get("name", "")

        file_path_raw = None
        if "::" in symbol_path:
            file_path_raw = symbol_path.split("::")[0]

        content = None
        signature = str(symbol_data.get("parameters", []))

        if file_path_raw and name:
            # CONSTITUTIONAL FIX: Use settings.REPO_PATH as SSOT
            full_path = settings.REPO_PATH / file_path_raw
            if full_path.exists():
                try:
                    symbols = _parse_python_file(str(full_path))
                    for sym in symbols:
                        if sym.get("qualname") == name or sym["name"] == name:
                            content = sym["code"]
                            signature = sym.get("signature", signature)
                            break
                except Exception as e:
                    logger.warning(
                        "Failed to parse %s for symbol %s: %s", file_path_raw, name, e
                    )

        return {
            "name": name,
            "path": file_path_raw,
            "item_type": "code" if content else "symbol",
            "content": content,
            "signature": signature,
            "summary": symbol_data.get("intent") or symbol_data.get("docstring", ""),
            "source": "db_graph_traversal",
        }

    async def _force_add_code_item(self, task_spec: dict) -> list[dict]:
        """
        Loads the specific target symbol source code.
        Returns a list containing the code item (or empty if not found).
        """
        target_file_str = task_spec.get("target_file")
        target_symbol = task_spec.get("target_symbol")

        if not target_file_str or not target_symbol:
            return []

        logger.debug(
            "ContextBuilder: force_add_code target_file=%s, target_symbol=%s",
            target_file_str,
            target_symbol,
        )

        # CONSTITUTIONAL FIX: Use settings.REPO_PATH as SSOT
        full_path = settings.REPO_PATH / target_file_str

        if not full_path.exists():
            logger.warning(
                "ContextBuilder: File not found via REPO_PATH: %s", full_path
            )
            return []

        logger.info("FORCE-ADDING CODE ITEM for '%s'", target_symbol)
        symbols = _parse_python_file(str(full_path))

        for sym in symbols:
            if sym["name"] == target_symbol or sym.get("qualname") == target_symbol:
                item = {
                    "name": sym["name"],
                    "path": target_file_str,
                    "item_type": "code",
                    "content": sym["code"],
                    "summary": sym["docstring"][:200] if sym["docstring"] else "",
                    "source": "builtin_ast",
                    "signature": sym.get("signature", ""),
                }
                return [item]

        logger.warning(
            "Target symbol '%s' not found in %s", target_symbol, target_file_str
        )
        return []

    def _apply_constraints(self, items: list, constraints: dict) -> list:
        max_items = constraints.get("max_items", 50)
        max_tokens = constraints.get("max_tokens", 100000)
        if len(items) > max_items:
            items = items[:max_items]
        total = 0
        filtered = []
        for item in items:
            tok = self._estimate_item_tokens(item)
            if total + tok > max_tokens:
                break
            filtered.append(item)
            total += tok
        return filtered

    def _estimate_item_tokens(self, item: dict) -> int:
        text = " ".join([item.get("content", ""), item.get("summary", "")])
        return ContextSerializer.estimate_tokens(text)

    def _build_constraints(self, task_spec: dict) -> dict:
        constraints = task_spec.get("constraints", {})
        return {
            "max_tokens": constraints.get("max_tokens", 100000),
            "max_items": constraints.get("max_items", 50),
            "forbidden_paths": [],
            "forbidden_calls": [],
        }

    def _default_invariants(self) -> list[str]:
        return [
            "All symbols must have signatures",
            "No filesystem operations in snippets",
            "No network calls in snippets",
            "All paths must be relative",
        ]
