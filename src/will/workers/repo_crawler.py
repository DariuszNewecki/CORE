# src/will/workers/repo_crawler.py
"""
Repo Crawler Worker — structural self-model builder.

- Declaration:  .intent/workers/repo_crawler.yaml
- Class:        sensing
- Phase:        audit
- Schedule:     max_interval=86400s, glide_off=8640s (10% default)

Responsibilities (one per run):
  1. Open a crawl_run record.
  2. Walk declared directory scopes (no symlinks).
  3. For each .py file: extract AST call graph → core.symbol_calls
     AND register artifact → core.repo_artifacts (for semantic embedding).
  4. For each non-.py file: register → core.repo_artifacts.
  5. Cross-reference artifacts → symbols → core.artifact_symbol_links.
  6. Close crawl_run with summary stats.
  7. Post blackboard report.

Does NOT embed. Embedding is delegated to RepoEmbedderWorker.
"""

from __future__ import annotations

import ast
import hashlib
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from shared.logger import getLogger
from shared.workers.base import Worker


logger = getLogger(__name__)

# ---------------------------------------------------------------------------
# Directory scope configuration
# ---------------------------------------------------------------------------

_CRAWL_SCOPES: list[tuple[str, str]] = [
    # (glob_pattern, artifact_type)
    ("src/**/*.py", "python"),  # Python — call graph + semantic embedding
    ("docs/**/*.md", "doc"),
    ("docs/**/*.rst", "doc"),
    ("tests/**/*.py", "test"),
    ("var/prompts/**/model.yaml", "prompt"),
    ("var/prompts/**/system.txt", "prompt"),
    ("var/prompts/**/user.txt", "prompt"),
    ("reports/**/*.yaml", "report"),
    ("reports/**/*.md", "report"),
    (".intent/**/*.yaml", "intent"),
    (".intent/**/*.json", "intent"),
    ("infra/**/*.sql", "infra"),
]

_QDRANT_COLLECTION_MAP: dict[str, str] = {
    "python": "core-code",  # Python source — semantic search over implementation
    "doc": "core-docs",
    "test": "core-tests",
    "prompt": "core-prompts",
    "report": "core-reports",
    "intent": "core-patterns",  # reuses existing intent collection
    "infra": "core-docs",  # infra SQL goes into docs collection
}

# Layer detection from module path prefix
_LAYER_MAP: dict[str, str] = {
    "src/mind": "mind",
    "src/body": "body",
    "src/will": "will",
    "src/shared": "shared",
}


