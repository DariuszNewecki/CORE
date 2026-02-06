# src/features/self_healing/handlers/import_sorting_handler.py
"""
Import sorting handler for audit remediation.

This is a SINGLE-FILE fixer that takes one audit finding and fixes
just that file's import ordering.

Different from the CLI command which fixes the whole codebase,
this works on individual files as directed by audit findings.

Uses ruff under the hood, but wraps it in the remediation interface.
"""

from __future__ import annotations

import time
from pathlib import Path

from features.self_healing.remediation_models import FixResult
from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger
from shared.models import AuditFinding


logger = getLogger(__name__)


# ID: TBD (will be assigned by dev-sync)
# ID: fb0168b4-bf66-496f-a739-0fed60bc6f5a
async def sort_imports_handler(
    finding: AuditFinding,
    file_handler: FileHandler,
    repo_root: Path,
    write: bool,
) -> FixResult:
    """
    Fix import ordering in a single file using ruff.

    This handler:
    1. Takes the file path from the audit finding
    2. Runs ruff's import sorter on JUST that file
    3. If write=True, re-writes the file via FileHandler (constitutional compliance)
    4. Returns success/failure status

    Args:
        finding: The audit finding that identified the import problem
        file_handler: Constitutional write gateway (ensures IntentGuard enforcement)
        repo_root: Repository root for path resolution
        write: If False, just check if fix would work (dry-run)

    Returns:
        FixResult indicating success/failure

    Example:
        # From audit finding: "Imports not sorted in src/body/cli/admin_cli.py"
        result = await sort_imports_handler(
            finding=finding,
            file_handler=file_handler,
            repo_root=Path("/opt/dev/CORE"),
            write=True
        )
        # Result: FixResult(ok=True, error_message=None, changes_made={"sorted": True})
    """

    start_time = time.time()

    # Step 1: Get the file path from the finding
    if not finding.file_path:
        logger.warning("Finding has no file_path, cannot fix: %s", finding.message)
        return FixResult(
            ok=False,
            error_message="No file path in finding",
            changes_made=None,
        )

    # Step 2: Resolve absolute path
    file_path = repo_root / finding.file_path

    if not file_path.exists():
        logger.error("File does not exist: %s", file_path)
        return FixResult(
            ok=False,
            error_message=f"File not found: {finding.file_path}",
            changes_made=None,
        )

    # Step 3: Read original content (for comparison and re-writing)
    try:
        original_content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error("Failed to read file %s: %s", file_path, e)
        return FixResult(
            ok=False,
            error_message=f"Read failed: {e!s}",
            changes_made=None,
        )

    # Step 4: Run ruff on this specific file
    try:
        # Build the ruff command
        # --select I = import sorting rules
        # --fix = actually fix the file
        # --exit-zero = don't return error code on violations
        cmd = [
            "ruff",
            "check",
            str(file_path),
            "--select",
            "I",  # Import sorting rules
            "--exit-zero",  # Don't fail on violations found
        ]

        if write:
            cmd.append("--fix")

        # Run ruff asynchronously to avoid blocking event loop (ASYNC221 compliance)
        import asyncio

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        _stdout_bytes, _stderr_bytes = await process.communicate()

        # Ruff writes directly to the file, so we need to read it back
        if write:
            # Step 5: Read the modified content
            try:
                new_content = file_path.read_text(encoding="utf-8")
            except Exception as e:
                logger.error("Failed to read modified file %s: %s", file_path, e)
                return FixResult(
                    ok=False,
                    error_message=f"Post-fix read failed: {e!s}",
                    changes_made=None,
                )

            # Step 6: Check if anything actually changed
            if new_content == original_content:
                # No changes needed - imports were already sorted
                duration_ms = int((time.time() - start_time) * 1000)
                logger.info(
                    "No changes needed for %s (already sorted)", finding.file_path
                )
                return FixResult(
                    ok=True,
                    error_message=None,
                    changes_made={
                        "imports_changed": False,
                        "already_sorted": True,
                        "duration_ms": duration_ms,
                    },
                )

            # Step 7: Re-write via FileHandler for constitutional compliance
            # This ensures IntentGuard validates the write
            try:
                # Convert to repo-relative path
                rel_path = str(file_path.relative_to(repo_root))

                # Write via FileHandler (constitutional gateway)
                file_handler.write_source_code(rel_path, new_content)

                duration_ms = int((time.time() - start_time) * 1000)

                logger.info(
                    "Successfully sorted imports in %s (%d ms)",
                    finding.file_path,
                    duration_ms,
                )

                return FixResult(
                    ok=True,
                    error_message=None,
                    changes_made={
                        "imports_changed": True,
                        "duration_ms": duration_ms,
                        "file_path": rel_path,
                    },
                )

            except Exception as e:
                logger.error("Failed to write via FileHandler: %s", e)
                return FixResult(
                    ok=False,
                    error_message=f"FileHandler write failed: {e!s}",
                    changes_made=None,
                )

        else:
            # Dry-run mode - just report that we COULD fix it
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info("Dry-run: Would sort imports in %s", finding.file_path)

            return FixResult(
                ok=True,
                error_message=None,
                changes_made={
                    "dry_run": True,
                    "would_fix": True,
                    "duration_ms": duration_ms,
                },
            )

    except Exception as e:
        logger.error("Ruff execution failed: %s", e)
        return FixResult(
            ok=False,
            error_message=f"Ruff failed: {e!s}",
            changes_made=None,
        )


# Convenience function for testing
# ID: 4ef99bc7-2149-4aba-b25a-446d7caa1392
async def test_handler():
    """
    Quick test function to verify the handler works.

    You can run this from a Python shell:
        from features.self_healing.handlers.import_sorting_handler import test_handler
        import asyncio
        asyncio.run(test_handler())
    """
    from shared.config import settings
    from shared.models import AuditSeverity

    # Create a fake finding
    test_finding = AuditFinding(
        check_id="style.import_order",
        severity=AuditSeverity.WARNING,
        message="Imports not sorted",
        file_path="src/body/cli/admin_cli.py",
        line_number=None,
    )

    # Create file handler
    file_handler = FileHandler(str(settings.REPO_PATH))

    # Test dry-run
    result = await sort_imports_handler(
        finding=test_finding,
        file_handler=file_handler,
        repo_root=settings.REPO_PATH,
        write=False,
    )

    print(f"Test result: {result}")
    return result
