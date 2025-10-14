# src/features/self_healing/header_service.py
"""
The orchestration logic for the unified header fixer, which uses a deterministic
tool to enforce constitutional style rules on Python file headers.
"""

from __future__ import annotations

import asyncio

from rich.progress import track

from features.introspection.knowledge_graph_service import KnowledgeGraphBuilder
from shared.config import settings
from shared.logger import getLogger
from shared.utils.header_tools import HeaderTools

log = getLogger("core_admin.fixer")
REPO_ROOT = settings.REPO_PATH


def _run_header_fix_cycle(dry_run: bool, all_py_files: list[str]):
    """The core logic for finding and fixing all header style violations."""
    log.info(f"Scanning {len(all_py_files)} files for header compliance...")

    files_to_fix = {}
    for file_path_str in track(all_py_files, description="Analyzing headers..."):
        file_path = REPO_ROOT / file_path_str
        try:
            original_content = file_path.read_text(encoding="utf-8")
            header = HeaderTools.parse(original_content)

            # Check for violations that need fixing
            correct_location_comment = f"# {file_path_str}"
            is_compliant = (
                header.location == correct_location_comment
                and header.module_description is not None
                and header.has_future_import
            )

            if not is_compliant:
                header.location = correct_location_comment
                if not header.module_description:
                    # Provide a default, high-quality docstring
                    header.module_description = (
                        f'"""Provides functionality for the {file_path.stem} module."""'
                    )
                header.has_future_import = True

                corrected_code = HeaderTools.reconstruct(header)
                if corrected_code != original_content:
                    files_to_fix[file_path_str] = corrected_code

        except Exception as e:
            log.warning(f"Could not process {file_path_str}: {e}")

    if not files_to_fix:
        log.info("✅ All file headers are constitutionally compliant.")
        return

    log.info(f"Found {len(files_to_fix)} file(s) requiring header fixes.")

    if dry_run:
        for file_path in sorted(files_to_fix.keys()):
            log.info(f"   -> [DRY RUN] Would fix header in: {file_path}")
    else:
        log.info("💾 Writing changes to disk...")
        for file_path_str, new_code in files_to_fix.items():
            (REPO_ROOT / file_path_str).write_text(new_code, "utf-8")
        log.info("   -> ✅ All header fixes have been applied.")

        # Rebuild the knowledge graph after making changes
        log.info("🧠 Rebuilding knowledge graph to reflect all changes...")
        builder = KnowledgeGraphBuilder(REPO_ROOT)
        asyncio.run(builder.build_and_sync())
        log.info("✅ Knowledge graph successfully updated.")
