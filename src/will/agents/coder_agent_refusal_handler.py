# src/will/agents/coder_agent_refusal_handler.py
# ID: e37553e8-a253-4bbd-a5b6-69a67416862b

"""
RefusalResult handler for CoderAgent.

Constitutional Compliance:
Handles RefusalResult from CodeGenerator by:
1. Recording refusal to database (constitutional audit trail)
2. Converting to appropriate exception/response for upstream
3. Logging refusal details

This module integrates constitutional refusal discipline into the
existing CoderAgent workflow without breaking compatibility.
"""

from __future__ import annotations

from shared.infrastructure.repositories.refusal_repository import RefusalRepository
from shared.logger import getLogger
from shared.models.refusal_result import RefusalResult


logger = getLogger(__name__)


# ID: dd35851e-f15b-4dce-85bd-60cfe08d2ed7
class CoderAgentRefusalHandler:
    """
    Handles RefusalResult from CodeGenerator.

    Responsibilities:
    - Record refusal to database for constitutional audit
    - Convert refusal to appropriate exception for upstream
    - Log refusal for observability
    """

    def __init__(self, session_id: str | None = None, user_id: str | None = None):
        """
        Initialize refusal handler.

        Args:
            session_id: Decision trace session ID (links to trace)
            user_id: User ID for UX analysis
        """
        self.session_id = session_id
        self.user_id = user_id
        self.refusal_repo = RefusalRepository()

    # ID: ed1a701f-411c-4387-9166-a10a360f5f52
    async def handle_refusal(self, refusal: RefusalResult) -> None:
        """
        Handle a refusal from CodeGenerator.

        Constitutional Compliance:
        1. Records refusal to database (never blocks on failure)
        2. Logs refusal details
        3. Raises ValueError for backward compatibility

        Args:
            refusal: RefusalResult from CodeGenerator

        Raises:
            ValueError: Always raised (backward compatible with existing code)
        """
        # 1. Record refusal to database (constitutional audit trail)
        await self._record_refusal(refusal)

        # 2. Log refusal for observability
        self._log_refusal(refusal)

        # 3. Raise ValueError for backward compatibility
        # This allows existing try/except blocks to continue working
        raise ValueError(refusal.to_user_message())

    # ID: 5a6cc499-dc17-42aa-8ec1-d2b0fbcb4954
    async def _record_refusal(self, refusal: RefusalResult) -> None:
        """
        Record refusal to database.

        CONSTITUTIONAL: Never blocks - graceful degradation on storage failure.

        Args:
            refusal: RefusalResult to record
        """
        try:
            await self.refusal_repo.record_refusal(
                component_id=refusal.component_id,
                phase=refusal.phase.value if refusal.phase else "unknown",
                refusal_type=refusal.refusal_type,
                reason=refusal.reason,
                suggested_action=refusal.suggested_action,
                original_request=refusal.original_request,
                confidence=refusal.confidence,
                context_data=refusal.data,
                session_id=self.session_id,
                user_id=self.user_id,
            )

            logger.debug(
                "Refusal recorded: %s (type: %s)",
                refusal.component_id,
                refusal.refusal_type,
            )

        except Exception as e:
            # Constitutional: Storage failure doesn't block operations
            logger.warning(
                "Failed to record refusal (non-blocking): %s",
                e,
                exc_info=True,
            )

    # ID: fc4950be-6a0a-460f-93ef-7e4e7b6e96be
    def _log_refusal(self, refusal: RefusalResult) -> None:
        """
        Log refusal for observability.

        Args:
            refusal: RefusalResult to log
        """
        logger.warning(
            "❌ Constitutional refusal: %s",
            refusal.refusal_type,
        )
        logger.warning("   Component: %s", refusal.component_id)
        logger.warning(
            "   Phase: %s", refusal.phase.value if refusal.phase else "unknown"
        )
        logger.warning("   Reason: %s", refusal.reason[:200])
        logger.warning("   Suggested: %s", refusal.suggested_action[:200])

        if refusal.original_request:
            logger.debug("   Original request: %s", refusal.original_request[:200])


# ID: 83993372-47ff-4b56-8680-081be743b6e1
async def handle_code_generation_result(
    result: str | RefusalResult,
    session_id: str | None = None,
    user_id: str | None = None,
) -> str:
    """
    Helper function to handle CodeGenerator results.

    Handles both successful code generation and refusals.

    Args:
        result: Either generated code (str) or RefusalResult
        session_id: Decision trace session ID
        user_id: User ID for UX analysis

    Returns:
        Generated code string

    Raises:
        ValueError: If result is RefusalResult (backward compatible)
    """
    # Success case: return code directly
    if isinstance(result, str):
        return result

    # Refusal case: handle and raise
    handler = CoderAgentRefusalHandler(session_id=session_id, user_id=user_id)
    await handler.handle_refusal(result)

    # This line is never reached (handle_refusal always raises)
    # but keeps type checker happy
    raise ValueError("Refusal handled")