# ID: f1a2b3c4-d5e6-7890-abcd-ef1234567891
class RepoCrawlerWorker(Worker):
    """
    Sensing worker. Walks the CORE repository and builds the structural
    self-model: call graph edges, artifact registry, and artifact-symbol links.
    """

    declaration_name = "repo_crawler"

    def __init__(self, cognitive_service: Any = None) -> None:
        from shared.infrastructure.bootstrap_registry import BootstrapRegistry

        super().__init__()
        self._cognitive_service = cognitive_service
        self._repo_root: Path = BootstrapRegistry.get_repo_path()
        schedule = self._declaration.get("mandate", {}).get("schedule", {})
        self._max_interval: int = schedule.get("max_interval", 86400)
        self._glide_off: int = schedule.get(
            "glide_off", max(int(self._max_interval * 0.10), 10)
        )

    # ID: a1b2c3d4-e5f6-7890-abcd-ef1234567892
    async def run_loop(self) -> None:
        """
        Continuous self-scheduling loop. Runs one crawl pass per
        max_interval seconds.
        """
        logger.info(
            "RepoCrawlerWorker: starting loop (max_interval=%ds, glide_off=%ds)",
            self._max_interval,
            self._glide_off,
        )

        await self._register()

        while True:
            try:
                await self.run()
            except Exception as exc:
                logger.error("RepoCrawlerWorker: cycle failed: %s", exc, exc_info=True)
                try:
                    await self._post_entry(
                        entry_type="report",
                        subject="repo_crawler.cycle_error",
                        payload={"error": str(exc)},
                        status="abandoned",
                    )
                except Exception:
                    logger.exception("RepoCrawlerWorker: failed to post error report")

            await __import__("asyncio").sleep(self._max_interval)

    # ID: b2c3d4e5-f6a7-8901-bcde-f12345678903
    async def run(self) -> None:
        """Crawl repository — extract call graph and register artifacts."""
        from body.services.service_registry import service_registry

        logger.info("RepoCrawlerWorker: starting crawl pass")

        crawl_run_id = uuid.uuid4()
        stats = {
            "files_scanned": 0,
            "files_changed": 0,
            "symbols_linked": 0,
            "edges_created": 0,
            "chunks_upserted": 0,
        }

        svc = await service_registry.get_crawl_service()
        await svc.open_crawl_run(str(crawl_run_id))

        try:
            symbol_index = await svc.load_symbol_index()
            existing_hashes = await svc.load_artifact_hashes()

            for glob_pattern, artifact_type in _CRAWL_SCOPES:
                for file_path in sorted(self._repo_root.glob(glob_pattern)):
                    # Never follow symlinks
                    if file_path.is_symlink():
                        continue

                    rel_path = str(file_path.relative_to(self._repo_root))
                    stats["files_scanned"] += 1

                    try:
                        content_hash = _sha256(file_path)

                        if artifact_type == "python":
                            changed = await self._process_python_file(
                                svc=svc,
                                file_path=file_path,
                                rel_path=rel_path,
                                content_hash=content_hash,
                                existing_hashes=existing_hashes,
                                symbol_index=symbol_index,
                                crawl_run_id=crawl_run_id,
                                stats=stats,
                            )
                        else:
                            changed = await self._process_artifact_file(
                                svc=svc,
                                file_path=file_path,
                                rel_path=rel_path,
                                content_hash=content_hash,
                                artifact_type=artifact_type,
                                existing_hashes=existing_hashes,
                                symbol_index=symbol_index,
                                crawl_run_id=crawl_run_id,
                                stats=stats,
                            )

                        if changed:
                            stats["files_changed"] += 1

                    except Exception as exc:
                        logger.warning(
                            "RepoCrawlerWorker: error processing %s: %s",
                            rel_path,
                            exc,
                        )

            await svc.close_crawl_run_completed(str(crawl_run_id), stats)

        except Exception as exc:
            await svc.close_crawl_run_failed(str(crawl_run_id), str(exc))
            raise

        await self.post_report(
            subject="repo.crawl.complete",
            payload={
                "crawl_run_id": str(crawl_run_id),
                **stats,
                "completed_at": datetime.now(UTC).isoformat(),
            },
        )
        logger.info("RepoCrawlerWorker: crawl complete — %s", stats)

    # -------------------------------------------------------------------------
    # Python file processing — call graph extraction + artifact registration
    # -------------------------------------------------------------------------

    # ID: c4d5e6f7-a8b9-0c1d-2e3f-4a5b6c7d8e9f
    async def _process_python_file(
        self,
        svc: Any,
        file_path: Path,
        rel_path: str,
        content_hash: str,
        existing_hashes: dict[str, str],
        symbol_index: dict[str, str],
        crawl_run_id: uuid.UUID,
        stats: dict[str, int],
    ) -> bool:
        """
        Extract AST call graph edges AND register in repo_artifacts for
        semantic embedding by RepoEmbedderWorker.

        Both operations run on every changed file. Call graph extraction
        is skipped on unchanged files; artifact registration uses
        ON CONFLICT DO UPDATE so it is always current.
        """
        changed = existing_hashes.get(rel_path) != content_hash

        qdrant_collection = _QDRANT_COLLECTION_MAP["python"]
        await svc.upsert_python_artifact(
            rel_path, content_hash, qdrant_collection, str(crawl_run_id)
        )

        if not changed:
            return False

        # Call graph extraction — only on changed files
        source = file_path.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(source)
        except SyntaxError:
            logger.warning("RepoCrawlerWorker: syntax error in %s, skipping", rel_path)
            return True  # Still registered in artifacts, just no call graph

        layer = _detect_layer(rel_path)
        extractor = _CallGraphExtractor(
            rel_path=rel_path,
            layer=layer,
            symbol_index=symbol_index,
            crawl_run_id=crawl_run_id,
        )
        edges = extractor.extract(tree)

        if edges:
            await svc.delete_stale_symbol_calls(rel_path, str(crawl_run_id))
            await svc.insert_symbol_calls(edges)
            stats["edges_created"] += len(edges)

        return True

    # -------------------------------------------------------------------------
    # Non-Python artifact processing
    # -------------------------------------------------------------------------

    # ID: d5e6f7a8-b9c0-1d2e-3f4a-5b6c7d8e9f0a
    async def _process_artifact_file(
        self,
        svc: Any,
        file_path: Path,
        rel_path: str,
        content_hash: str,
        artifact_type: str,
        existing_hashes: dict[str, str],
        symbol_index: dict[str, str],
        crawl_run_id: uuid.UUID,
        stats: dict[str, int],
    ) -> bool:
        """Register a non-Python artifact and cross-reference symbols."""
        changed = existing_hashes.get(rel_path) != content_hash

        qdrant_collection = _QDRANT_COLLECTION_MAP.get(artifact_type)
        await svc.upsert_artifact(
            rel_path, artifact_type, content_hash, qdrant_collection, str(crawl_run_id)
        )

        if changed:
            artifact_id = await svc.fetch_artifact_id(rel_path)
            if artifact_id:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                links = _find_symbol_references(
                    content, symbol_index, rel_path, artifact_type
                )
                await svc.insert_artifact_symbol_links(artifact_id, links)
                stats["symbols_linked"] += len(links)

        return changed


