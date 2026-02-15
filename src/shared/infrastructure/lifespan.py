# src/shared/infrastructure/lifespan.py
# ID: 7c3a9f12-b4e8-4d5c-a1f0-6e8b2d9c4a7f

"""
System Lifespan - Infrastructure Ignition Sequence.

CONSTITUTIONAL AUTHORITY: Infrastructure (coordination)
AUTHORITY LIMITS:
    - Performs mechanical startup/shutdown coordination only.
    - Cannot make strategic decisions or route user requests.
    - Cannot evaluate constitutional rules.

This module owns the system bootstrap lifecycle that was previously
embedded in src/api/main.py. Extracting it here resolves the
constitutional violation where the API layer imported Body services
directly (architecture.api.no_body_bypass).

The ignition sequence is infrastructure wiring, not request handling.
Big Boys Pattern: Kubernetes kubelet, Spring ApplicationContext,
AWS CloudFormation stack creation — all separate ignition from
the request path.

Dependencies:
    - body.infrastructure.bootstrap (creates CoreContext)
    - body.services.service_registry (DI container)
    - shared.config (environment coordinates)
    - shared.infrastructure.config_service (DB-backed config)
    - shared.infrastructure.diagnostic_service (health sensor)
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
from shared.logger import getLogger, reconfigure_log_level


if TYPE_CHECKING:
    from fastapi import FastAPI

logger = getLogger(__name__)


@asynccontextmanager
# ID: 8d4b1e23-c5f9-4a6d-b2e1-7f9c3d0a5b8e
async def core_lifespan(app: FastAPI):
    """
    Constitutional ignition and shutdown sequence for the CORE system.

    Phases:
        1. Constitutional Bootstrap - Create CoreContext, prime ServiceRegistry
        2. Pre-Ignition Sensation - Health gate for infrastructure connectivity
        3. Service Warm-Up - Initialize heavy services (Cognitive, Auditor, Qdrant)
        4. Database & Config - Load DB-backed configuration
        5. Knowledge Graph - Load constitutional knowledge into memory

    Shutdown:
        Logs clean shutdown. Service cleanup is handled by garbage collection
        and context manager teardown.

    Args:
        app: FastAPI application instance. CoreContext is attached to app.state.
    """
    logger.info("\U0001f680 Starting CORE system...")

    # 1. CONSTITUTIONAL BOOTSTRAP
    core_context = create_core_context(service_registry)
    app.state.core_context = core_context

    if os.getenv("PYTEST_CURRENT_TEST"):
        core_context._is_test_mode = True

    try:
        if not getattr(core_context, "_is_test_mode", False):
            # ============================================================
            # 2. PRE-IGNITION SENSATION (Health Gate)
            # ============================================================
            diagnostic = DiagnosticService(settings.REPO_PATH)
            health = await diagnostic.check_connectivity()

            unhealthy_components = [
                name for name, res in health.items() if not res["ok"]
            ]

            if unhealthy_components:
                msg = f"Degraded Infrastructure Detected: {', '.join(unhealthy_components)}"
                if settings.CORE_STRICT_MODE:
                    logger.critical("\u274c STRICT MODE: Aborting startup. %s", msg)
                    raise RuntimeError(f"Constitutional Ignition Failure: {msg}")
                else:
                    logger.warning(
                        "\u26a0\ufe0f ADVISORY MODE: Continuing despite %s", msg
                    )

            # 3. WARM UP HEAVY SERVICES
            cognitive = await service_registry.get_cognitive_service()
            auditor = await service_registry.get_auditor_context()
            qdrant = await service_registry.get_qdrant_service()

            core_context.cognitive_service = cognitive
            core_context.auditor_context = auditor
            core_context.qdrant_service = qdrant

            # 4. DATABASE & CONFIG INITIALIZATION
            async with service_registry.session() as session:
                config = await ConfigService.create(session)
                log_level_from_db = await config.get("LOG_LEVEL", "INFO")
                reconfigure_log_level(log_level_from_db)
                await cognitive.initialize(session)

            # 5. LOAD KNOWLEDGE GRAPH
            await auditor.load_knowledge_graph()

        yield
    finally:
        logger.info("\U0001f6d1 CORE system shutting down.")
