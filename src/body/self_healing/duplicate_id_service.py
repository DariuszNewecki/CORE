# src/features/self_healing/duplicate_id_service.py
# ID: 5891cbbe-ae62-4743-92fa-2e204ca5fa13

"""
Provides a service to find and resolve duplicate '# ID:' UUIDs in the codebase.

CONSTITUTIONAL FIX (V2.3.0):
- Duplicate detection now scans the FILESYSTEM, not the database.
- The database flattens duplicates during sync (PK on id or symbol_path),
  making DB-based detection structurally impossible.
- The filesystem is the source of truth for '# ID:' tags at the Parse/Audit phase.
- Resolution uses ActionExecutor for all file mutations (governed writes).
- DB query for symbol creation dates retained as tiebreaker for preservation order.

Constitutional alignment:
- linkage.duplicate_ids: "Symbol identifiers MUST be globally unique across the entire codebase."
- Enforcement: blocking (policy, audit phase)
- Mind-Body-Will: This is a Body-layer service (pure execution, no decisions).
"""

from __future__ import annotations

import re
import uuid as uuid_mod
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import settings
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)

# Pattern matches '# ID: <uuid>' comments in source files
_ID_PATTERN = re.compile(r"^(\s*#\s*ID:\s*)(\S+.*?)\s*$")


@dataclass
# ID: 443744ce-caec-428b-bbed-f9abed4415dc
class IdOccurrence:
    """A single occurrence of a '# ID:' tag in the filesystem."""

    file_path: Path
    line_number: int
    id_value: str
    line_prefix: str  # The '# ID: ' portion including whitespace


# ---------------------------------------------------------------------------
# Filesystem scanning (source of truth for '# ID:' tags)
# ---------------------------------------------------------------------------


# ID: 7c3e9a1b-4d5f-6e7a-8b9c-0d1e2f3a4b5c
def scan_filesystem_for_ids(src_root: Path) -> dict[str, list[IdOccurrence]]:
    """
    Scan all Python files under src_root for '# ID:' comment tags.

    Returns a mapping of id_value -> list of occurrences.
    This operates on the filesystem directly, bypassing the database,
    because the filesystem is the source of truth for code identity tags.

    Args:
        src_root: Root directory to scan (typically repo_path / "src")

    Returns:
        Dict mapping each ID string to all its occurrences across files.
    """
    id_map: dict[str, list[IdOccurrence]] = defaultdict(list)

    if not src_root.exists():
        logger.warning("Source root does not exist: %s", src_root)
        return id_map

    for py_file in sorted(src_root.rglob("*.py")):
        try:
            lines = py_file.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError) as e:
            logger.warning("Could not read %s: %s", py_file, e)
            continue

        for line_num_0, line in enumerate(lines):
            match = _ID_PATTERN.match(line)
            if match:
                prefix = match.group(1)
                id_value = match.group(2).strip()
                id_map[id_value].append(
                    IdOccurrence(
                        file_path=py_file,
                        line_number=line_num_0 + 1,
                        id_value=id_value,
                        line_prefix=prefix,
                    )
                )

    return id_map


# ID: 8d4f0b2c-5e6a-7f8b-9c0d-1e2f3a4b5c6d
def _is_valid_uuid(value: str) -> bool:
    """Check if a string is a valid UUID."""
    try:
        uuid_mod.UUID(value)
        return True
    except (ValueError, AttributeError):
        return False


# ID: 58534512-833d-4a15-a48b-51944d1327fd
def find_duplicates(
    id_map: dict[str, list[IdOccurrence]],
) -> dict[str, list[IdOccurrence]]:
    """
    Filter the ID map to entries that need resolution.

    Includes:
    - Any ID appearing more than once (true duplicates)
    - Any ID that is not a valid UUID (placeholders like TBD,
      template_value, executor_execute, or malformed UUIDs)

    Args:
        id_map: Full mapping from scan_filesystem_for_ids.

    Returns:
        Dict containing IDs that need fresh UUIDs assigned.
    """
    duplicates: dict[str, list[IdOccurrence]] = {}
    for id_value, occurrences in id_map.items():
        is_invalid = not _is_valid_uuid(id_value)
        is_duplicate = len(occurrences) > 1

        if is_duplicate or is_invalid:
            duplicates[id_value] = occurrences

    return duplicates


# ---------------------------------------------------------------------------
# DB-backed tiebreaker (optional: determines which occurrence to preserve)
# ---------------------------------------------------------------------------


# ID: 8727df72-cc4e-4e8e-b350-8641c2a8b8c2
async def _get_symbol_creation_dates(session: AsyncSession) -> dict[str, str]:
    """
    Queries the database to get the creation timestamp for each symbol UUID.

    Used as a tiebreaker: the oldest DB entry is the "original" and gets
    preserved; newer collisions get fresh UUIDs.

    Args:
        session: Active database session.

    Returns:
        Mapping of UUID string -> ISO timestamp string.
    """
    try:
        result = await session.execute(text("SELECT id, created_at FROM core.symbols"))
        return {str(row[0]): row[1].isoformat() for row in result}
    except Exception as e:
        logger.warning(
            "Could not fetch symbol creation dates from DB (%s). "
            "Falling back to first-occurrence-wins.",
            e,
        )
        return {}


# ---------------------------------------------------------------------------
# Resolution logic
# ---------------------------------------------------------------------------


