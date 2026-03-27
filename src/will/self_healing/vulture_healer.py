# src/will/self_healing/vulture_healer.py
"""Surgical cleanup of Vulture dead-code findings.

Uses local LLM intelligence to safely remove unused variables and functions
identified by the Vulture static analyser.

V2.7 FIX:
- Removed hardcoded: repo_root / "reports" / "audit_findings.json"
- Evidence path now resolved via PathResolver.audit_findings_path.
"""

from __future__ import annotations

import json
from pathlib import Path

from body.services.file_service import FileService
from shared.ai.prompt_model import PromptModel
from shared.logger import getLogger
from shared.path_resolver import PathResolver
from shared.utils.parsing import extract_python_code_from_response


logger = getLogger(__name__)


# ID: 515a5f31-deb3-41bc-9736-4e29e1989a0f
async def heal_dead_code(
    context,
    file_handler: FileService,
    repo_root: Path,
    write: bool = False,
) -> None:
    """Surgical cleanup of Vulture findings using local intelligence.

    Args:
        context: CoreContext providing cognitive_service.
        file_handler: Governed file mutation surface.
        repo_root: Repository root path.
        write: If False, dry-run only. If True, applies deletions.
    """
    path_resolver = PathResolver(repo_root)

    # Canonical path via PathResolver — never hardcoded.
    evidence_path = path_resolver.audit_findings_path

    if not evidence_path.exists():
        logger.error(
            "No audit evidence found at %s. Run 'core-admin check audit' first.",
            evidence_path,
        )
        return

    try:
        findings = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Failed to read audit findings from %s: %s", evidence_path, e)
        return

    dead_code_targets = [
        f for f in findings if f.get("check_id") == "workflow.dead_code_check"
    ]

    if not dead_code_targets:
        logger.info("No dead code findings in the ledger.")
        return

    # Ensure artifact directory exists via governed channel.
    artifact_rel = "work/artifacts/healer"
    file_handler.ensure_dir(artifact_rel)

    logger.info(
        "Found %d dead code targets — beginning surgical cleanup (write=%s)",
        len(dead_code_targets),
        write,
    )

    cognitive_service = getattr(context, "cognitive_service", None)
    if cognitive_service is None:
        logger.error(
            "cognitive_service unavailable on CoreContext — cannot perform LLM-assisted healing."
        )
        return

    healed = 0
    skipped = 0
    errors = 0

    for finding in dead_code_targets:
        file_path_str = finding.get("file_path")
        line_number = finding.get("line_number")
        message = finding.get("message", "")

        if not file_path_str or not file_path_str.endswith(".py"):
            skipped += 1
            continue

        abs_path = repo_root / file_path_str
        if not abs_path.exists():
            logger.warning("Dead code target not found: %s — skipping", abs_path)
            skipped += 1
            continue

        try:
            source = abs_path.read_text(encoding="utf-8")
        except OSError as e:
            logger.error("Could not read %s: %s", abs_path, e)
            errors += 1
            continue

        prompt_model = PromptModel(cognitive_service=cognitive_service)
        prompt = (
            f"You are a precise Python refactoring tool.\n\n"
            f"The following finding was reported by Vulture (dead code detector):\n"
            f"  File: {file_path_str}\n"
            f"  Line: {line_number}\n"
            f"  Finding: {message}\n\n"
            f"Remove the dead code item identified above from the source file below. "
            f"Do not modify any other code. "
            f"Return only the complete updated Python file, no explanation.\n\n"
            f"```python\n{source}\n```"
        )

        try:
            response = await prompt_model.complete(prompt)
            updated_code = extract_python_code_from_response(response)
        except Exception as e:
            logger.error("LLM healing failed for %s: %s", file_path_str, e)
            errors += 1
            continue

        if not updated_code or updated_code.strip() == source.strip():
            logger.info("No change produced for %s — skipping", file_path_str)
            skipped += 1
            continue

        if write:
            try:
                file_handler.write_runtime_text(file_path_str, updated_code)
                logger.info("Healed: %s (line %s)", file_path_str, line_number)
                healed += 1
            except Exception as e:
                logger.error("FileHandler write failed for %s: %s", file_path_str, e)
                errors += 1
        else:
            logger.info(
                "[DRY RUN] Would remove dead code in %s (line %s)",
                file_path_str,
                line_number,
            )
            healed += 1

    logger.info(
        "Vulture healer complete — healed=%d, skipped=%d, errors=%d (write=%s)",
        healed,
        skipped,
        errors,
        write,
    )
