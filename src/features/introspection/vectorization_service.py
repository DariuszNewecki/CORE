# src/features/introspection/vectorization_service.py

"""
High-performance orchestrator for capability vectorization.
This version reads its work queue directly from the database, treating it as the
single source of truth for the symbol catalog. It intelligently re-vectorizes
symbols when their source code has been modified by comparing structural hashes.
"""

from __future__ import annotations

import ast
import asyncio
import hashlib
from pathlib import Path

from rich.console import Console
from rich.progress import track
from sqlalchemy import text

from services.clients.qdrant_client import QdrantService
from services.database.session_manager import get_session
from shared.config import settings
from shared.context import CoreContext
from shared.logger import getLogger
from shared.utils.embedding_utils import normalize_text
from will.orchestration.cognitive_service import CognitiveService

logger = getLogger(__name__)
console = Console()


async def _fetch_all_public_symbols_from_db() -> list[dict]:
    """Queries the database for all public symbols."""
    # SIMPLIFIED: We no longer need the LEFT JOIN here. We'll get links separately.
    async with get_session() as session:
        stmt = text(
            """
            SELECT id, symbol_path, module, fingerprint AS structural_hash
            FROM core.symbols
            WHERE is_public = TRUE
            """
        )
        result = await session.execute(stmt)
        return [dict(row._mapping) for row in result]


# --- START OF NEW HELPER FUNCTION ---
async def _fetch_existing_vector_links() -> dict[str, str]:
    """Fetches all existing symbol_id -> vector_id mappings from the database."""
    async with get_session() as session:
        result = await session.execute(
            text("SELECT symbol_id, vector_id FROM core.symbol_vector_links")
        )
        # Key: symbol_id (str), Value: vector_id (str)
        return {str(row.symbol_id): str(row.vector_id) for row in result}


# --- END OF NEW HELPER FUNCTION ---


async def _get_stored_vector_hashes(qdrant_service: QdrantService) -> dict[str, str]:
    """Fetches all point IDs and their content hashes from Qdrant."""
    hashes = {}
    offset = None
    try:
        while True:
            points, next_offset = await qdrant_service.client.scroll(
                collection_name=qdrant_service.collection_name,
                limit=1000,
                offset=offset,
                with_payload=["content_sha256"],
                with_vectors=False,
            )
            for point in points:
                if point.payload and "content_sha256" in point.payload:
                    hashes[str(point.id)] = point.payload.get("content_sha256")
            if not next_offset:
                break
            offset = next_offset
    except Exception as e:
        logger.warning(
            f"Could not retrieve hashes from Qdrant, will re-vectorize all. Error: {e}"
        )
    return hashes


def _get_source_code(file_path: Path, symbol_path: str) -> str | None:
    """Extracts the source code of a specific symbol from a file using AST."""
    if not file_path.exists():
        logger.warning(
            f"Source file not found for symbol {symbol_path} at path {file_path}"
        )
        return None
    content = file_path.read_text("utf-8", errors="ignore")
    try:
        tree = ast.parse(content)
        target_name = symbol_path.split("::")[-1]
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if hasattr(node, "name") and node.name == target_name:
                    return ast.get_source_segment(content, node)
    except Exception:
        return None
    return None


async def _process_vectorization_task(
    task: dict,
    cognitive_service: CognitiveService,
    qdrant_service: QdrantService,
    failure_log_path: Path,
) -> str | None:
    """Processes a single symbol: gets embedding and upserts to Qdrant. Returns Qdrant point ID on success."""
    try:
        vector = await cognitive_service.get_embedding_for_code(task["source_code"])
        if not vector:
            raise ValueError("Embedding service returned None")
        point_id = str(task["id"])
        payload_data = {
            "source_path": task["file_path_str"],
            "source_type": "code",
            "chunk_id": task["symbol_path"],
            "content_sha256": task["code_hash"],
            "language": "python",
            "symbol": task["symbol_path"],
            "capability_tags": [point_id],
        }
        await qdrant_service.upsert_capability_vector(
            point_id_str=point_id, vector=vector, payload_data=payload_data
        )
        return point_id
    except Exception as e:
        logger.error(f"Failed to process symbol '{task['symbol_path']}': {e}")
        failure_log_path.parent.mkdir(parents=True, exist_ok=True)
        with failure_log_path.open("a", encoding="utf-8") as f:
            f.write(f"vectorization_error\t{task['symbol_path']}\t{e}\n")
        return None


