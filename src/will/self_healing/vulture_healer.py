# src/features/self_healing/vulture_healer.py

"""Refactored logic for src/features/self_healing/vulture_healer.py."""

from __future__ import annotations

import json
import re
from pathlib import Path

from body.services.file_service import FileService
from shared.logger import getLogger
from shared.utils.parsing import extract_python_code_from_response


logger = getLogger(__name__)


# ID: 515a5f31-deb3-41bc-9736-4e29e1989a0f
async def heal_dead_code(
    context,
    file_handler: FileService,
    repo_root: Path,
    write: bool = False,
):
    """Surgical cleanup of Vulture findings using local intelligence."""
    evidence_path = repo_root / "reports" / "audit_findings.json"
    if not evidence_path.exists():
        logger.error("No audit evidence found. Run 'core-admin check audit' first.")
        return

    findings = json.loads(evidence_path.read_text())
    dead_code_targets = [
        f for f in findings if f["check_id"] == "workflow.dead_code_check"
    ]

    if not dead_code_targets:
        logger.info("✅ No dead code findings in the ledger.")
        return

    # Ensure artifact directory exists via governed channel
    artifact_rel = "work/artifacts/healer"
    file_handler.ensure_dir(artifact_rel)

    logger.info(
        "✂️  Starting Surgical Purge of %d dead code findings...", len(dead_code_targets)
    )
    coder = await context.cognitive_service.aget_client_for_role("LocalCoder")

    for finding in dead_code_targets:
        msg = finding["message"]
        path_match = re.search(r"Dead code detected: ([\w/.-]+\.py)", msg)

        if not path_match:
            continue

        file_rel = path_match.group(1)
        file_abs = repo_root / file_rel

        if not file_abs.exists():
            continue

        source = file_abs.read_text(encoding="utf-8")

        prompt = f"""
        TASK: Remove dead code from {file_rel}.
        VULTURE FINDING: {msg}
        SOURCE CODE:
        {source}
        INSTRUCTION:
        Delete the unused variable or function mentioned in the finding.
        Preserve all other logic and formatting perfectly.
        Return ONLY the corrected Python code.
        """

        try:
            response = await coder.make_request_async(prompt, user_id="vulture_healer")
            fixed_code = extract_python_code_from_response(response) or response

            if fixed_code and fixed_code.strip() != source.strip():
                if write:
                    from body.atomic.executor import ActionExecutor

                    executor = ActionExecutor(context)
                    await executor.execute(
                        "file.edit", write=True, file_path=file_rel, code=fixed_code
                    )
                    logger.info("   ✅ APPLIED: %s", file_rel)
                else:
                    # PROPOSED CHANGE ARCHIVE (For your inspection)
                    artifact_file_rel = (
                        f"work/artifacts/healer/proposed_{Path(file_rel).name}"
                    )
                    result = file_handler.write_runtime_text(
                        artifact_file_rel, fixed_code
                    )
                    if result.status != "success":
                        raise RuntimeError(
                            f"Governance rejected write: {result.message}"
                        )
                    logger.info("   👀 INSPECT PROPOSAL: %s", artifact_file_rel)
            else:
                logger.info("   → No changes suggested for %s", file_rel)
        except Exception as e:
            logger.error("   ❌ Failed to heal %s: %s", file_rel, e)
