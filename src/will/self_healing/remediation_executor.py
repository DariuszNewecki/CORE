# src/will/self_healing/remediation_executor.py
"""Remediation Executor.

Executes deterministic fix handlers for matched audit patterns.
Single responsibility: handler dispatch and execution only.
"""

from __future__ import annotations

import time

from body.self_healing.remediation_models import FixDetail, FixResult, MatchedPattern
from body.services.file_service import FileService
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: bf469e1f-d1ed-4169-90c1-485963414fd2
class RemediationExecutor:
    """Dispatches and executes fix handlers for matched patterns."""

    def __init__(self, file_handler: FileService, repo_root) -> None:
        self.file_handler = file_handler
        self.repo_root = repo_root

    # ID: 3ca733ec-5568-47e5-8129-9439827e8f8b
    async def execute(
        self,
        matched: list[MatchedPattern],
        write: bool,
    ) -> list[FixDetail]:
        """Execute fixes for all matched patterns.

        Args:
            matched: Matched patterns to fix.
            write: Whether to apply changes or dry-run.

        Returns:
            List of FixDetail records.
        """
        fix_details: list[FixDetail] = []

        for match in matched:
            start_ms = int(time.time() * 1000)
            handler = self._get_handler(match.pattern.action_handler)

            if handler is None:
                logger.warning(
                    "Handler not found: %s (skipping)", match.pattern.action_handler
                )
                fix_details.append(
                    FixDetail(
                        finding_id=match.finding.check_id,
                        file_path=match.finding.file_path or "unknown",
                        action_handler=match.pattern.action_handler,
                        status="skipped",
                        error_message="Handler not implemented",
                        duration_ms=0,
                    )
                )
                continue

            try:
                result: FixResult = await handler(
                    finding=match.finding,
                    file_handler=self.file_handler,
                    repo_root=self.repo_root,
                    write=write,
                )
                duration_ms = int(time.time() * 1000) - start_ms
                fix_details.append(
                    FixDetail(
                        finding_id=match.finding.check_id,
                        file_path=match.finding.file_path or "unknown",
                        action_handler=match.pattern.action_handler,
                        status="success" if result.ok else "failed",
                        error_message=result.error_message,
                        duration_ms=duration_ms,
                    )
                )
            except Exception as e:
                logger.error(
                    "Handler crashed: %s - %s", match.pattern.action_handler, e
                )
                duration_ms = int(time.time() * 1000) - start_ms
                fix_details.append(
                    FixDetail(
                        finding_id=match.finding.check_id,
                        file_path=match.finding.file_path or "unknown",
                        action_handler=match.pattern.action_handler,
                        status="failed",
                        error_message=f"Exception: {e!s}",
                        duration_ms=duration_ms,
                    )
                )

        return fix_details

    def _get_handler(self, action_handler: str):
        """Resolve handler name to callable.

        Returns:
            Handler function or None if not implemented.
        """
        if action_handler == "sort_imports":
            from body.self_healing.handlers.import_sorting_handler import (
                sort_imports_handler,
            )

            return sort_imports_handler
        return None