async def _update_db_after_vectorization(updates: list[dict]):
    """Creates links in symbol_vector_links and updates the last_embedded timestamp."""
    if not updates:
        return
    async with get_session() as session:
        async with session.begin():
            await session.execute(
                text(
                    """
                    INSERT INTO core.symbol_vector_links (symbol_id, vector_id, embedding_model, embedding_version, created_at)
                    VALUES (:symbol_id, :vector_id, :embedding_model, :embedding_version, NOW())
                    ON CONFLICT (symbol_id) DO UPDATE SET
                        vector_id = EXCLUDED.vector_id,
                        embedding_model = EXCLUDED.embedding_model,
                        embedding_version = EXCLUDED.embedding_version,
                        created_at = NOW();
                """
                ),
                updates,
            )
            await session.execute(
                text(
                    "UPDATE core.symbols SET last_embedded = NOW() WHERE id = ANY(:symbol_ids)"
                ),
                {"symbol_ids": [u["symbol_id"] for u in updates]},
            )
    console.print(f"   -> Updated {len(updates)} records in the database.")


# --- START OF REFACTOR ---
# ID: c1f403a3-cc28-450f-a182-b368e32abca5
async def run_vectorize(
    context: CoreContext, dry_run: bool = False, force: bool = False
):
    """
    The main orchestration logic for vectorizing capabilities based on the database.
    """
    console.print("[bold cyan]🚀 Starting Database-Driven Vectorization...[/bold cyan]")
    failure_log_path = settings.REPO_PATH / "logs" / "vectorization_failures.log"

    # 1. Fetch all state concurrently
    all_symbols, existing_links, stored_vector_hashes = await asyncio.gather(
        _fetch_all_public_symbols_from_db(),
        _fetch_existing_vector_links(),
        _get_stored_vector_hashes(context.qdrant_service),
    )

    cognitive_service = context.cognitive_service
    qdrant_service = context.qdrant_service
    await qdrant_service.ensure_collection()

    tasks = []
    for symbol in all_symbols:
        symbol_id_str = str(symbol["id"])

        # 2. Get source code and calculate its current hash
        module_path = symbol["module"]
        file_path_str = "src/" + module_path.replace(".", "/") + ".py"
        file_path = settings.REPO_PATH / file_path_str
        source_code = _get_source_code(file_path, symbol["symbol_path"])
        if not source_code:
            continue

        normalized_code = normalize_text(source_code)
        current_code_hash = hashlib.sha256(normalized_code.encode("utf-8")).hexdigest()

        # 3. Determine if vectorization is needed using explicit logic
        needs_vectorization = False
        if force:
            needs_vectorization = True
        elif symbol_id_str not in existing_links:
            # Case A: Symbol is new and has never been vectorized.
            needs_vectorization = True
        else:
            # Case B: Symbol has been vectorized. Check if its content has changed.
            vector_id = existing_links[symbol_id_str]
            stored_hash = stored_vector_hashes.get(vector_id)
            if current_code_hash != stored_hash:
                needs_vectorization = True

        if needs_vectorization:
            task_data = {
                **symbol,
                "source_code": normalized_code,
                "code_hash": current_code_hash,
                "file_path_str": str(file_path.relative_to(settings.REPO_PATH)),
            }
            tasks.append(task_data)

    if not tasks:
        console.print(
            "[bold green]✅ Vector knowledge base is already up-to-date.[/bold green]"
        )
        return

    console.print(f"   -> Found {len(tasks)} symbols needing vectorization.")
    if dry_run:
        console.print(
            "\n[bold yellow]💧 Dry Run: No embeddings will be generated or stored.[/bold yellow]"
        )
        for task in tasks[:5]:
            console.print(f"   -> Would vectorize: {task['symbol_path']}")
        if len(tasks) > 5:
            console.print(f"   -> ... and {len(tasks) - 5} more.")
        return

    updates_to_db = []
    for task in track(tasks, description="Vectorizing symbols..."):
        point_id = await _process_vectorization_task(
            task, cognitive_service, qdrant_service, failure_log_path
        )
        if point_id:
            updates_to_db.append(
                {
                    "symbol_id": task["id"],
                    "vector_id": point_id,
                    "embedding_model": settings.LOCAL_EMBEDDING_MODEL_NAME,
                    "embedding_version": 1,
                }
            )

    await _update_db_after_vectorization(updates_to_db)
    console.print(
        f"\n[bold green]✅ Vectorization complete. Processed {len(updates_to_db)}/{len(tasks)} symbols.[/bold green]"
    )
    if len(updates_to_db) < len(tasks):
        console.print(
            f"[bold red]   -> {len(tasks) - len(updates_to_db)} failures logged to {failure_log_path}[/bold red]"
        )
