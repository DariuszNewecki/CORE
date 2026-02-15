# src/features/maintenance/idempotency_harness.py
# ID: 89bd5782-1ffd-4883-8fe0-e9719f554e29

"""
Idempotency Test Harness - Phase 2 Hardening.
Verifies that system mutations are stable and do not cause 'logic drift' on repeated runs.
"""

from __future__ import annotations

import time
from typing import Any

from body.atomic.executor import ActionExecutor
from shared.infrastructure.storage.integrity_service import IntegrityService
from shared.logger import getLogger
from shared.models.validation_result import ValidationResult


logger = getLogger(__name__)


# ID: c5de649e-62b2-49a4-80f2-aedc16b6cdfb
class IdempotencyHarness:
    """
    Orchestrates the 'Run -> Baseline -> Run -> Verify' stability sequence.
    """

    def __init__(self, core_context: Any):
        self.context = core_context
        self.executor = ActionExecutor(core_context)
        self.integrity = IntegrityService(core_context.git_service.repo_path)

    # ID: f06e3a61-9e9a-4e95-9bcb-3bf71f377646
    async def verify_action(self, action_id: str, **params: Any) -> ValidationResult:
        """
        Tests an atomic action for idempotency.

        Sequence:
        1. Primary Mutation: Applies the fix/change.
        2. Snapshot: Records the 'Clean' state.
        3. Secondary Mutation: Attempts the same change again.
        4. Drift Check: Ensures the second run produced zero changes.
        """
        logger.info("🧪 Testing Idempotency for: %s", action_id)
        label = f"idempotency_{action_id}_{int(time.time())}"

        # 1. Primary Mutation (Ensure we are in a 'Final' state)
        logger.debug("   -> Phase 1: Primary Mutation")
        await self.executor.execute(action_id, write=True, **params)

        # 2. Snapshot (Historical Truth)
        logger.debug("   -> Phase 2: Creating Baseline")
        self.integrity.create_baseline(label)

        # 3. Secondary Mutation (The Stability Test)
        logger.debug("   -> Phase 3: Secondary Mutation")
        await self.executor.execute(action_id, write=True, **params)

        # 4. Drift Check (Sensation)
        logger.debug("   -> Phase 4: Verifying zero-drift")
        result = self.integrity.verify_integrity(label)

        if result.ok:
            logger.info("✅ Idempotency Proven: %s is stable.", action_id)
        else:
            logger.warning(
                "❌ Idempotency Failure: %s caused drift on repeat.", action_id
            )

        return result
