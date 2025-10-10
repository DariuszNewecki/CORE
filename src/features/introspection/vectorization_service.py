# src/features/introspection/vectorization_service.py
"""
High-performance orchestrator for capability vectorization.
This version reads its work queue directly from the database, treating it as the
single source of truth for the symbol catalog. It intelligently re-vectorizes
symbols when their source code has been modified.
"""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import Dict, List, Optional

from core.cognitive_service import CognitiveService
from rich.console import Console
from rich.progress import track
from services.clients.qdrant_client import QdrantService
from services.database.session_manager import get_session
from shared.config import settings
from shared.logger import getLogger
from shared.utils.embedding_utils import normalize_text
from sqlalchemy import text

log = getLogger("core_admin.knowledge.orchestrator")
console = Console()


async def _fetch_symbols_from_db() -> List[Dict]:
    """Queries the database for symbols needing vectorization using the v_symbols_needing_embedding view."""
    async with get_session() as session:
        stmt = text(
            """
            SELECT id, symbol_path, module, fingerprint AS structural_hash, vector_id
            FROM core.v_symbols_needing_embedding
            """
        )
        result = await session.execute(stmt)
        # We now return the raw module path from the DB
        return [dict(row._mapping) for row in result]


def _get_source_code(file_path: Path, symbol_path: str) -> Optional[str]:
    """Extracts the source code of a specific symbol from a file using AST."""
    if not file_path.exists():
        log.warning(
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
    task: Dict,
    cognitive_service: CognitiveService,
    qdrant_service: QdrantService,
    failure_log_path: Path,
) -> Optional[str]:
    """Processes a single symbol: gets embedding and upserts to Qdrant. Returns Qdrant point ID on success."""
    try:
        vector = await cognitive_service.get_embedding_for_code(task["source_code"])
        if not vector:
            raise ValueError("Embedding service returned None")

        # The ID for Qdrant and Postgres MUST be the same string representation.
        # The symbol's `id` from the database is a UUID object. We cast it to a string here.
        vector_id_str = str(task["id"])

        payload_data = {
            "source_path": task[
                "file_path_str"
            ],  # Use the string representation of the file path
            "source_type": "code",
            "chunk_id": task["symbol_path"],
            "content_sha256": task["code_hash"],
            "language": "python",
            "symbol": task["symbol_path"],
            # Use the stringified UUID in the payload for traceability
            "capability_tags": [vector_id_str],
        }
        # The upsert function now internally uses this string ID to create the point.
        # We don't need its return value because we already know the ID.
        await qdrant_service.upsert_capability_vector(
            point_id_str=vector_id_str,  # Pass the ID explicitly
            vector=vector,
            payload_data=payload_data,
        )

        # Return the same string ID we used, ensuring consistency.
        return vector_id_str
    except Exception as e:
        log.error(f"Failed to process symbol '{task['symbol_path']}': {e}")
        failure_log_path.parent.mkdir(parents=True, exist_ok=True)
        with failure_log_path.open("a", encoding="utf-8") as f:
            f.write(f"vectorization_error\t{task['symbol_path']}\t{e}\n")
        return None


async def _update_symbols_in_db(updates: List[Dict]):
    """Bulk updates the vector_id and embedding metadata for symbols in the database."""
    if not updates:
        return
    async with get_session() as session:
        async with session.begin():
            await session.execute(
                text(
                    """
                    UPDATE core.symbols SET
                        vector_id = :vector_id,
                        last_embedded = NOW(),
                        embedding_model = :embedding_model,
                        embedding_version = :embedding_version,
                        updated_at = NOW()
                    WHERE id = :id
                """
                ),
                updates,
            )
        await session.commit()
    console.print(f"   -> Updated {len(updates)} vector IDs in the database.")


# ID: 3bccc577-acce-4c72-81f4-ab48119d43c8
async def run_vectorize(
    cognitive_service: CognitiveService,
    dry_run: bool = False,
    force: bool = False,
):
    """
    The main orchestration logic for vectorizing capabilities based on the database.
    """
    console.print("[bold cyan]🚀 Starting Database-Driven Vectorization...[/bold cyan]")
    failure_log_path = settings.REPO_PATH / "logs" / "vectorization_failures.log"
    symbols_to_process = await _fetch_symbols_from_db()

    if force:
        console.print(
            "[bold yellow]--force flag detected: Re-vectorizing ALL symbols.[/bold yellow]"
        )
        async with get_session() as session:
            result = await session.execute(
                text(
                    "SELECT id, symbol_path, module, fingerprint AS structural_hash, vector_id FROM core.symbols WHERE is_public = TRUE"
                )
            )
            symbols_to_process = [dict(row._mapping) for row in result]

    if not symbols_to_process:
        console.print(
            "[bold green]✅ Vector knowledge base is already up-to-date.[/bold green]"
        )
        return

    console.print(
        f"   -> Found {len(symbols_to_process)} symbols needing vectorization."
    )

    qdrant_service = QdrantService()
    await qdrant_service.ensure_collection()

    tasks = []
    for symbol in symbols_to_process:
        # Translate the module path from the database back into a file system path.
        module_path = symbol["module"]
        file_path_str = "src/" + module_path.replace(".", "/") + ".py"
        file_path = settings.REPO_PATH / file_path_str

        source_code = _get_source_code(file_path, symbol["symbol_path"])
        if not source_code:
            continue

        normalized_code = normalize_text(source_code)
        code_hash = hashlib.sha256(normalized_code.encode("utf-8")).hexdigest()

        # Add both path representations to the task for later use
        task_data = {
            **symbol,
            "source_code": normalized_code,
            "code_hash": code_hash,
            "file_path_str": str(file_path.relative_to(settings.REPO_PATH)),
        }
        tasks.append(task_data)

    if not tasks:
        console.print(
            "[bold yellow]⚠️  No source code found for symbols needing vectorization. Check file paths.[/bold yellow]"
        )
        return

    console.print(f"   -> Preparing to vectorize {len(tasks)} symbols.")

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
                    "id": task["id"],
                    "vector_id": point_id,
                    "embedding_model": settings.LOCAL_EMBEDDING_MODEL_NAME,
                    "embedding_version": 1,
                }
            )

    await _update_symbols_in_db(updates_to_db)

    console.print(
        f"\n[bold green]✅ Vectorization complete. Processed {len(updates_to_db)}/{len(tasks)} symbols.[/bold green]"
    )
    if len(updates_to_db) < len(tasks):
        console.print(
            f"[bold red]   -> {len(tasks) - len(updates_to_db)} failures logged to {failure_log_path}[/bold red]"
        )
