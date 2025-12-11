# src/api/main_governance_patch.py
"""
Governance Integration Patch for FastAPI Lifespan.

Add this to your existing src/api/main.py lifespan function to initialize
constitutional governance on system startup.
"""

from __future__ import annotations

from mind.governance.validator_service import get_validator
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 5eeaa03d-dc6f-4c9d-af9e-72644bdcd710
def initialize_governance():
    """
    Initialize constitutional governance system.

    Call this during FastAPI lifespan startup to load and validate
    the constitution.

    Returns:
        ConstitutionalValidator instance
    """
    logger.info("📜 Loading constitutional governance...")

    try:
        validator = get_validator()
        logger.info("✅ Constitutional governance ready")
        logger.info(f"   📊 Indexed: {len(validator._critical_paths)} critical paths")
        logger.info(
            f"   📊 Indexed: {len(validator._autonomous_actions)} autonomous actions"
        )
        return validator
    except Exception as e:
        logger.error("❌ Failed to load constitution: %s", e)
        raise


# === INTEGRATION INSTRUCTIONS ===
#
# In your src/api/main.py, add to the lifespan function after line 180:
#
# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     logger.info("🚀 Starting CORE system...")
#
#     # ... existing code ...
#
#     # ADD THIS:
#     from api.main_governance_patch import initialize_governance
#     validator = initialize_governance()
#     app.state.governance_validator = validator
#
#     # ... rest of existing code ...
