# src/body/services/crawl_service.py
"""
CrawlService - Data-access layer and crawl orchestration for repository crawl tables.

Covers all DB operations from RepoCrawlerWorker:
  - core.crawl_runs            (open / close)
  - core.repo_artifacts        (upsert python + non-python, load hashes, fetch id)
  - core.symbol_calls          (delete stale, batch insert)
  - core.artifact_symbol_links (batch insert)
  - core.symbols               (load symbol index)

Also provides run_crawl() — full crawl orchestration extracted from
RepoCrawlerWorker.run() — so Body-layer callers can drive a crawl without
importing any Will worker class.

Transaction note: Each service method opens its own session. Callers are
responsible for any required savepoint wrapping.
"""

from __future__ import annotations

import ast
import hashlib
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import text

from shared.logger import getLogger


logger = getLogger(__name__)


# ---------------------------------------------------------------------------
# Crawl scope configuration (moved from will.workers.repo_crawler)
# ---------------------------------------------------------------------------

_CRAWL_SCOPES: list[tuple[str, str]] = [
    ("src/**/*.py", "python"),
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
    "python": "core-code",
    "doc": "core-docs",
    "test": "core-tests",
    "prompt": "core-prompts",
    "report": "core-reports",
    "intent": "core-patterns",
    "infra": "core-docs",
}

_LAYER_MAP: dict[str, str] = {
    "src/mind": "mind",
    "src/body": "body",
    "src/will": "will",
    "src/shared": "shared",
}


# ---------------------------------------------------------------------------
# Pure crawl helpers (moved from will.workers.repo_crawler)
# ---------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    """Compute SHA256 hex digest of a file."""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _path_to_module(rel_path: str) -> str:
    """Convert src/will/workers/foo.py → will.workers.foo (for layer detection only)."""
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


# ---------------------------------------------------------------------------
# AST Call Graph Extractor (moved from will.workers.repo_crawler)
# ---------------------------------------------------------------------------


