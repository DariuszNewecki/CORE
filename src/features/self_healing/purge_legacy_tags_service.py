# src/features/self_healing/purge_legacy_tags_service.py

"""
Service logic for purging legacy tags and descriptive pollution from source code.
Uses the dynamic constitutional rule engine instead of deleted legacy check classes.
"""

from __future__ import annotations

from collections import defaultdict

from mind.governance.audit_context import AuditorContext
from mind.governance.rule_executor import execute_rule
from mind.governance.rule_extractor import extract_executable_rules
from shared.config import settings
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 0e5a08a4-7c8f-4b5d-86b7-539a77d4e829
async def purge_legacy_tags(dry_run: bool = True) -> int:
    """
    Finds legacy tags (like # owner: or # Tag:) using constitutional rules
    and removes them from the source files.

    Args:
        dry_run: If True, only prints the actions that would be taken.

    Returns:
        The total number of lines that were (or would be) removed.
    """
    # 1. Initialize Context and load the Knowledge Graph from DB
    context = AuditorContext(settings.REPO_PATH)
    await context.load_knowledge_graph()

    # 2. Extract rules from the Constitution and find the "Purity" rule
    # This rule is defined in src/mind/governance/checks/capability_owner_check.py
    # and targets "# owner:" and other comment pollution.
    all_rules = extract_executable_rules(context.policies)
    target_rule = next(
        (r for r in all_rules if r.rule_id == "purity.no_descriptive_pollution"), None
    )

    if not target_rule:
        logger.warning(
            "Constitutional rule 'purity.no_descriptive_pollution' not found. Skipping purge."
        )
        return 0

    # 3. Execute the rule dynamically
    logger.info(
        "🔍 Scanning for legacy tags via constitutional rule: %s", target_rule.rule_id
    )
    all_findings = await execute_rule(target_rule, context)

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

    # 5. Group findings by file so we only open each file once
    files_to_fix = defaultdict(list)
    for finding in src_findings:
        if finding.line_number:
            files_to_fix[finding.file_path].append(finding.line_number)

    total_lines_removed = 0

    # 6. Apply fixes
    for file_path_str, line_numbers_to_delete in files_to_fix.items():
        file_path = settings.REPO_PATH / file_path_str

        # Sort lines in reverse order to avoid index shifting while deleting
        sorted_line_numbers = sorted(line_numbers_to_delete, reverse=True)

        if dry_run:
            logger.info("💧 [DRY RUN] Would process: %s", file_path_str)
            for line_num in sorted_line_numbers:
                logger.debug("   -> Would delete line %s", line_num)
                total_lines_removed += 1
            continue

        try:
            if not file_path.exists():
                continue

            lines = file_path.read_text("utf-8").splitlines()
            original_count = len(lines)

            for line_num in sorted_line_numbers:
                index_to_delete = line_num - 1
                if 0 <= index_to_delete < len(lines):
                    del lines[index_to_delete]
                    total_lines_removed += 1

            # Save the file back only if lines were actually removed
            if len(lines) < original_count:
                file_path.write_text("\n".join(lines) + "\n", "utf-8")
                logger.info(
                    "   -> ✅ Purged %s tags from %s",
                    len(sorted_line_numbers),
                    file_path_str,
                )

        except Exception as e:
            logger.error("❌ Error processing %s: %s", file_path_str, e)

    return total_lines_removed
