# src/features/self_healing/purge_legacy_tags_service.py
"""Provides functionality for the purge_legacy_tags_service module."""

from __future__ import annotations

from collections import defaultdict

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.legacy_tag_check import LegacyTagCheck
from rich.console import Console
from shared.config import settings

console = Console()


# ID: 5b7a5950-e534-4fb8-ad13-f9e6ad555643
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
        console.print(
            "[bold green]✅ No legacy tags found anywhere in the project.[/bold green]"
        )
        return 0

    # --- THIS IS THE CRITICAL AMENDMENT ---
    # Filter the findings to only include those within the 'src/' directory.
    src_findings = [
        finding
        for finding in all_findings
        if finding.file_path and finding.file_path.startswith("src/")
    ]
    # --- END OF AMENDMENT ---

    if not src_findings:
        console.print(
            f"[bold yellow]🔍 Found {len(all_findings)} total legacy tag(s) in non-code files, but none in 'src/'. No automated action taken.[/bold yellow]"
        )
        return 0

    console.print(
        f"[bold]🔍 Found {len(all_findings)} total legacy tag(s). Purging the {len(src_findings)} found in 'src/'...[/bold]"
    )

    # Group findings by file path to process one file at a time
    files_to_fix = defaultdict(list)
    for finding in src_findings:
        files_to_fix[finding.file_path].append(finding.line_number)

    total_lines_removed = 0
    for file_path_str, line_numbers_to_delete in files_to_fix.items():
        console.print(f"🔧 Processing file: [cyan]{file_path_str}[/cyan]")
        file_path = settings.REPO_PATH / file_path_str

        # Your critical insight: sort line numbers in reverse to avoid index shifting
        sorted_line_numbers = sorted(line_numbers_to_delete, reverse=True)

        if dry_run:
            for line_num in sorted_line_numbers:
                console.print(f"   -> [DRY RUN] Would delete line {line_num}")
                total_lines_removed += 1
            continue

        try:
            lines = file_path.read_text("utf-8").splitlines()
            for line_num in sorted_line_numbers:
                # Convert 1-based line number to 0-based index
                index_to_delete = line_num - 1
                if 0 <= index_to_delete < len(lines):
                    del lines[index_to_delete]
                    total_lines_removed += 1

            file_path.write_text("\n".join(lines) + "\n", "utf-8")
            console.print(f"   -> ✅ Purged {len(sorted_line_numbers)} legacy tag(s).")
        except Exception as e:
            console.print(
                f"   -> [bold red]❌ Error processing {file_path_str}: {e}[/bold red]"
            )

    return total_lines_removed
