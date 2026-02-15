# src/shared/infrastructure/diagnostic_service.py
# ID: 56e00499-1e65-4a9f-a960-5cbc0f31f39f

"""
Diagnostic Service - Infrastructure Health Sensor.

CONSTITUTIONAL AUTHORITY: Infrastructure (coordination)
AUTHORITY LIMITS: Performs mechanical checks only; cannot make strategic decisions.
EXEMPTIONS: Authorized to import settings directly per architecture.boundary.settings_access.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import text

from shared.config import settings
from shared.infrastructure.clients.qdrant_client import QdrantService
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: fc6b4dfb-b432-4fbf-80de-4147f2d062d7
class DiagnosticService:
    """
    Performs mechanical connectivity and environment sensation.
    """

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root

    # ID: 0321a5a3-1b29-4b1c-9e3c-3c88bbd35593
    async def check_connectivity(self) -> dict[str, Any]:
        """
        Tests physical links to Database and Vector stores.
        """
        results = {
            "database": {"ok": False, "detail": "Not tested"},
            "qdrant": {"ok": False, "detail": "Not tested"},
            "environment": {"ok": False, "detail": "Not tested"},
        }

        # 1. Database Sensation
        try:
            async with get_session() as session:
                await session.execute(text("SELECT 1"))
                results["database"] = {"ok": True, "detail": "PostgreSQL Link Active"}
        except Exception as e:
            results["database"] = {"ok": False, "detail": str(e)}

        # 2. Vector Store Sensation
        try:
            q_service = QdrantService()
            await q_service.client.get_collections()
            results["qdrant"] = {"ok": True, "detail": "Qdrant API Active"}
        except Exception as e:
            results["qdrant"] = {"ok": False, "detail": str(e)}

        # 3. Environment Variable Sensation
        missing_vars = []
        required = ["DATABASE_URL", "QDRANT_URL", "LLM_API_KEY", "CORE_MASTER_KEY"]
        for var in required:
            if not getattr(settings, var, None):
                missing_vars.append(var)

        if not missing_vars:
            results["environment"] = {
                "ok": True,
                "detail": "Required coordinates present",
            }
        else:
            results["environment"] = {
                "ok": False,
                "detail": f"Missing variables: {', '.join(missing_vars)}",
            }

        return results

    # ID: ca4207be-2d72-41f4-a615-f4f1dbb1660b
    def check_file_system(self) -> list[str]:
        """
        Verifies existence of mandatory constitutional roots.
        """
        errors = []
        required = [
            self.repo_root / "src",
            self.repo_root / ".intent",
            self.repo_root / "var/prompts",
            self.repo_root / "sql",
        ]

        for path in required:
            if not path.exists():
                try:
                    errors.append(f"MISSING: {path.relative_to(self.repo_root)}")
                except ValueError:
                    errors.append(f"MISSING: {path}")

        return errors