# ---------------------------------------------------------------------------
# AST Call Graph Extractor
# ---------------------------------------------------------------------------


class _CallGraphExtractor(ast.NodeVisitor):
    """
    Extracts directed call graph edges from a Python AST.
    Produces edge dicts ready for insertion into core.symbol_calls.

    symbol_path format matches DB: src/path/to/file.py::ClassName.method_name

    Resolution cascade (applied in order until a match is found):
      1. Direct key match against symbol_index (rarely hits — kept for completeness)
      2. Qualname match: symbol_index key suffix after '::' (e.g. 'ClassName.method')
      3. self./cls. stripping + current-class qualification
      4. Module dotted path → file path conversion
         (e.g. 'will.workers.foo.Bar' → 'src/will/workers/foo.py::Bar')
      5. Short name unique match (only when exactly one symbol has that short name)
    """

    def __init__(
        self,
        rel_path: str,
        layer: str,
        symbol_index: dict[str, str],
        crawl_run_id: uuid.UUID,
    ) -> None:
        self._rel_path = rel_path
        self._layer = layer
        self._symbol_index = symbol_index
        self._crawl_run_id = str(crawl_run_id)
        self._edges: list[dict[str, Any]] = []
        self._current_caller_id: str | None = None
        self._current_class: str | None = None

        # --- Secondary indexes built once at construction time ---

        # qualname (part after '::') → id
        self._qualname_index: dict[str, str] = {}
        # short name (last dot-segment of qualname) → list of ids
        _shortname_bucket: dict[str, list[str]] = {}

        for symbol_path, symbol_id in symbol_index.items():
            if "::" not in symbol_path:
                continue
            qualname = symbol_path.split("::", 1)[1]
            self._qualname_index[qualname] = symbol_id
            short = qualname.split(".")[-1]
            _shortname_bucket.setdefault(short, []).append(symbol_id)

        # Only keep entries that are unambiguous (exactly one match)
        self._shortname_index: dict[str, str] = {
            k: v[0] for k, v in _shortname_bucket.items() if len(v) == 1
        }

    # ID: 6b2f1fc9-9666-44db-a3e1-407dc81e2a39
    def extract(self, tree: ast.AST) -> list[dict[str, Any]]:
        self.visit(tree)
        return self._edges

    # ID: 02eaa803-3c00-4aa3-b2e5-dbaced1a91a2
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if self._current_class:
            qualname = f"{self._current_class}.{node.name}"
        else:
            qualname = node.name
        symbol_path = f"{self._rel_path}::{qualname}"
        self._current_caller_id = self._symbol_index.get(symbol_path)
        self.generic_visit(node)
        self._current_caller_id = None

    visit_AsyncFunctionDef = visit_FunctionDef

    # ID: 216190a2-ca25-4659-9cac-7659d3fefef4
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        prev_class = self._current_class
        self._current_class = node.name
        # Record inheritance edges
        symbol_path = f"{self._rel_path}::{node.name}"
        caller_id = self._symbol_index.get(symbol_path)
        for base in node.bases:
            callee_raw = ast.unparse(base)
            self._add_edge(
                callee_raw=callee_raw,
                edge_kind="inheritance",
                line_number=node.lineno,
                caller_id=caller_id,
            )
        self.generic_visit(node)
        self._current_class = prev_class

    # ID: 09f061e2-059f-4fce-8232-1c10ff4df527
    def visit_Call(self, node: ast.Call) -> None:
        if self._current_caller_id is None:
            self.generic_visit(node)
            return

        callee_raw = ast.unparse(node.func)
        self._add_edge(
            callee_raw=callee_raw,
            edge_kind="direct_call",
            line_number=node.lineno,
        )
        self.generic_visit(node)

    # ID: b15b99d6-420f-49b9-8cbf-c5a83f8f6700
    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._add_edge(
                callee_raw=alias.name,
                edge_kind="import",
                line_number=node.lineno,
            )

    # ID: 855c7b0d-8fe4-4fd5-a7f9-c694ff9adce3
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        for alias in node.names:
            callee_raw = f"{module}.{alias.name}" if module else alias.name
            self._add_edge(
                callee_raw=callee_raw,
                edge_kind="import",
                line_number=node.lineno,
            )

    def _resolve_callee_id(self, callee_raw: str) -> str | None:
        """Multi-strategy callee resolution cascade."""
        hit = self._symbol_index.get(callee_raw)
        if hit:
            return hit

        hit = self._qualname_index.get(callee_raw)
        if hit:
            return hit

        if self._current_class and callee_raw.startswith(("self.", "cls.")):
            stripped = callee_raw.split(".", 1)[1]
            qualified = f"{self._current_class}.{stripped}"
            hit = self._qualname_index.get(qualified)
            if hit:
                return hit
            hit = self._qualname_index.get(stripped)
            if hit:
                return hit

        if "." in callee_raw:
            parts = callee_raw.split(".")
            for split in range(len(parts) - 1, 0, -1):
                module_path = "src/" + "/".join(parts[:split]) + ".py"
                qualname = ".".join(parts[split:])
                candidate = f"{module_path}::{qualname}"
                hit = self._symbol_index.get(candidate)
                if hit:
                    return hit
                candidate_no_src = "/".join(parts[:split]) + ".py::" + qualname
                hit = self._symbol_index.get(candidate_no_src)
                if hit:
                    return hit

        short = callee_raw.split(".")[-1]
        hit = self._shortname_index.get(short)
        if hit:
            return hit

        return None

    def _add_edge(
        self,
        callee_raw: str,
        edge_kind: str,
        line_number: int | None,
        caller_id: str | None = None,
    ) -> None:
        resolved_caller_id = caller_id or self._current_caller_id
        if resolved_caller_id is None:
            return

        callee_id = self._resolve_callee_id(callee_raw)
        caller_layer = self._layer
        callee_layer = _detect_layer_from_symbol(callee_raw)
        is_cross_layer = (
            caller_layer != callee_layer
            and callee_layer != "unknown"
            and caller_layer != "unknown"
        )
        is_external = not callee_raw.startswith(
            ("src.", "will.", "body.", "mind.", "shared.")
        )

        self._edges.append(
            {
                "caller_id": resolved_caller_id,
                "callee_id": callee_id,
                "callee_raw": callee_raw[:500],
                "edge_kind": edge_kind,
                "file_path": self._rel_path,
                "line_number": line_number,
                "is_cross_layer": is_cross_layer,
                "is_external": is_external,
                "crawl_run_id": self._crawl_run_id,
            }
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    """Compute SHA256 hex digest of a file."""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _path_to_module(rel_path: str) -> str:
    """Convert src/will/workers/foo.py → will.workers.foo (for layer detection only)"""
    p = rel_path.replace("/", ".").removesuffix(".py")
    if p.startswith("src."):
        p = p[4:]
    return p


def _detect_layer(rel_path: str) -> str:
    """Detect architectural layer from repo-relative file path."""
    for prefix, layer in _LAYER_MAP.items():
        if rel_path.startswith(prefix):
            return layer
    return "unknown"


def _detect_layer_from_symbol(symbol: str) -> str:
    """Detect layer from a dotted symbol/module name."""
    for prefix, layer in {
        "mind.": "mind",
        "body.": "body",
        "will.": "will",
        "shared.": "shared",
    }.items():
        if symbol.startswith(prefix):
            return layer
    return "unknown"


def _find_symbol_references(
    content: str,
    symbol_index: dict[str, str],
    rel_path: str,
    artifact_type: str,
) -> list[dict[str, Any]]:
    """
    Scan file text for mentions of known symbol qualnames.
    Returns link dicts ready for core.artifact_symbol_links insertion.
    """
    link_kind_map = {
        "doc": "documents",
        "test": "tests",
        "intent": "governs",
        "infra": "configures",
        "prompt": "references",
        "report": "references",
    }
    link_kind = link_kind_map.get(artifact_type, "references")
    links = []
    seen: set[str] = set()

    for symbol_path, symbol_id in symbol_index.items():
        qualname = symbol_path.split(":")[-1] if ":" in symbol_path else symbol_path
        if len(qualname) < 4:
            continue
        if qualname in content and symbol_id not in seen:
            seen.add(symbol_id)
            links.append(
                {
                    "symbol_id": symbol_id,
                    "link_kind": link_kind,
                    "confidence": 0.8,
                    "source": "name_match",
                }
            )

    return links
