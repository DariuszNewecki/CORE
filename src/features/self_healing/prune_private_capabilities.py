# src/features/self_healing/prune_private_capabilities.py

"""
A self-healing tool that scans the codebase and removes # CAPABILITY tags
from private symbols (those starting with an underscore), enforcing the
'caps.ignore_private' constitutional policy.
"""

from __future__ import annotations

import asyncio
import re

import typer

from shared.config import settings
from shared.infrastructure.knowledge_service import KnowledgeService
from shared.logger import getLogger


logger = getLogger(__name__)
REPO_ROOT = settings.REPO_PATH


# ID: 8b4c4e45-0236-4af1-9d76-1483e8b96a4a
def main(
    write: bool = typer.Option(
        False, "--write", help="Apply fixes and remove tags from source files."
    ),
):
    """
    Finds and removes capability tags from private symbols (_ or __).
    """
    dry_run = not write
    logger.info("🐍 Pruning capability tags from private symbols...")

    async def _async_main():
        knowledge_service = KnowledgeService(REPO_ROOT)
        graph = await knowledge_service.get_graph()
        symbols = graph.get("symbols", {})
        private_symbols_with_tags = [
            s
            for s in symbols.values()
            if s.get("name", "").startswith("_")
            and s.get("capability") != "unassigned"
            and (s.get("capability") is not None)
        ]
        if not private_symbols_with_tags:
            logger.info(
                "✅ No private symbols with capability tags found. Compliance is perfect."
            )
            return
        logger.info(
            f"Found {len(private_symbols_with_tags)} private symbol(s) with capability tags."
        )
        files_to_modify = {}
        tag_pattern = re.compile("^\\s*#\\s*CAPABILITY:\\s*\\S+\\s*$", re.IGNORECASE)
        for symbol in private_symbols_with_tags:
            file_path_str = symbol.get("file")
            if not file_path_str:
                continue
            file_path = settings.paths.repo_root / file_path_str
            line_num = symbol.get("line_number", 0)
            if file_path not in files_to_modify:
                if file_path.exists():
                    files_to_modify[file_path] = file_path.read_text(
                        "utf-8"
                    ).splitlines()
                else:
                    logger.warning(
                        f"File not found for symbol {symbol['symbol_path']}: {file_path}"
                    )
                    continue
            tag_line_index = line_num - 2
            if 0 <= tag_line_index < len(files_to_modify[file_path]):
                line_to_check = files_to_modify[file_path][tag_line_index]
                if tag_pattern.match(line_to_check):
                    logger.info(
                        f"   -> Planning to remove tag for '{symbol['name']}' in {file_path_str}"
                    )
                    files_to_modify[file_path][tag_line_index] = "__DELETE_THIS_LINE__"
        if dry_run:
            logger.info("-- DRY RUN: No files will be changed --")
            return
        logger.info("Applying fixes to source files...")
        for file_path, lines in files_to_modify.items():
            new_content = (
                "\n".join([line for line in lines if line != "__DELETE_THIS_LINE__"])
                + "\n"
            )
            file_path.write_text(new_content, "utf-8")
            logger.info(f"  - ✅ Pruned tags from {file_path.relative_to(REPO_ROOT)}")

    asyncio.run(_async_main())


if __name__ == "__main__":
    typer.run(main)
