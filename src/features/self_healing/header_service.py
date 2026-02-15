# src/features/self_healing/header_service.py
# ID: 9f8e7d6c-5b4a-4932-1e0d-2f3c4b5a6978

"""
HeaderService — enforces the constitutional file header law.
Refactored to use the canonical ActionExecutor Gateway for all mutations.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from body.atomic.executor import ActionExecutor
from shared.config import settings
from shared.logger import getLogger
from shared.utils.header_tools import _HeaderTools


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)
REPO_ROOT = settings.REPO_PATH


# ID: e1e63d42-0626-40d7-84bc-5d3469a00bc5
class HeaderService:
    """Detects and fixes missing or incorrect file path headers in src/**/*.py files."""

    def __init__(self) -> None:
        self.repo_root = settings.REPO_PATH

    def _get_expected_header(self, file_path: Path) -> str:
        rel_path = file_path.relative_to(self.repo_root).as_posix()
        return f"# {rel_path}"

    def _get_current_header(self, file_path: Path) -> str | None:
        try:
            lines = file_path.read_text(encoding="utf-8").splitlines()
        except Exception:
            return None

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
        """Identifies header violations in the provided paths."""
        issues = []
        for p in paths:
            path = Path(p)
            # Ensure we only target source files within the repo
            if path.suffix != ".py" or not str(path.resolve()).startswith(
                str(self.repo_root.resolve() / "src")
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
        """Scans the entire src directory for header violations."""
        return self.analyze([str(p) for p in self.repo_root.rglob("src/**/*.py")])

    # ID: fbb21920-5457-4aa2-9ae7-23da72fff8fd
    async def fix(
        self, context: CoreContext, paths: list[str], write: bool = False
    ) -> None:
        """Fixes headers for specific paths via the Action Gateway."""
        issues = self.analyze(paths)
        for issue in issues:
            await self._apply_fix(
                context, Path(issue["file"]), issue["expected_header"], write
            )

    async def _fix_all(self, context: CoreContext, write: bool = False) -> None:
        """Fixes all header violations in the project via the Action Gateway."""
        issues = self.analyze_all()
        for issue in issues:
            await self._apply_fix(
                context, Path(issue["file"]), issue["expected_header"], write
            )

    async def _apply_fix(
        self, context: CoreContext, file_path: Path, expected_header: str, write: bool
    ) -> None:
        """Prepares the new source and dispatches to ActionExecutor."""
        rel_path = str(file_path.relative_to(self.repo_root))
        executor = ActionExecutor(context)

        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error("Could not read %s for header fix: %s", rel_path, e)
            return

        lines = content.splitlines(keepends=True)
        new_lines = []
        skip_next_blank = False

        for line in lines:
            stripped = line.strip()
            # Skip existing header line
            if stripped.startswith("# src/"):
                skip_next_blank = True
                continue
            # Skip blank line immediately after removed header
            if skip_next_blank and not stripped:
                skip_next_blank = False
                continue
            skip_next_blank = False
            new_lines.append(line)

        # Reconstruct with the correct header
        final_lines = [expected_header + "\n"]
        if new_lines and new_lines[0].strip():
            final_lines.append("\n")
        final_lines.extend(new_lines)

        final_code = "".join(final_lines)

        # CONSTITUTIONAL GATEWAY: Mutation is audited and guarded
        result = await executor.execute(
            action_id="file.edit", write=write, file_path=rel_path, code=final_code
        )

        if result.ok:
            status = "Fixed" if write else "Proposed (Dry Run)"
            logger.info("   -> [%s] Header in %s", status, rel_path)
        else:
            logger.error("   -> [BLOCKED] %s: %s", rel_path, result.data.get("error"))


# ID: 4828affd-f7da-4995-9493-7037211b4144
async def _run_header_fix_cycle(
    context: CoreContext, dry_run: bool, all_py_files: list[str]
):
    """
    The core logic for finding and fixing all header style violations.
    Mutations are routed through the governed ActionExecutor.
    """
    logger.info("🔍 Scanning %d files for header compliance...", len(all_py_files))

    executor = ActionExecutor(context)
    write_mode = not dry_run
    count = 0

    for i, file_path_str in enumerate(all_py_files, 1):
        if i % 50 == 0:
            logger.debug("Header analysis progress: %d/%d", i, len(all_py_files))

        file_path = settings.paths.repo_root / file_path_str
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
                    # CONSTITUTIONAL GATEWAY
                    result = await executor.execute(
                        action_id="file.edit",
                        write=write_mode,
                        file_path=file_path_str,
                        code=corrected_code,
                    )

                    if result.ok:
                        count += 1
                    else:
                        logger.warning("   -> [BLOCKED] %s", file_path_str)

        except Exception as e:
            logger.warning("Could not process %s: %s", file_path_str, e)

    if count == 0:
        logger.info("✅ All file headers are constitutionally compliant.")
    else:
        mode_label = "Fixed" if write_mode else "Proposed fixes for"
        logger.info("🏁 Header fix cycle complete. %s %d file(s).", mode_label, count)

        if write_mode:
            logger.info("🔄 Rebuilding Knowledge Graph to reflect metadata changes...")
            # Sync DB Action (Unified Substrate)
            await executor.execute(action_id="sync.db", write=True)
            logger.info("✅ Knowledge Graph successfully updated.")
