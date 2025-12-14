# src/features/self_healing/purge_legacy_tags_service.py

"""Provides functionality for the purge_legacy_tags_service module."""

from __future__ import annotations

from collections import defaultdict

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.legacy_tag_check import LegacyTagCheck
from shared.config import settings
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 0e5a08a4-7c8f-4b5d-86b7-539a77d4e829
def purge_legacy_tags(dry_run: bool = True) -> int:
    """
    removes them from the source files. This function is constitutionally

    Args:
        dry_run: If True, only prints the actions that would be taken.

    Returns:
        The total number of lines that were (or would be) removed.
    """
    context = AuditorContext(settings.REPO_PATH)
    check = LegacyTagCheck(context)
    all_findings = check.execute()
    if not all_findings:
        logger.info("No legacy tags found anywhere in the project.")
        return 0
    src_findings = [
        finding
        for finding in all_findings
        if finding.file_path and finding.file_path.startswith("src/")
    ]
    if not src_findings:
        logger.info(
            "Found %s total legacy tag(s) in non-code files, but none in 'src/'. No automated action taken.",
            len(all_findings),
        )
        return 0
    logger.info(
        "Found %s total legacy tag(s). Purging the %s found in 'src/'...",
        len(all_findings),
        len(src_findings),
    )
    files_to_fix = defaultdict(list)
    for finding in src_findings:
        files_to_fix[finding.file_path].append(finding.line_number)
    total_lines_removed = 0
    for file_path_str, line_numbers_to_delete in files_to_fix.items():
        logger.info("Processing file: %s", file_path_str)
        file_path = settings.REPO_PATH / file_path_str
        sorted_line_numbers = sorted(line_numbers_to_delete, reverse=True)
        if dry_run:
            for line_num in sorted_line_numbers:
                logger.info("   -> [DRY RUN] Would delete line %s", line_num)
                total_lines_removed += 1
            continue
        try:
            lines = file_path.read_text("utf-8").splitlines()
            for line_num in sorted_line_numbers:
                index_to_delete = line_num - 1
                if 0 <= index_to_delete < len(lines):
                    del lines[index_to_delete]
                    total_lines_removed += 1
            file_path.write_text("\n".join(lines) + "\n", "utf-8")
            logger.info("   -> Purged %s legacy tag(s).", len(sorted_line_numbers))
        except Exception as e:
            logger.error("Error processing {file_path_str}: %s", e)
    return total_lines_removed
