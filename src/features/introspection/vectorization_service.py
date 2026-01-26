# src/features/introspection/vectorization_service.py
"""
High-performance orchestrator for capability vectorization.
Preserves all robustness logic via high-fidelity modularization.

FIX (2026-01):
- Hardens against legacy attribute drift: some downstream code expects `role_name`,
  while the DB model uses `role`. We provide a runtime alias to avoid total failure.
- Adds strict/degraded completion semantics (configurable) so workflows don't report
  "success" while processing 0 vectors due to hidden errors.
"""

from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import settings
from shared.context import CoreContext
from shared.infrastructure.config_service import ConfigService
from shared.logger import getLogger
from shared.utils.embedding_utils import normalize_text

from .vectorization.db_queries import fetch_initial_state, finalize_vector_update
from .vectorization.embedding_logic import get_robust_embedding


logger = getLogger(__name__)


def _ensure_legacy_role_alias(obj: Any) -> Any:
    """
    Some call paths still expect CognitiveRole.role_name, but the model uses .role.
    We provide a best-effort alias to prevent embedding/vectorization hard-failing.

    This is intentionally localized here to avoid forcing a DB model contract change
    if you want to keep schema objects "clean".
    """
    try:
        if hasattr(obj, "role") and not hasattr(obj, "role_name"):
            # Best-effort: attach a dynamic attribute (works for normal Python objects).
            setattr(obj, "role_name", getattr(obj, "role"))
    except Exception:
        # If the object forbids setattr (e.g., slots / proxy), we just proceed;
        # downstream should still be fixed, but we avoid crashing here.
        pass
    return obj


# ID: 0e545e4a-22e4-42cc-b1f6-9e900445627b
async def run_vectorize(
    context: CoreContext,
    session: AsyncSession,
    dry_run: bool = False,
    force: bool = False,
) -> None:
    """Orchestrates the full vectorization workflow."""
    config = await ConfigService.create(session)

    if not await config.get_bool("LLM_ENABLED", default=False):
        logger.info("Vectorization skipped: LLM_ENABLED=false")
        return

    # Strict mode: if any symbol fails vectorization, raise to mark workflow degraded/failed.
    strict = await config.get_bool("VECTORIZATION_STRICT", default=True)

    logger.info("🚀 Starting High-Fidelity Vectorization...")
    qdrant = context.qdrant_service or await context.registry.get_qdrant_service()
    cog = await context.registry.get_cognitive_service()
    cog = _ensure_legacy_role_alias(cog)

    # 1. DB State + Qdrant Hashes
    await qdrant.ensure_collection()
    all_symbols, existing_links = await fetch_initial_state(session)
    stored_hashes = await qdrant.get_stored_hashes()

    # Local import to avoid circulars and to keep hot path clean.
    # (extract_symbol_source is file-system heavy and can be treated as an optional dependency.)
    from .vectorization.code_processor import extract_symbol_source

    # 2. ANALYZE DELTA
    tasks: list[dict[str, Any]] = []
    for sym in all_symbols:
        rel_path = f"src/{sym['module'].replace('.', '/')}.py"
        source = extract_symbol_source(
            settings.REPO_PATH / rel_path, sym["symbol_path"]
        )
        if not source:
            continue

        norm_code = normalize_text(source)
        code_hash = hashlib.sha256(norm_code.encode("utf-8")).hexdigest()

        link_key = str(sym["id"])
        existing_vector_id = existing_links.get(link_key)
        existing_hash = (
            stored_hashes.get(existing_vector_id) if existing_vector_id else None
        )

        needs_vec = (
            force or (existing_vector_id is None) or (code_hash != existing_hash)
        )
        if needs_vec:
            tasks.append(
                {
                    "id": sym["id"],
                    "path": sym["symbol_path"],
                    "source": norm_code,
                    "hash": code_hash,
                    "file": rel_path,
                }
            )

    if not tasks:
        logger.info("✅ Vector knowledge base is already up-to-date.")
        return

    if dry_run:
        logger.info("[DRY RUN] %d symbols need update.", len(tasks))
        return

    # 3. EXECUTE
    updates: list[dict[str, Any]] = []
    failures: list[tuple[str, str]] = []

    for i, t in enumerate(tasks, 1):
        if i % 10 == 0:
            logger.info("Progress: %d/%d", i, len(tasks))

        try:
            vec = await get_robust_embedding(cog, t["source"])
            p_id = str(t["id"])

            payload = {
                "source_path": t["file"],
                "source_type": "code",
                "chunk_id": t["path"],
                "content_sha256": t["hash"],
                "language": "python",
                "symbol": t["path"],
            }

            await qdrant.upsert_capability_vector(p_id, vec, payload)

            updates.append(
                {
                    "symbol_id": t["id"],
                    "vector_id": p_id,
                    "embedding_model": settings.LOCAL_EMBEDDING_MODEL_NAME,
                    "embedding_version": 1,
                }
            )

        except Exception as e:
            failures.append((t["path"], str(e)))
            logger.error("Failed symbol %s: %s", t["path"], e)

    # 4. FINALIZE
    if updates:
        await finalize_vector_update(session, updates)
        await session.commit()

    logger.info(
        "🏁 Vectorization complete. Processed %d/%d symbols (failures=%d).",
        len(updates),
        len(tasks),
        len(failures),
    )

    if failures:
        # Keep the log readable but provide a deterministic summary.
        preview = "\n".join([f"- {p}: {msg}" for p, msg in failures[:10]])
        logger.warning(
            "Vectorization failures (first %d):\n%s", min(10, len(failures)), preview
        )

        if strict:
            raise RuntimeError(
                f"Vectorization degraded: {len(failures)} failures out of {len(tasks)}. "
                f"Set VECTORIZATION_STRICT=false to allow degraded success."
            )
