# src/body/services/governance_init.py

"""
Governance Integration Service for Application Startup.

Provides initialization utilities for constitutional governance system.
Used during FastAPI lifespan or CLI startup to load and validate constitution.
"""

from __future__ import annotations

from mind.governance.validator_service import get_validator
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 47d49349-577d-4c8a-864f-4037f2c1b026
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
        logger.info("   📊 Indexed: %s critical paths", len(validator._critical_paths))
        logger.info(
            "   📊 Indexed: %s autonomous actions", len(validator._autonomous_actions)
        )
        return validator
    except Exception as e:
        logger.error("❌ Failed to load constitution: %s", e)
        raise
