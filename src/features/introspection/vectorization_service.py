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
            SELECT id, symbol_path, module, fingerprint AS structural_hash
            FROM core.v_symbols_needing_embedding
            """
        )
        result = await session.execute(stmt)
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

        vector_id_str = str(task["id"])

        payload_data = {
            "source_path": task["file_path_str"],
            "source_type": "code",
            "chunk_id": task["symbol_path"],
            "content_sha256": task["code_hash"],
            "language": "python",
            "symbol": task["symbol_path"],
            "capability_tags": [vector_id_str],
        }
        await qdrant_service.upsert_capability_vector(
            point_id_str=vector_id_str,
            vector=vector,
            payload_data=payload_data,
        )

        return vector_id_str
    except Exception as e:
        log.error(f"Failed to process symbol '{task['symbol_path']}': {e}")
        failure_log_path.parent.mkdir(parents=True, exist_ok=True)
        with failure_log_path.open("a", encoding="utf-8") as f:
            f.write(f"vectorization_error\t{task['symbol_path']}\t{e}\n")
        return None


async def _update_db_after_vectorization(updates: List[Dict]):
    """
    Creates links in symbol_vector_links and updates the last_embedded timestamp
    on the symbols table.
    """
    if not updates:
        return
    async with get_session() as session:
        async with session.begin():
            # Upsert into the link table
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

            # Update the timestamp on the main symbols table
            await session.execute(
                text(
                    """
                    UPDATE core.symbols SET last_embedded = NOW()
                    WHERE id = ANY(:symbol_ids)
                """
                ),
                {"symbol_ids": [u["symbol_id"] for u in updates]},
            )

    console.print(f"   -> Updated {len(updates)} records in the database.")


# ID: 4bcad5fa-c30b-4c24-bf6c-5b692ecbbf67
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

    if force:
        console.print(
            "[bold yellow]--force flag detected: Re-vectorizing ALL public symbols.[/bold yellow]"
        )
        async with get_session() as session:
            result = await session.execute(
                text(
                    "SELECT id, symbol_path, module, fingerprint AS structural_hash FROM core.symbols WHERE is_public = TRUE"
                )
            )
            symbols_to_process = [dict(row._mapping) for row in result]
    else:
        symbols_to_process = await _fetch_symbols_from_db()

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
        module_path = symbol["module"]
        file_path_str = "src/" + module_path.replace(".", "/") + ".py"
        file_path = settings.REPO_PATH / file_path_str

        source_code = _get_source_code(file_path, symbol["symbol_path"])
        if not source_code:
            continue

        normalized_code = normalize_text(source_code)
        code_hash = hashlib.sha256(normalized_code.encode("utf-8")).hexdigest()

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
