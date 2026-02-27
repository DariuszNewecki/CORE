# src/features/test_generation/persistence.py

"""
Test Persistence Service

Purpose:
- Promote generated tests that passed sandbox execution into /tests using a mirrored
  directory structure that matches the originating src/ path.
- Extract and save individual passing tests from files with mixed results.
- Quarantine complete failures outside /tests into a "morgue" under var/artifacts/.

Constitutional Alignment:
- Path Mirroring: Reconstructs src/ structure within tests/ for successful artifacts.
- Surgical Extraction: Saves individual passing tests even when some fail.
- Body Hygiene: Prevents known-failed tests from polluting the /tests directory.
- Traceable Persistence: Routes failures to var/artifacts for audit and debugging.
- Governed Mutation: All directory creation and writes go through FileHandler.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from body.services.file_service import FileService
from shared.logger import getLogger


logger = getLogger(__name__)


@dataclass(frozen=True)
# ID: 0fa80b24-245c-4aa7-9b4d-0d11b9d93f32
class PersistResult:
    """Result of a persistence operation."""

    ok: bool
    path: str = ""
    error: str = ""
    tests_saved: int = 0  # Number of individual tests saved


# ID: 8b6e2c1b-4e11-4b7a-a077-5e2856e44a38
class TestPersistenceService:
    """
    Handles the promotion of verified tests and the isolation of failures.
    Ensures the /tests directory only contains sandbox-passing code.
    """

    def __init__(self, file_handler: FileService):
        self._fh = file_handler

    # ID: 55c23007-2524-4721-a88f-c35a9f660cfe
    def persist(
        self, original_file: str, symbol_name: str, test_code: str
    ) -> PersistResult:
        """
        Promote a successful test to its mirrored location in /tests.

        Example:
            src/shared/utils/text.py -> tests/shared/utils/test_text__my_symbol.py
        """
        try:
            rel_target = self._calculate_mirrored_path(original_file, symbol_name)

            stamp = time.strftime("%Y-%m-%d %H:%M:%S")
            header = (
                '"""AUTO-GENERATED TEST (PROMOTED)\n'
                f"- Source: {original_file}\n"
                f"- Symbol: {symbol_name}\n"
                "- Status: verified_in_sandbox\n"
                f"- Generated: {stamp}\n"
                '"""\n\n'
            )

            target_dir = str(Path(rel_target).parent)
            self._fh.ensure_dir(target_dir)
            self._fh.write_runtime_text(rel_target, header + test_code)

            logger.info("Test promoted to mirrored path: %s", rel_target)
            return PersistResult(ok=True, path=rel_target, error="", tests_saved=1)

        except Exception as e:
            logger.error("Failed to promote test: %s", e, exc_info=True)
            return PersistResult(ok=False, path="", error=str(e), tests_saved=0)

    # ID: 8549f483-e4b8-4520-8778-772b51b0b419
    def persist_quarantined(
        self,
        original_file: str,
        symbol_name: str,
        test_code: str,
        sandbox_passed: bool,
        passing_test_names: list[str] | None = None,
    ) -> PersistResult:
        """
        Policy:
        - If sandbox passed completely: promote entire file to /tests (mirrored).
        - If sandbox partially passed: extract passing tests and promote those.
        - If sandbox failed completely: route to var/artifacts/test_gen/failures/ (morgue).

        Args:
            original_file: Source file that was tested
            symbol_name: Symbol that was tested
            test_code: Generated test code
            sandbox_passed: True if ALL tests passed
            passing_test_names: List of individual test names that passed
        """
        # Case 1: All tests passed - promote entire file
        if sandbox_passed:
            return self.persist(original_file, symbol_name, test_code)

        # Case 2: Some tests passed - extract and promote those
        if passing_test_names and len(passing_test_names) > 0:
            return self._persist_partial_success(
                original_file, symbol_name, test_code, passing_test_names
            )

        # Case 3: All tests failed - route to morgue
        return self._persist_to_morgue(original_file, symbol_name, test_code)

    def _persist_partial_success(
        self,
        original_file: str,
        symbol_name: str,
        test_code: str,
        passing_test_names: list[str],
    ) -> PersistResult:
        """
        Extract passing tests and promote them, while routing failures to morgue.
        """
        try:
            from will.test_generation.test_extractor import TestCodeExtractor

            extractor = TestCodeExtractor()
            passing_code = extractor.extract_passing_tests(
                test_code, passing_test_names
            )

            if not passing_code:
                logger.warning(
                    "Failed to extract passing tests for %s, routing to morgue",
                    symbol_name,
                )
                return self._persist_to_morgue(original_file, symbol_name, test_code)

            # Promote passing tests
            rel_target = self._calculate_mirrored_path(original_file, symbol_name)
            stamp = time.strftime("%Y-%m-%d %H:%M:%S")
            header = (
                '"""AUTO-GENERATED TEST (PARTIAL SUCCESS)\n'
                f"- Source: {original_file}\n"
                f"- Symbol: {symbol_name}\n"
                f"- Status: {len(passing_test_names)} tests passed, some failed\n"
                f"- Passing tests: {', '.join(passing_test_names)}\n"
                f"- Generated: {stamp}\n"
                '"""\n\n'
            )

            target_dir = str(Path(rel_target).parent)
            self._fh.ensure_dir(target_dir)
            self._fh.write_runtime_text(rel_target, header + passing_code)

            # Also save full code (with failures) to morgue for analysis
            self._persist_to_morgue(
                original_file, symbol_name + "_FULL", test_code, is_partial=True
            )

            logger.info(
                "✅ Promoted %d passing tests to: %s",
                len(passing_test_names),
                rel_target,
            )
            logger.info("📋 Full code (with failures) saved to morgue for analysis")

            return PersistResult(
                ok=True,
                path=rel_target,
                error="",
                tests_saved=len(passing_test_names),
            )

        except Exception as e:
            logger.error("Failed to persist partial success: %s", e, exc_info=True)
            return self._persist_to_morgue(original_file, symbol_name, test_code)

    def _persist_to_morgue(
        self,
        original_file: str,
        symbol_name: str,
        test_code: str,
        is_partial: bool = False,
    ) -> PersistResult:
        """Route failed tests to the morgue for analysis."""
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            stem = Path(original_file).stem
            safe_symbol = self._sanitize_symbol(symbol_name)

            morgue_dir = "var/artifacts/test_gen/failures"
            rel_target = f"{morgue_dir}/{timestamp}_{stem}__{safe_symbol}.py"

            status = "partial_failure" if is_partial else "sandbox_failed"
            header = (
                '"""AUTO-GENERATED TEST (MORGUE)\n'
                f"- Source: {original_file}\n"
                f"- Symbol: {symbol_name}\n"
                f"- Status: {status}\n"
                f"- Failed-At: {timestamp}\n"
                '"""\n\n'
            )

            self._fh.ensure_dir(morgue_dir)
            self._fh.write_runtime_text(rel_target, header + test_code)

            logger.warning("Test routed to morgue: %s", rel_target)
            return PersistResult(ok=True, path=rel_target, error=status, tests_saved=0)

        except Exception as e:
            logger.error("Failed to isolate failed test: %s", e, exc_info=True)
            return PersistResult(ok=False, path="", error=str(e), tests_saved=0)

    def _calculate_mirrored_path(self, original_file: str, symbol_name: str) -> str:
        """
        Calculate the /tests equivalent of a src/ path.

        Rules:
        - If original_file starts with "src/", strip that prefix.
        - Keep the remaining directory structure under "tests/".
        - Filename: test_{stem}__{safe_symbol}.py
        """
        path_obj = Path(original_file)
        parts = list(path_obj.parts)

        if parts and parts[0] == "src":
            parts.pop(0)

        stem = path_obj.stem
        safe_symbol = self._sanitize_symbol(symbol_name)
        test_filename = f"test_{stem}__{safe_symbol}.py"

        mirrored = Path("tests").joinpath(*parts[:-1], test_filename)
        return mirrored.as_posix()

    def _sanitize_symbol(self, name: str) -> str:
        """Convert symbol name to a filename-safe string."""
        return "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in name)
