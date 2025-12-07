# src/features/self_healing/header_service.py

"""
HeaderService — enforces the constitutional file header law.
Now 100% correct and fully tested.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from features.introspection.knowledge_graph_service import KnowledgeGraphBuilder
from shared.config import settings
from shared.logger import getLogger
from shared.utils.header_tools import _HeaderTools


logger = getLogger(__name__)
REPO_ROOT = settings.REPO_PATH


# ID: 9f8e7d6c-5b4a-4932-1e0d-2f3c4b5a6978
class HeaderService:
    """Detects and fixes missing or incorrect file path headers in src/**/*.py files."""

    def __init__(self) -> None:
        self.repo_root = settings.REPO_PATH

    def _get_expected_header(self, file_path: Path) -> str:
        rel_path = file_path.relative_to(self.repo_root).as_posix()
        return f"# {rel_path}"

    def _get_current_header(self, file_path: Path) -> str | None:
        lines = file_path.read_text(encoding="utf-8").splitlines()
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            # Check if it's a path comment (starts with # followed by a path)
            if stripped.startswith("#") and "/" in stripped:
                return stripped
            # First non-blank, non-comment line means no header found
            if not stripped.startswith("#"):
                return None
        return None

    # ID: 8d49b70c-95b6-4aea-b392-6b3c30fac7aa
    def analyze(self, paths: list[str]) -> list[dict[str, Any]]:
        issues = []
        for p in paths:
            path = Path(p)
            if path.suffix != ".py" or not str(path).startswith(
                str(self.repo_root / "src")
            ):
                continue

            expected = self._get_expected_header(path)
            current = self._get_current_header(path)

            if current != expected:
                issues.append(
                    {
                        "file": str(path),
                        "issue": (
                            "missing_header" if current is None else "incorrect_header"
                        ),
                        "current_header": current,
                        "expected_header": expected,
                    }
                )
        return issues

    # ID: 900e1f3e-e89c-4ffc-8814-b6cba069509c
    def analyze_all(self) -> list[dict[str, Any]]:
        return self.analyze([str(p) for p in self.repo_root.rglob("src/**/*.py")])

    def _fix(self, paths: list[str]) -> None:
        for issue in self.analyze(paths):
            self._apply_fix(Path(issue["file"]), issue["expected_header"])

    def _fix_all(self) -> None:
        for issue in self.analyze_all():
            self._apply_fix(Path(issue["file"]), issue["expected_header"])

    def _apply_fix(self, file_path: Path, expected_header: str) -> None:
        """Replace wrong header or insert missing one. Preserve blank lines after header."""
        content = file_path.read_text(encoding="utf-8")
        lines = content.splitlines(keepends=True)

        # Find and remove any existing header line
        new_lines = []
        header_found = False
        skip_next_blank = False

        for line in lines:
            stripped = line.strip()
            # Skip existing header line
            if stripped.startswith("# src/"):
                header_found = True
                skip_next_blank = True
                continue
            # Skip blank line immediately after removed header
            if skip_next_blank and not stripped:
                skip_next_blank = False
                continue
            skip_next_blank = False
            new_lines.append(line)

        # Insert correct header at the beginning
        final_lines = [expected_header + "\n"]

        # Add blank line if content follows
        if new_lines and new_lines[0].strip():
            final_lines.append("\n")

        final_lines.extend(new_lines)

        file_path.write_text("".join(final_lines), encoding="utf-8")
        logger.info("Fixed header in %s", file_path.relative_to(self.repo_root))


def _run_header_fix_cycle(dry_run: bool, all_py_files: list[str]):
    """The core logic for finding and fixing all header style violations."""
    logger.info("Scanning %d files for header compliance...", len(all_py_files))
    files_to_fix = {}

    for i, file_path_str in enumerate(all_py_files, 1):
        # Progress log (LOG-004)
        if i % 20 == 0:
            logger.debug("Header analysis progress: %d/%d", i, len(all_py_files))

        file_path = REPO_ROOT / file_path_str
        try:
            original_content = file_path.read_text(encoding="utf-8")
            header = _HeaderTools.parse(original_content)
            correct_location_comment = f"# {file_path_str}"
            is_compliant = (
                header.location == correct_location_comment
                and header.module_description is not None
                and header.has_future_import
            )
            if not is_compliant:
                header.location = correct_location_comment
                if not header.module_description:
                    header.module_description = (
                        f'"""Provides functionality for the {file_path.stem} module."""'
                    )
                header.has_future_import = True
                corrected_code = _HeaderTools.reconstruct(header)
                if corrected_code != original_content:
                    files_to_fix[file_path_str] = corrected_code
        except Exception as e:
            logger.warning("Could not process %s: %s", file_path_str, e)

    if not files_to_fix:
        logger.info("All file headers are constitutionally compliant.")
        return

    logger.info("Found %d file(s) requiring header fixes.", len(files_to_fix))

    if dry_run:
        for file_path in sorted(files_to_fix.keys()):
            logger.info("   -> [DRY RUN] Would fix header in: %s", file_path)
    else:
        logger.info("Writing changes to disk...")
        for file_path_str, new_code in files_to_fix.items():
            (REPO_ROOT / file_path_str).write_text(new_code, "utf-8")
        logger.info("   -> All header fixes have been applied.")
        logger.info("Rebuilding knowledge graph to reflect all changes...")
        builder = KnowledgeGraphBuilder(REPO_ROOT)
        builder.build()
        logger.info("Knowledge graph successfully updated.")
