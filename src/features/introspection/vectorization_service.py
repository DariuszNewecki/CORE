# src/features/introspection/vectorization_service.py
"""
High-performance orchestrator for capability vectorization.
This version reads its work queue directly from the database, treating it as the
single source of truth for the symbol catalog.
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import Dict, List, Optional

from rich.console import Console
from rich.progress import track
from sqlalchemy import text

from core.cognitive_service import CognitiveService
from features.introspection.knowledge_helpers import log_failure
from services.clients.qdrant_client import QdrantService
from services.repositories.db.engine import get_session
from shared.config import settings
from shared.logger import getLogger
from shared.utils.embedding_utils import normalize_text

log = getLogger("core_admin.knowledge.orchestrator")
console = Console()


# ID: 65f3e8b5-35c7-4138-b177-f1a5faceee4d
async def _fetch_symbols_from_db() -> List[Dict]:
    """Queries the database to get the full list of symbols to be vectorized."""
    async with get_session() as session:
        stmt = text(
            """
            SELECT uuid, symbol_path, file_path, structural_hash
            FROM core.symbols
            WHERE status = 'active'
        """
        )
        result = await session.execute(stmt)
        return [dict(row._mapping) for row in result]


# ID: 11c635ed-9d61-4d04-b7c8-5a55a210e64b
async def _fetch_existing_vectors(qdrant_service: QdrantService) -> Dict[str, str]:
    """Fetches existing vectors from Qdrant and returns a map of content_hash -> point_id."""
    existing_vectors = {}
    records, _ = await qdrant_service.client.scroll(
        collection_name=qdrant_service.collection_name,
        limit=10000,
        with_payload=["content_sha256"],
        with_vectors=False,
    )
    for record in records:
        if record.payload and "content_sha256" in record.payload:
            existing_vectors[record.payload["content_sha256"]] = record.id
    return existing_vectors


# ID: 9d0b75e7-f064-49a3-b743-92bb3cc8e9a9
def _get_source_code(file_path: Path, symbol_path: str) -> Optional[str]:
    """Extracts the source code of a specific symbol from a file using AST."""
    if not file_path.exists():
        return None

    content = file_path.read_text("utf-8", errors="ignore")
    try:
        tree = ast.parse(content)
        symbol_name = symbol_path.split("::")[-1]

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if hasattr(node, "name") and node.name == symbol_name:
                    return ast.get_source_segment(content, node)
    except Exception:
        return None
    return None


# ID: e06caaf0-1af4-421a-ad5c-e468c8d41f36
async def _process_vectorization_task(
    task: Dict,
    cognitive_service: CognitiveService,
    qdrant_service: QdrantService,
    failure_log_path: Path,
) -> Optional[str]:
    """Processes a single symbol: gets embedding and upserts to Qdrant. Returns Qdrant point ID on success."""
    try:
        vector = await cognitive_service.get_embedding_for_code(task["source_code"])
        payload_data = {
            "source_path": task["file_path"],
            "source_type": "code",
            "chunk_id": task["symbol_path"],
            "content_sha256": task["code_hash"],
            "language": "python",
            "symbol": task["symbol_path"],
            "capability_tags": [task["uuid"]],  # Use the UUID as the tag
        }
        point_id = await qdrant_service.upsert_capability_vector(
            vector=vector, payload_data=payload_data
        )
        return point_id
    except Exception as e:
        log.error(f"Failed to process symbol '{task['symbol_path']}': {e}")
        log_failure(
            failure_log_path, task["symbol_path"], str(e), "vectorization_error"
        )
        return None


# ID: 10de89a4-bc4a-42cc-adc6-d276de8be7c3
async def _update_symbols_in_db(updates: List[Dict]):
    """Bulk updates the vector_id for symbols in the database."""
    if not updates:
        return
    async with get_session() as session:
        async with session.begin():
            await session.execute(
                text(
                    """
                    UPDATE core.symbols SET vector_id = :vector_id, updated_at = NOW()
                    WHERE uuid = :uuid
                """
                ),
                updates,
            )
        await session.commit()
    console.print(f"   -> Updated {len(updates)} vector IDs in the database.")


# ID: 1171223d-a43d-4c61-a493-f29f8e75218b
async def run_vectorize(dry_run: bool = False, force: bool = False):
    """
    The main orchestration logic for vectorizing capabilities based on the database.
    """
    console.print("[bold cyan]🚀 Starting Database-Driven Vectorization...[/bold cyan]")
    failure_log_path = settings.REPO_PATH / "logs" / "vectorization_failures.log"
    failure_log_path.parent.mkdir(parents=True, exist_ok=True)

    symbols_in_db = await _fetch_symbols_from_db()
    console.print(f"   -> Found {len(symbols_in_db)} active symbols in the database.")

    qdrant_service = QdrantService()
    existing_vectors = await _fetch_existing_vectors(qdrant_service)
    console.print(f"   -> Found {len(existing_vectors)} existing vectors in Qdrant.")

    tasks = []
    for symbol in symbols_in_db:
        file_path = settings.REPO_PATH / symbol["file_path"]
        source_code = _get_source_code(file_path, symbol["symbol_path"])
        if not source_code:
            continue

        normalized_code = normalize_text(source_code)
        code_hash = hashlib.sha256(normalized_code.encode("utf-8")).hexdigest()

        if not force and code_hash in existing_vectors:
            continue

        tasks.append({**symbol, "source_code": normalized_code, "code_hash": code_hash})

    if not tasks:
        console.print(
            "[bold green]✅ Vector knowledge base is already up-to-date.[/bold green]"
        )
        return

    console.print(f"   -> Preparing to vectorize {len(tasks)} new or modified symbols.")

    if dry_run:
        console.print(
            "\n[bold yellow]💧 Dry Run: No embeddings will be generated or stored.[/bold yellow]"
        )
        return

    cognitive_service = CognitiveService(settings.REPO_PATH)
    updates_to_db = []

    for task in track(tasks, description="Vectorizing symbols..."):
        point_id = await _process_vectorization_task(
            task, cognitive_service, qdrant_service, failure_log_path
        )
        if point_id:
            updates_to_db.append({"uuid": task["uuid"], "vector_id": point_id})

    await _update_symbols_in_db(updates_to_db)

    console.print(
        f"\n[bold green]✅ Vectorization complete. Processed {len(updates_to_db)}/{len(tasks)} symbols.[/bold green]"
    )
    if len(updates_to_db) < len(tasks):
        console.print(
            f"[bold red]   -> {len(tasks) - len(updates_to_db)} failures were logged to {failure_log_path}[/bold red]"
        )
