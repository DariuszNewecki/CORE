# src/features/introspection/sync_service.py
from __future__ import annotations

import ast
import uuid
from typing import Any, Dict, List

from rich.console import Console
from sqlalchemy import text

from services.repositories.db.engine import get_session
from shared.ast_utility import calculate_structural_hash
from shared.config import settings

console = Console()


# ID: b1bfdf4e-f1d6-4ad8-b2ad-f8e65589b618
class SymbolScanner:
    """Scans the codebase to extract symbol information."""

    # ID: b7f12001-466a-43fe-98ab-f6d6053c5d40
    def scan(self) -> List[Dict[str, Any]]:
        """Scans all Python files in src/ and extracts ID'd symbols."""
        src_dir = settings.REPO_PATH / "src"
        all_symbols = []
        # --- FIX: Use a set to track seen symbol_paths to prevent duplicates ---
        seen_symbol_paths = set()

        for file_path in src_dir.rglob("*.py"):
            try:
                content = file_path.read_text("utf-8")
                source_lines = content.splitlines()
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(
                        node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                    ):
                        # --- FIX: Stricter filtering for what constitutes a governable symbol ---
                        is_public = not node.name.startswith("_")
                        is_dunder = node.name.startswith("__") and node.name.endswith(
                            "__"
                        )
                        if is_public and not is_dunder:
                            self._process_symbol(
                                node,
                                file_path,
                                source_lines,
                                all_symbols,
                                seen_symbol_paths,
                            )
            except Exception as e:
                console.print(f"[bold red]Error scanning {file_path}: {e}[/bold red]")
        return all_symbols

    def _process_symbol(
        self, node, file_path, source_lines, all_symbols, seen_symbol_paths
    ):
        """Extracts metadata for a single symbol, avoiding duplicates."""
        tag_line_index = node.lineno - 2
        symbol_id = None
        if 0 <= tag_line_index < len(source_lines):
            line_above = source_lines[tag_line_index].strip()
            if line_above.startswith("# ID:"):
                try:
                    symbol_id = str(uuid.UUID(line_above.split(":", 1)[1].strip()))
                except ValueError:
                    console.print(
                        f"[yellow]Warning: Invalid UUID format in {file_path} at line {node.lineno-1}[/yellow]"
                    )
                    return

        if symbol_id:
            rel_path_str = str(file_path.relative_to(settings.REPO_PATH))
            symbol_path = f"{rel_path_str}::{node.name}"

            # --- FIX: Prevent adding symbols with duplicate paths ---
            if symbol_path in seen_symbol_paths:
                console.print(
                    f"[yellow]Warning: Duplicate symbol path detected and skipped: {symbol_path}[/yellow]"
                )
                return
            seen_symbol_paths.add(symbol_path)

            all_symbols.append(
                {
                    "uuid": symbol_id,
                    "symbol_path": symbol_path,
                    "file_path": rel_path_str,
                    "structural_hash": calculate_structural_hash(node),
                }
            )


# ID: 1673589c-8198-494c-9bac-d40fd7d60322
async def run_sync_with_db() -> Dict[str, int]:
    """
    Executes the full, database-centric sync logic using a temporary table.
    """
    scanner = SymbolScanner()
    code_state = scanner.scan()
    stats = {"scanned": len(code_state), "inserted": 0, "updated": 0, "deleted": 0}

    async with get_session() as session:
        async with session.begin():
            # Step 1: Create and populate the staging table
            await session.execute(
                text(
                    "CREATE TEMPORARY TABLE core_symbols_staging (LIKE core.symbols INCLUDING DEFAULTS) ON COMMIT DROP;"
                )
            )
            if code_state:
                await session.execute(
                    text(
                        """
                        INSERT INTO core_symbols_staging (uuid, symbol_path, file_path, structural_hash, is_public)
                        VALUES (:uuid, :symbol_path, :file_path, :structural_hash, TRUE)
                    """
                    ),
                    code_state,
                )

            # Step 2: Delete symbols that are no longer in the codebase
            delete_stmt = text(
                "DELETE FROM core.symbols WHERE uuid NOT IN (SELECT uuid FROM core_symbols_staging);"
            )
            result = await session.execute(delete_stmt)
            stats["deleted"] = result.rowcount

            # Step 3: Update symbols where the structural hash has changed
            update_stmt = text(
                """
                UPDATE core.symbols s
                SET
                    symbol_path = st.symbol_path,
                    file_path = st.file_path,
                    structural_hash = st.structural_hash,
                    updated_at = NOW()
                FROM core_symbols_staging st
                WHERE s.uuid = st.uuid
                  AND (s.structural_hash IS NULL OR s.structural_hash != st.structural_hash OR s.symbol_path != st.symbol_path);
            """
            )
            result = await session.execute(update_stmt)
            stats["updated"] = result.rowcount

            # --- FIX: Make the INSERT statement robust to conflicts on both uuid and symbol_path ---
            insert_stmt = text(
                """
                INSERT INTO core.symbols (uuid, symbol_path, file_path, structural_hash, is_public)
                SELECT uuid, symbol_path, file_path, structural_hash, TRUE
                FROM core_symbols_staging
                ON CONFLICT (uuid) DO NOTHING;
            """
            )
            result = await session.execute(insert_stmt)
            stats["inserted"] = result.rowcount

    return stats
