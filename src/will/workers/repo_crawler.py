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
  3. For each .py file: extract AST call graph → core.symbol_calls.
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

from sqlalchemy import text

from shared.config import settings
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger
from shared.workers.base import Worker


logger = getLogger(__name__)

# ---------------------------------------------------------------------------
# Directory scope configuration
# ---------------------------------------------------------------------------

_CRAWL_SCOPES: list[tuple[str, str]] = [
    # (glob_pattern, artifact_type)
    ("src/**/*.py", "python"),  # Python — call graph only
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
        super().__init__()
        self._repo_root: Path = settings.REPO_PATH
        schedule = self._declaration.get("mandate", {}).get("schedule", {})
        self._max_interval: int = schedule.get("max_interval", 86400)
        self._glide_off: int = schedule.get(
            "glide_off", max(int(self._max_interval * 0.10), 10)
        )

    # ID: a1b2c3d4-e5f6-7890-1234-abcdef012345
    async def run_loop(self) -> None:
        """
        Continuous self-scheduling loop. Runs one crawl per max_interval seconds.
        Sanctuary calls this once on bootstrap.

        Never raises — exceptions are caught, logged, and posted to Blackboard.
        """
        import asyncio

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

            await asyncio.sleep(self._max_interval)

    # ID: b3c4d5e6-f7a8-9b0c-1234-567890abcdef
    async def run(self) -> None:
        """Execute one full repository crawl."""
        logger.info("RepoCrawlerWorker: starting crawl of %s", self._repo_root)

        crawl_run_id = uuid.uuid4()
        stats: dict[str, int] = {
            "files_scanned": 0,
            "files_changed": 0,
            "symbols_linked": 0,
            "edges_created": 0,
            "chunks_upserted": 0,
        }

        async with get_session() as session:
            # Open crawl run
            await session.execute(
                text(
                    """
                    INSERT INTO core.crawl_runs
                        (id, triggered_by, status, started_at)
                    VALUES
                        (:id, 'worker', 'running', now())
                """
                ),
                {"id": str(crawl_run_id)},
            )
            await session.commit()

            try:
                # Load existing symbol index (symbol_path → uuid)
                symbol_index = await self._load_symbol_index(session)

                # Load existing artifact hashes for skip-if-unchanged
                existing_hashes = await self._load_artifact_hashes(session)

                # Walk all scopes
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
                                # Python: extract call graph edges
                                changed = await self._process_python_file(
                                    session=session,
                                    file_path=file_path,
                                    rel_path=rel_path,
                                    content_hash=content_hash,
                                    existing_hashes=existing_hashes,
                                    symbol_index=symbol_index,
                                    crawl_run_id=crawl_run_id,
                                    stats=stats,
                                )
                            else:
                                # Non-Python: register artifact + cross-reference
                                changed = await self._process_artifact_file(
                                    session=session,
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

                await session.commit()

                # Close crawl run as completed
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
                    {"id": str(crawl_run_id), **stats},
                )
                await session.commit()

            except Exception as exc:
                await session.execute(
                    text(
                        """
                        UPDATE core.crawl_runs
                        SET status = 'failed', error_message = :err, finished_at = now()
                        WHERE id = :id
                    """
                    ),
                    {"id": str(crawl_run_id), "err": str(exc)},
                )
                await session.commit()
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
    # Python file processing — call graph extraction
    # -------------------------------------------------------------------------

    # ID: c4d5e6f7-a8b9-0c1d-2e3f-4a5b6c7d8e9f
    async def _process_python_file(
        self,
        session: Any,
        file_path: Path,
        rel_path: str,
        content_hash: str,
        existing_hashes: dict[str, str],
        symbol_index: dict[str, str],
        crawl_run_id: uuid.UUID,
        stats: dict[str, int],
    ) -> bool:
        """Extract AST call graph edges from a Python file."""
        if existing_hashes.get(rel_path) == content_hash:
            return False

        source = file_path.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(source)
        except SyntaxError:
            logger.warning("RepoCrawlerWorker: syntax error in %s, skipping", rel_path)
            return False

        layer = _detect_layer(rel_path)
        extractor = _CallGraphExtractor(
            rel_path=rel_path,  # used directly as symbol_path prefix
            layer=layer,
            symbol_index=symbol_index,
            crawl_run_id=crawl_run_id,
        )
        edges = extractor.extract(tree)

        if edges:
            # Delete stale edges for this file before inserting fresh ones
            await session.execute(
                text(
                    """
                    DELETE FROM core.symbol_calls
                    WHERE file_path = :file_path
                      AND crawl_run_id != :crawl_run_id
                """
                ),
                {"file_path": rel_path, "crawl_run_id": str(crawl_run_id)},
            )

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
            stats["edges_created"] += len(edges)

        return True

    # -------------------------------------------------------------------------
    # Non-Python artifact processing
    # -------------------------------------------------------------------------

    # ID: d5e6f7a8-b9c0-1d2e-3f4a-5b6c7d8e9f0a
    async def _process_artifact_file(
        self,
        session: Any,
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
                    content_hash     = EXCLUDED.content_hash,
                    artifact_type    = EXCLUDED.artifact_type,
                    qdrant_collection = EXCLUDED.qdrant_collection,
                    last_crawled_at  = EXCLUDED.last_crawled_at,
                    crawl_run_id     = EXCLUDED.crawl_run_id
            """
            ),
            {
                "file_path": rel_path,
                "artifact_type": artifact_type,
                "content_hash": content_hash,
                "qdrant_collection": qdrant_collection,
                "crawl_run_id": str(crawl_run_id),
            },
        )

        if changed:
            # Get the artifact id we just upserted
            result = await session.execute(
                text("SELECT id FROM core.repo_artifacts WHERE file_path = :fp"),
                {"fp": rel_path},
            )
            row = result.fetchone()
            if row:
                artifact_id = str(row[0])
                content = file_path.read_text(encoding="utf-8", errors="replace")
                links = _find_symbol_references(
                    content, symbol_index, rel_path, artifact_type
                )
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
                stats["symbols_linked"] += len(links)

        return changed

    async def _load_symbol_index(self, session: Any) -> dict[str, str]:
        """Load symbol_path → id mapping from core.symbols."""
        result = await session.execute(
            text("SELECT symbol_path, id FROM core.symbols WHERE state != 'deprecated'")
        )
        return {row[0]: str(row[1]) for row in result.fetchall()}

    # ID: f7a8b9c0-d1e2-3f4a-5b6c-7d8e9f0a1b2c
    async def _load_artifact_hashes(self, session: Any) -> dict[str, str]:
        """Load file_path → content_hash for skip-if-unchanged logic."""
        result = await session.execute(
            text("SELECT file_path, content_hash FROM core.repo_artifacts")
        )
        return {row[0]: row[1] for row in result.fetchall()}


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
        """
        Multi-strategy callee resolution cascade.

        Tries each strategy in order and returns the first match.
        """
        # Strategy 1: direct symbol_path key (almost never hits in practice,
        # kept for completeness and future import-alias resolution)
        hit = self._symbol_index.get(callee_raw)
        if hit:
            return hit

        # Strategy 2: qualname match — the most common internal hit.
        # e.g. callee_raw="RepoCrawlerWorker.run" → qualname_index lookup
        hit = self._qualname_index.get(callee_raw)
        if hit:
            return hit

        # Strategy 3: self./cls. stripping + current-class qualification.
        # e.g. "self.run" inside class RepoCrawlerWorker → "RepoCrawlerWorker.run"
        if self._current_class and callee_raw.startswith(("self.", "cls.")):
            stripped = callee_raw.split(".", 1)[1]
            qualified = f"{self._current_class}.{stripped}"
            hit = self._qualname_index.get(qualified)
            if hit:
                return hit
            # Also try the short name alone (handles inherited methods)
            hit = self._qualname_index.get(stripped)
            if hit:
                return hit

        # Strategy 4: module dotted path → file path conversion.
        # e.g. "will.workers.repo_crawler.RepoCrawlerWorker"
        #   → "src/will/workers/repo_crawler.py::RepoCrawlerWorker"
        # Try progressively shorter module prefixes (rightmost segment = qualname)
        if "." in callee_raw:
            parts = callee_raw.split(".")
            for split in range(len(parts) - 1, 0, -1):
                module_path = "src/" + "/".join(parts[:split]) + ".py"
                qualname = ".".join(parts[split:])
                candidate = f"{module_path}::{qualname}"
                hit = self._symbol_index.get(candidate)
                if hit:
                    return hit
                # Also try without 'src/' prefix (handles relative imports)
                candidate_no_src = "/".join(parts[:split]) + ".py::" + qualname
                hit = self._symbol_index.get(candidate_no_src)
                if hit:
                    return hit

        # Strategy 5: short name unique match — only when exactly one symbol
        # in the entire codebase has this short name (avoids false positives).
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
            return  # Can't record edge without a known caller

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
        # Match on the qualname part (after the colon)
        qualname = symbol_path.split(":")[-1] if ":" in symbol_path else symbol_path
        if len(qualname) < 4:  # skip trivially short names
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