class _CallGraphExtractor(ast.NodeVisitor):
    """
    Extracts directed call graph edges from a Python AST.
    Produces edge dicts ready for insertion into core.symbol_calls.

    symbol_path format matches DB: src/path/to/file.py::ClassName.method_name

    Resolution cascade (applied in order until a match is found):
      1. Direct key match against symbol_index
      2. Qualname match: symbol_index key suffix after '::'
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

        self._qualname_index: dict[str, str] = {}
        _shortname_bucket: dict[str, list[str]] = {}

        for symbol_path, symbol_id in symbol_index.items():
            if "::" not in symbol_path:
                continue
            qualname = symbol_path.split("::", 1)[1]
            self._qualname_index[qualname] = symbol_id
            short = qualname.split(".")[-1]
            _shortname_bucket.setdefault(short, []).append(symbol_id)

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


# ID: 5f469d78-73c8-46c8-8b6c-d0b0c5cd9ed7
class CrawlService:
    """
    Body layer service. Exposes named methods for every DB operation
    performed by RepoCrawlerWorker across crawl_runs, repo_artifacts,
    symbol_calls, artifact_symbol_links, and symbols.

    Also provides run_crawl() for driving the full crawl pipeline from
    Body-layer callers without importing any Will worker class.
    """

    # ------------------------------------------------------------------
    # crawl_runs lifecycle
    # ------------------------------------------------------------------

    # ID: 42f4f41d-ada7-4662-b4b2-9c2a7ba7c800
    async def open_crawl_run(self, crawl_run_id: str) -> None:
        """
        Insert a new crawl_run record in 'running' status.

        Covers:
          - RepoCrawlerWorker.run — initial INSERT into core.crawl_runs
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO core.crawl_runs (id, triggered_by, status, started_at)
                    VALUES (cast(:id as uuid), 'worker', 'running', now())
                    """
                ),
                {"id": crawl_run_id},
            )
            await session.commit()

    # ID: ac48548f-ec42-442a-81df-4dd8255593c2
    async def close_crawl_run_completed(
        self, crawl_run_id: str, stats: dict[str, int]
    ) -> None:
        """
        Mark a crawl_run as completed and record final stats.

        Covers:
          - RepoCrawlerWorker.run — UPDATE core.crawl_runs SET status = 'completed'
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            await session.execute(
                text(
                    """
                    UPDATE core.crawl_runs SET
                        status          = 'completed',
                        files_scanned   = :files_scanned,
                        files_changed   = :files_changed,
                        symbols_linked  = :symbols_linked,
                        edges_created   = :edges_created,
                        chunks_upserted = :chunks_upserted,
                        finished_at     = now()
                    WHERE id = :id
                    """
                ),
                {"id": crawl_run_id, **stats},
            )
            await session.commit()

    # ID: 845ddf95-4bc1-45b7-bc28-743637178893
    async def close_crawl_run_failed(self, crawl_run_id: str, error: str) -> None:
        """
        Mark a crawl_run as failed and record the error message.

        Covers:
          - RepoCrawlerWorker.run — UPDATE core.crawl_runs SET status = 'failed'
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            await session.execute(
                text(
                    """
                    UPDATE core.crawl_runs
                    SET status = 'failed', error_message = :err, finished_at = now()
                    WHERE id = :id
                    """
                ),
                {"id": crawl_run_id, "err": error},
            )
            await session.commit()

    # ------------------------------------------------------------------
    # repo_artifacts
    # ------------------------------------------------------------------

    # ID: 8729f486-acb0-46b1-a69a-404257979ec8
    async def upsert_python_artifact(
        self,
        file_path: str,
        content_hash: str,
        qdrant_collection: str,
        crawl_run_id: str,
    ) -> None:
        """
        Upsert a Python source file into core.repo_artifacts.
        Resets chunk_count to 0 only when the content hash changed,
        signalling RepoEmbedderWorker to re-embed the file.

        Covers:
          - RepoCrawlerWorker._process_python_file — repo_artifacts upsert
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO core.repo_artifacts
                        (id, file_path, artifact_type, content_hash,
                         qdrant_collection, chunk_count, last_crawled_at, crawl_run_id)
                    VALUES
                        (gen_random_uuid(), :file_path, :artifact_type, :content_hash,
                         :qdrant_collection, 0, now(), cast(:crawl_run_id as uuid))
                    ON CONFLICT (file_path) DO UPDATE SET
                        content_hash      = EXCLUDED.content_hash,
                        artifact_type     = EXCLUDED.artifact_type,
                        qdrant_collection = EXCLUDED.qdrant_collection,
                        chunk_count       = CASE
                            WHEN repo_artifacts.content_hash != EXCLUDED.content_hash
                            THEN 0
                            ELSE repo_artifacts.chunk_count
                        END,
                        last_crawled_at   = EXCLUDED.last_crawled_at,
                        crawl_run_id      = EXCLUDED.crawl_run_id
                    """
                ),
                {
                    "file_path": file_path,
                    "artifact_type": "python",
                    "content_hash": content_hash,
                    "qdrant_collection": qdrant_collection,
                    "crawl_run_id": crawl_run_id,
                },
            )
            await session.commit()

    # ID: e40bf578-0c6f-4f7f-8c00-84ffb706cb39
    async def upsert_artifact(
        self,
        file_path: str,
        artifact_type: str,
        content_hash: str,
        qdrant_collection: str | None,
        crawl_run_id: str,
    ) -> None:
        """
        Upsert a non-Python artifact into core.repo_artifacts.

        Covers:
          - RepoCrawlerWorker._process_artifact_file — repo_artifacts upsert
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO core.repo_artifacts
                        (id, file_path, artifact_type, content_hash,
                         qdrant_collection, last_crawled_at, crawl_run_id)
                    VALUES
                        (gen_random_uuid(), :file_path, :artifact_type, :content_hash,
                         :qdrant_collection, now(), cast(:crawl_run_id as uuid))
                    ON CONFLICT (file_path) DO UPDATE SET
                        content_hash      = EXCLUDED.content_hash,
                        artifact_type     = EXCLUDED.artifact_type,
                        qdrant_collection = EXCLUDED.qdrant_collection,
                        last_crawled_at   = EXCLUDED.last_crawled_at,
                        crawl_run_id      = EXCLUDED.crawl_run_id
                    """
                ),
                {
                    "file_path": file_path,
                    "artifact_type": artifact_type,
                    "content_hash": content_hash,
                    "qdrant_collection": qdrant_collection,
                    "crawl_run_id": crawl_run_id,
                },
            )
            await session.commit()

    # ID: f0cfa2b8-53fb-4b42-90d4-233e952a26e6
    async def fetch_artifact_id(self, file_path: str) -> str | None:
        """
        Return the UUID of a repo_artifact by file_path, or None if absent.

        Covers:
          - RepoCrawlerWorker._process_artifact_file — SELECT id FROM core.repo_artifacts
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            result = await session.execute(
                text("SELECT id FROM core.repo_artifacts WHERE file_path = :fp"),
                {"fp": file_path},
            )
            row = result.fetchone()
            return str(row[0]) if row else None

    # ID: 588ffa06-2c09-4fa3-9eff-4ed94428ae87
    async def load_artifact_hashes(self) -> dict[str, str]:
        """
        Return file_path → content_hash for all registered artifacts.
        Used for skip-if-unchanged logic during crawl.

        Covers:
          - RepoCrawlerWorker._load_artifact_hashes
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            result = await session.execute(
                text("SELECT file_path, content_hash FROM core.repo_artifacts")
            )
            return {row[0]: row[1] for row in result.fetchall()}

    # ------------------------------------------------------------------
    # symbol_calls
    # ------------------------------------------------------------------

    # ID: 110cc97e-1872-434f-ae33-436802b9a63f
    async def delete_stale_symbol_calls(
        self, file_path: str, crawl_run_id: str
    ) -> None:
        """
        Delete symbol_calls edges for *file_path* from any previous crawl run.

        Covers:
          - RepoCrawlerWorker._process_python_file — DELETE FROM core.symbol_calls
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            await session.execute(
                text(
                    """
                    DELETE FROM core.symbol_calls
                    WHERE file_path = :file_path
                      AND crawl_run_id != :crawl_run_id
                    """
                ),
                {"file_path": file_path, "crawl_run_id": crawl_run_id},
            )
            await session.commit()

    # ID: 92277ff6-286d-41f0-aaaf-768350e04426
    async def insert_symbol_calls(self, edges: list[dict[str, Any]]) -> None:
        """
        Batch-insert call graph edges into core.symbol_calls in a single
        transaction. Silently ignores duplicates (ON CONFLICT DO NOTHING).

        Each edge dict must contain the keys produced by _CallGraphExtractor:
        caller_id, callee_id, callee_raw, edge_kind, file_path, line_number,
        is_cross_layer, is_external, crawl_run_id.

        Covers:
          - RepoCrawlerWorker._process_python_file — INSERT INTO core.symbol_calls loop
        """
        from body.services.service_registry import ServiceRegistry

        if not edges:
            return

        async with ServiceRegistry.session() as session:
            async with session.begin():
                for edge in edges:
                    await session.execute(
                        text(
                            """
                            INSERT INTO core.symbol_calls
                                (id, caller_id, callee_id, callee_raw, edge_kind,
                                 file_path, line_number, is_cross_layer, is_external,
                                 crawl_run_id, created_at)
                            VALUES
                                (gen_random_uuid(),
                                 cast(:caller_id as uuid),
                                 cast(:callee_id as uuid),
                                 :callee_raw, :edge_kind,
                                 :file_path, :line_number,
                                 :is_cross_layer, :is_external,
                                 cast(:crawl_run_id as uuid),
                                 now())
                            ON CONFLICT DO NOTHING
                            """
                        ),
                        edge,
                    )

    # ------------------------------------------------------------------
    # artifact_symbol_links
    # ------------------------------------------------------------------

    # ID: a75c9602-8208-4608-897e-a950e8016cdf
    async def insert_artifact_symbol_links(
        self, artifact_id: str, links: list[dict[str, Any]]
    ) -> None:
        """
        Batch-insert artifact→symbol cross-reference links in a single
        transaction. Silently ignores duplicates (ON CONFLICT DO NOTHING).

        Each link dict must contain: symbol_id, link_kind, confidence, source.

        Covers:
          - RepoCrawlerWorker._process_artifact_file — INSERT INTO core.artifact_symbol_links loop
        """
        from body.services.service_registry import ServiceRegistry

        if not links:
            return

        async with ServiceRegistry.session() as session:
            async with session.begin():
                for link in links:
                    await session.execute(
                        text(
                            """
                            INSERT INTO core.artifact_symbol_links
                                (id, artifact_id, symbol_id, link_kind, confidence, source)
                            VALUES
                                (gen_random_uuid(),
                                 cast(:artifact_id as uuid),
                                 cast(:symbol_id as uuid),
                                 :link_kind, :confidence, :source)
                            ON CONFLICT DO NOTHING
                            """
                        ),
                        {"artifact_id": artifact_id, **link},
                    )

    # ------------------------------------------------------------------
    # symbols (read-only)
    # ------------------------------------------------------------------

    # ID: 1ef33e95-b0fc-425b-9152-5ba256334624
    async def load_symbol_index(self) -> dict[str, str]:
        """
        Return symbol_path → id mapping for all non-deprecated symbols.
        Used to resolve call graph callee IDs during crawl.

        Covers:
          - RepoCrawlerWorker._load_symbol_index
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            result = await session.execute(
                text(
                    "SELECT symbol_path, id FROM core.symbols WHERE state != 'deprecated'"
                )
            )
            return {row[0]: str(row[1]) for row in result.fetchall()}

    # ------------------------------------------------------------------
    # Crawl orchestration
    # ------------------------------------------------------------------

    # ID: d4e5f6a7-b8c9-0123-def0-123456789012
    async def run_crawl(
        self, repo_root: Path, cognitive_service: Any = None
    ) -> dict[str, int]:
        """
        Full crawl orchestration: walk all declared repo scopes, register
        artifacts in core.repo_artifacts, extract AST call-graph edges into
        core.symbol_calls, and cross-reference non-Python artifacts in
        core.artifact_symbol_links.

        cognitive_service is accepted for interface consistency and future use;
        the current crawl is purely structural and does not invoke any LLM or
        embedding service.

        Returns stats dict with keys: files_scanned, files_changed,
        symbols_linked, edges_created, chunks_upserted.
        """
        logger.info("CrawlService.run_crawl: starting crawl pass")
        crawl_run_id = uuid.uuid4()
        stats: dict[str, int] = {
            "files_scanned": 0,
            "files_changed": 0,
            "symbols_linked": 0,
            "edges_created": 0,
            "chunks_upserted": 0,
        }

        await self.open_crawl_run(str(crawl_run_id))
        try:
            symbol_index = await self.load_symbol_index()
            existing_hashes = await self.load_artifact_hashes()

            for glob_pattern, artifact_type in _CRAWL_SCOPES:
                for file_path in sorted(repo_root.glob(glob_pattern)):
                    if file_path.is_symlink():
                        continue
                    rel_path = str(file_path.relative_to(repo_root))
                    stats["files_scanned"] += 1
                    try:
                        content_hash = _sha256(file_path)
                        if artifact_type == "python":
                            changed = await self._crawl_python_file(
                                file_path=file_path,
                                rel_path=rel_path,
                                content_hash=content_hash,
                                existing_hashes=existing_hashes,
                                symbol_index=symbol_index,
                                crawl_run_id=crawl_run_id,
                                stats=stats,
                            )
                        else:
                            changed = await self._crawl_artifact_file(
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
                            "CrawlService.run_crawl: error processing %s: %s",
                            rel_path,
                            exc,
                        )

            await self.close_crawl_run_completed(str(crawl_run_id), stats)
        except Exception as exc:
            await self.close_crawl_run_failed(str(crawl_run_id), str(exc))
            raise

        logger.info("CrawlService.run_crawl: crawl complete — %s", stats)
        return stats

    async def _crawl_python_file(
        self,
        file_path: Path,
        rel_path: str,
        content_hash: str,
        existing_hashes: dict[str, str],
        symbol_index: dict[str, str],
        crawl_run_id: uuid.UUID,
        stats: dict[str, int],
    ) -> bool:
        """Register a Python artifact and extract call-graph edges on change."""
        await self.upsert_python_artifact(
            rel_path, content_hash, _QDRANT_COLLECTION_MAP["python"], str(crawl_run_id)
        )
        if existing_hashes.get(rel_path) == content_hash:
            return False

        source = file_path.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(source)
        except SyntaxError:
            logger.warning(
                "CrawlService.run_crawl: syntax error in %s, skipping", rel_path
            )
            return True  # registered in artifacts; no call graph

        extractor = _CallGraphExtractor(
            rel_path=rel_path,
            layer=_detect_layer(rel_path),
            symbol_index=symbol_index,
            crawl_run_id=crawl_run_id,
        )
        edges = extractor.extract(tree)
        if edges:
            await self.delete_stale_symbol_calls(rel_path, str(crawl_run_id))
            await self.insert_symbol_calls(edges)
            stats["edges_created"] += len(edges)
        return True

    async def _crawl_artifact_file(
        self,
        file_path: Path,
        rel_path: str,
        content_hash: str,
        artifact_type: str,
        existing_hashes: dict[str, str],
        symbol_index: dict[str, str],
        crawl_run_id: uuid.UUID,
        stats: dict[str, int],
    ) -> bool:
        """Register a non-Python artifact and cross-reference symbols on change."""
        changed = existing_hashes.get(rel_path) != content_hash
        await self.upsert_artifact(
            rel_path,
            artifact_type,
            content_hash,
            _QDRANT_COLLECTION_MAP.get(artifact_type),
            str(crawl_run_id),
        )
        if not changed:
            return False

        artifact_id = await self.fetch_artifact_id(rel_path)
        if artifact_id:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            links = _find_symbol_references(
                content, symbol_index, rel_path, artifact_type
            )
            await self.insert_artifact_symbol_links(artifact_id, links)
            stats["symbols_linked"] += len(links)
        return True
