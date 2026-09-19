# src/body/infrastructure/lifespan.py

"""
System Lifespan - Infrastructure Ignition Sequence.

CONSTITUTIONAL FIX (P2.3):
Moved from shared.infrastructure to body.infrastructure to prevent
the shared layer from importing higher-level Body/Mind components.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from body.infrastructure.bootstrap import create_core_context
from body.services.service_registry import service_registry
from shared.config import settings
from shared.infrastructure.config_service import ConfigService
from shared.infrastructure.diagnostic_service import DiagnosticService
from shared.infrastructure.repositories.db.schema_gate import run_startup_schema_gate
from shared.logger import apply_log_level, getLogger


if TYPE_CHECKING:
    from fastapi import FastAPI

logger = getLogger(__name__)


@asynccontextmanager
# ID: 174c23d1-ad9d-4785-bbde-0f1bf408f180
async def core_lifespan(app: FastAPI):
    """
    Constitutional ignition and shutdown sequence for the CORE system.
    """
    logger.info("🚀 Starting CORE system...")

    # 1. CONSTITUTIONAL BOOTSTRAP
    core_context = create_core_context(service_registry)
    app.state.core_context = core_context

    if os.getenv("PYTEST_CURRENT_TEST"):
        core_context._is_test_mode = True

    try:
        if not getattr(core_context, "_is_test_mode", False):
            # 2. PRE-IGNITION SENSATION (Health Gate)
            diagnostic = DiagnosticService(settings.REPO_PATH)
            health = await diagnostic.check_connectivity()

            unhealthy_components = [
                name for name, res in health.items() if not res["ok"]
            ]

            if unhealthy_components:
                msg = f"Degraded Infrastructure Detected: {', '.join(unhealthy_components)}"
                if settings.CORE_STRICT_MODE:
                    logger.critical("❌ STRICT MODE: Aborting startup. %s", msg)
                    raise RuntimeError(f"Constitutional Ignition Failure: {msg}")
                else:
                    logger.warning("⚠️ ADVISORY MODE: Continuing despite %s", msg)

            # 2b. SCHEMA GATE (ADR-162 D2): read-only; refuses to serve against
            # a schema the code does not match (pending / unledgered /
            # contradictory), naming the remedy. CORE_STRICT_MODE does not
            # relax it. An unreachable database was already handled above.
            # uvicorn turns the raised refusal into "Application startup
            # failed" (its own exit code); the daemon and the core-engine
            # entrypoint exit 78 for the same verdict.
            await run_startup_schema_gate("CORE API")

            # 3. WARM UP HEAVY SERVICES
            cognitive = await service_registry.get_cognitive_service()
            auditor = await service_registry.get_auditor_context()
            qdrant = await service_registry.get_qdrant_service()
            # Idempotent: creates the vector collection on a fresh install,
            # no-ops when it already exists. Replaces the retired one-shot
            # infra/scripts/create_qdrant_collection.py (#521 item 4).
            await qdrant.ensure_collection()

            core_context.cognitive_service = cognitive
            core_context.auditor_context = auditor
            core_context.qdrant_service = qdrant
            # ADR-064: wire the Body-layer dispatch facade (no direct will.* import here).
            core_context.capability_tagging_service = (
                service_registry.get_capability_tagging_service()
            )

            # 4. DATABASE & CONFIG INITIALIZATION
            async with service_registry.session() as session:
                config = await ConfigService.create(session)
                log_level_from_db = await config.get("LOG_LEVEL", "INFO")
                # #889: was `reconfigure_log_level(...)` un-awaited -- a
                # coroutine that never ran, so the DB LOG_LEVEL never
                # applied. Awaiting it is not the fix: it is an
                # @atomic_action and raises GovernanceBypassError outside
                # an executor. Bootstrap applies the primitive directly.
                try:
                    apply_log_level(str(log_level_from_db))
                    logger.info("Log level set from DB config: %s", log_level_from_db)
                except ValueError as exc:
                    logger.warning(
                        "Ignoring invalid LOG_LEVEL from DB config (%r): %s",
                        log_level_from_db,
                        exc,
                    )
                await cognitive.initialize(session)

            # 5. LOAD KNOWLEDGE GRAPH
            await auditor.load_knowledge_graph()

        yield
    finally:
        logger.info("🛑 CORE system shutting down.")
