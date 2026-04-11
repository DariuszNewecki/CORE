# src/body/workers/violation_remediator/ceremony.py
"""
Crate/Canary ceremony helpers for ViolationRemediator.

Responsibility: pack Crate, align staged file, run Canary, archive rollback.
No LLM calls. No Blackboard writes.
"""

from __future__ import annotations

import asyncio
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 7309bbd3-8a4b-427f-9d6f-b93b6bd3f719
class CeremonyMixin:
    """
    Mixin providing Crate/Canary ceremony methods for ViolationRemediator.

    Requires self._ctx and self._target_rule to be set by the host class.
    """

    async def _pack_crate(self, file_path: str, fixed_source: str) -> str | None:
        """Pack the fixed file into a CODE_MODIFICATION Crate via ActionExecutor."""
        try:
            result = await self._ctx.action_executor.execute(
                "crate.create",
                write=True,
                intent=(
                    f"Fix {self._target_rule} violations in {file_path} "
                    f"via autonomous remediation"
                ),
                payload_files={file_path: fixed_source},
            )
            if not result.ok:
                logger.warning(
                    "ViolationRemediator: Crate creation failed - %s",
                    result.data,
                )
                return None
            return result.data["crate_id"]
        except Exception as exc:
            logger.warning("ViolationRemediator: Crate error - %s", exc)
            return None

    async def _align_staged_file(self, crate_id: str, file_path: str) -> None:
        """Best-effort formatting alignment on the staged crate file.

        Runs black and ruff isort fix on the staged file so that Canary
        does not trip on trivial style issues. Failures are logged but
        never raised — Canary will catch anything that remains.
        """
        staged = Path(f"var/workflows/crates/inbox/{crate_id}/{file_path}")
        if not staged.exists():
            logger.warning(
                "ViolationRemediator: staged file not found for alignment - %s",
                staged,
            )
            return

        staged_str = str(staged)

        for label, cmd in (
            ("black", ["poetry", "run", "black", staged_str]),
            (
                "ruff-isort",
                [
                    "poetry",
                    "run",
                    "ruff",
                    "check",
                    "--select",
                    "I",
                    "--fix",
                    staged_str,
                ],
            ),
        ):
            try:
                proc = await asyncio.to_thread(
                    subprocess.run, cmd, capture_output=True, text=True, timeout=30
                )
                if proc.returncode == 0:
                    logger.info(
                        "ViolationRemediator: %s aligned %s",
                        label,
                        file_path,
                    )
                else:
                    logger.warning(
                        "ViolationRemediator: %s returned %d for %s - %s",
                        label,
                        proc.returncode,
                        file_path,
                        (proc.stderr or "")[:300],
                    )
            except Exception as exc:
                logger.warning(
                    "ViolationRemediator: %s failed for %s - %s",
                    label,
                    file_path,
                    exc,
                )

    async def _run_canary(self, crate_id: str) -> bool:
        """Run canary validation on the crate. Returns True if passed."""
        try:
            from body.services.crate_processing_service import CrateProcessingService

            service = CrateProcessingService(self._ctx)
            passed, findings = await service.validate_crate_by_id(crate_id)
            if not passed:
                logger.warning(
                    "ViolationRemediator: Canary FAILED for %s (%d findings)",
                    crate_id,
                    len(findings),
                )
            return passed
        except Exception as exc:
            logger.warning("ViolationRemediator: Canary error - %s", exc)
            return False

    def _archive_rollback(
        self,
        file_path: str,
        original_source: str,
        baseline_sha: str,
    ) -> None:
        """Archive rollback plan to var/mind/rollbacks/ via governed FileHandler."""
        try:
            file_handler = self._ctx.file_handler
            timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
            safe_name = file_path.replace("/", "_").replace(".", "_")
            rel_path = f"var/mind/rollbacks/{timestamp}-{safe_name}.json"

            file_handler.ensure_dir("var/mind/rollbacks")
            file_handler.write_runtime_json(
                rel_path,
                {
                    "file_path": file_path,
                    "rule": self._target_rule,
                    "baseline_sha": baseline_sha,
                    "original_source": original_source,
                    "archived_at": datetime.now(UTC).isoformat(),
                    "worker": "violation_remediator",
                },
            )
        except Exception as exc:
            logger.warning("ViolationRemediator: rollback archive failed - %s", exc)
