# src/features/self_healing/purge_legacy_tags_service.py
# ID: 0e5a08a4-7c8f-4b5d-86b7-539a77d4e829

"""
Service logic for purging legacy tags and descriptive pollution from source code.
Refactored to use the canonical ActionExecutor Gateway for all mutations.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from body.atomic.executor import ActionExecutor
from mind.governance.audit_context import AuditorContext
from mind.governance.rule_executor import execute_rule
from mind.governance.rule_extractor import extract_executable_rules

# REFACTORED: Removed direct settings import
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


# ID: b67cd592-b257-4228-b55e-424245f64205
async def purge_legacy_tags(context: CoreContext, dry_run: bool = True) -> int:
    """
    Finds legacy tags (like # owner: or # Tag:) using constitutional rules
    and removes them from the source files via the Action Gateway.

    Args:
        context: CoreContext (Required for ActionExecutor)
        dry_run: If True, only prints the actions (write=False in Gateway).

    Returns:
        The total number of lines that were (or would be) removed.
    """
    # 1. Initialize Context and Gateway
    executor = ActionExecutor(context)
    auditor_context = context.auditor_context or AuditorContext(
        context.git_service.repo_path
    )
    await auditor_context.load_knowledge_graph()

    # 2. Extract rules from the Constitution and find the "Purity" rule
    # FIX: Added enforcement_loader parameter
    all_rules = extract_executable_rules(
        auditor_context.policies, auditor_context.enforcement_loader
    )
    target_rule = next(
        (r for r in all_rules if r.rule_id == "purity.no_descriptive_pollution"), None
    )

    if not target_rule:
        logger.warning(
            "Constitutional rule 'purity.no_descriptive_pollution' not found. Skipping purge."
        )
        return 0

    # 3. Execute the rule dynamically to find violations
    logger.info(
        "🔍 Scanning for legacy tags via constitutional rule: %s", target_rule.rule_id
    )
    all_findings = await execute_rule(target_rule, auditor_context)

    if not all_findings:
        logger.info("✅ No legacy tags found. Codebase is pure.")
        return 0

    # 4. Filter findings to only include those in the source directory
    src_findings = [
        finding
        for finding in all_findings
        if finding.file_path and finding.file_path.startswith("src/")
    ]

    if not src_findings:
        logger.info(
            "Found %s findings in non-code files. No automated action taken on 'src/'.",
            len(all_findings),
        )
        return 0

    logger.info(
        "Found %s instances of legacy tags in 'src/'. Starting cleanup...",
        len(src_findings),
    )

    # 5. Group findings by file to minimize gateway transactions
    files_to_fix = defaultdict(list)
    for finding in src_findings:
        if finding.line_number:
            files_to_fix[finding.file_path].append(finding.line_number)

    total_lines_removed = 0
    write_mode = not dry_run

    # 6. Apply fixes via Governed Gateway
    for file_path_str, line_numbers_to_delete in files_to_fix.items():
        file_path = context.git_service.repo_path / file_path_str

        # Sort lines in reverse order to avoid index shifting while deleting
        sorted_line_numbers = sorted(line_numbers_to_delete, reverse=True)

        try:
            if not file_path.exists():
                continue

            lines = file_path.read_text("utf-8").splitlines()

            for line_num in sorted_line_numbers:
                index_to_delete = line_num - 1
                if 0 <= index_to_delete < len(lines):
                    del lines[index_to_delete]
                    total_lines_removed += 1

            final_code = "\n".join(lines) + "\n"

            # CONSTITUTIONAL GATEWAY: Mutation is audited and guarded
            result = await executor.execute(
                action_id="file.edit",
                write=write_mode,
                file_path=file_path_str,
                code=final_code,
            )

            if result.ok:
                mode_str = "Purged" if write_mode else "Proposed (Dry Run)"
                logger.info(
                    "   -> [%s] %s lines from %s",
                    mode_str,
                    len(sorted_line_numbers),
                    file_path_str,
                )
            else:
                logger.error(
                    "   -> [BLOCKED] %s: %s", file_path_str, result.data.get("error")
                )

        except Exception as e:
            logger.error("❌ Error processing %s: %s", file_path_str, e)

    return total_lines_removed