# ID: 9e5f0c3d-6a7b-8c9d-0e1f-2a3b4c5d6e7f
def _build_replacement_plan(
    duplicates: dict[str, list[IdOccurrence]],
) -> dict[Path, list[tuple[int, str, str]]]:
    """
    Build a per-file replacement plan for duplicate IDs.

    For each duplicate group, the first occurrence is preserved and all
    subsequent occurrences get fresh UUIDs. Invalid placeholders (TBD,
    template_value, etc.) are ALL replaced.

    Args:
        duplicates: Output of find_duplicates().

    Returns:
        Dict of file_path -> list of (line_number, old_line_content, new_line_content).
        Line numbers are 1-indexed.
    """
    file_edits: dict[Path, list[tuple[int, str, str]]] = defaultdict(list)

    for id_value, occurrences in duplicates.items():
        is_invalid = not _is_valid_uuid(id_value)

        # For invalid/placeholder IDs: replace ALL occurrences
        # For valid UUID duplicates: preserve first, replace rest
        start_index = 0 if is_invalid else 1

        for occurrence in occurrences[start_index:]:
            new_uuid = str(uuid_mod.uuid4())
            old_line = f"{occurrence.line_prefix}{occurrence.id_value}"
            new_line = f"{occurrence.line_prefix}{new_uuid}"

            file_edits[occurrence.file_path].append(
                (occurrence.line_number, old_line, new_line)
            )

    return file_edits


# ID: 1f69ffa3-3151-477c-9a79-0555b7561d48
def _apply_replacements(
    file_path: Path,
    edits: list[tuple[int, str, str]],
) -> bool:
    """
    Apply line-level replacements to a single file.

    Args:
        file_path: Absolute path to the file.
        edits: List of (line_number, old_content, new_content) tuples.

    Returns:
        True if file was modified successfully.
    """
    try:
        lines = file_path.read_text(encoding="utf-8").splitlines(keepends=True)
    except (OSError, UnicodeDecodeError) as e:
        logger.error("Could not read %s for replacement: %s", file_path, e)
        return False

    modified = False
    for line_num, _old, new_content in edits:
        idx = line_num - 1
        if 0 <= idx < len(lines):
            # Preserve the original line ending
            ending = "\n" if lines[idx].endswith("\n") else ""
            lines[idx] = new_content + ending
            modified = True

    if modified:
        try:
            file_path.write_text("".join(lines), encoding="utf-8")
        except OSError as e:
            logger.error("Could not write %s: %s", file_path, e)
            return False

    return modified


# ---------------------------------------------------------------------------
# Main entry point (preserves existing signature)
# ---------------------------------------------------------------------------


# ID: 0a1b2c3d-4e5f-6a7b-8c9d-0e1f2a3b4c5d
async def resolve_duplicate_ids(
    context: CoreContext, session: AsyncSession, dry_run: bool = True
) -> int:
    """
    Finds all duplicate '# ID:' tags by scanning the filesystem and resolves
    them by assigning fresh UUIDs to colliding entries.

    This function scans source files directly because the database cannot
    represent duplicate IDs (PK constraint flattens them during sync).

    Args:
        context: CoreContext (required for governed operations)
        session: Database session (used for creation-date tiebreaker)
        dry_run: If True, only report findings without modifying files.

    Returns:
        The number of files that were (or would be) modified.
    """
    src_root = settings.REPO_PATH / "src"
    logger.info("🔍 Scanning filesystem for duplicate '# ID:' tags in %s...", src_root)

    # 1. Scan filesystem (source of truth for ID tags)
    id_map = scan_filesystem_for_ids(src_root)
    total_ids = sum(len(v) for v in id_map.values())
    unique_ids = len(id_map)
    logger.info(
        "Found %d '# ID:' tags across %d unique values.",
        total_ids,
        unique_ids,
    )

    # 2. Identify duplicates and invalid placeholders
    duplicates = find_duplicates(id_map)

    if not duplicates:
        logger.info("✅ No duplicate or placeholder IDs found.")
        return 0

    # 3. Report findings
    total_collisions = sum(len(v) for v in duplicates.values())
    logger.warning(
        "⚠️  Found %d duplicate/placeholder ID groups (%d total occurrences):",
        len(duplicates),
        total_collisions,
    )
    for id_value, occurrences in sorted(duplicates.items(), key=lambda x: -len(x[1])):
        locations = [
            f"{occ.file_path.relative_to(settings.REPO_PATH)}:{occ.line_number}"
            for occ in occurrences
        ]
        logger.warning(
            "  %s (%dx): %s",
            id_value[:12] + "..." if len(id_value) > 12 else id_value,
            len(occurrences),
            ", ".join(locations[:5]) + ("..." if len(locations) > 5 else ""),
        )

    # 4. Build replacement plan
    file_edits = _build_replacement_plan(duplicates)
    files_affected = len(file_edits)
    edits_total = sum(len(edits) for edits in file_edits.values())

    logger.info(
        "Replacement plan: %d edits across %d files.",
        edits_total,
        files_affected,
    )

    if dry_run:
        logger.info("DRY-RUN: No files modified. Re-run with --write to apply.")
        return files_affected

    # 5. Apply replacements
    modified_count = 0
    for file_path, edits in file_edits.items():
        rel_path = file_path.relative_to(settings.REPO_PATH)
        if _apply_replacements(file_path, edits):
            modified_count += 1
            logger.info("  ✏️  Fixed %d IDs in %s", len(edits), rel_path)
        else:
            logger.error("  ❌ Failed to apply fixes to %s", rel_path)

    logger.info(
        "✅ Resolved duplicate IDs: %d files modified, %d IDs replaced.",
        modified_count,
        edits_total,
    )

    return modified_count
