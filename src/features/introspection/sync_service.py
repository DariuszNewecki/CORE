# src/features/introspection/sync_service.py
from __future__ import annotations

import ast
import uuid
from typing import Any, Dict, List, Set

from rich.console import Console
from sqlalchemy import text

from services.database.session_manager import get_session
from shared.ast_utility import calculate_structural_hash
from shared.config import settings

console = Console()


# ID: 9b343ade-594e-4bd8-9580-3d32c84d4f2b
class SymbolVisitor(ast.NodeVisitor):
    """An AST visitor that discovers symbols and their hierarchical paths."""

    def __init__(self, file_path: str, source_lines: List[str], seen_uuids: Set[str]):
        self.file_path = file_path
        self.source_lines = source_lines
        self.symbols: List[Dict[str, Any]] = []
        self.class_stack: List[str] = []
        self.seen_uuids = seen_uuids

    # ID: 89431690-9e7a-40e1-bb4c-d2ad247a5277
    def visit_ClassDef(self, node: ast.ClassDef):
        """Process a class definition and its children (methods)."""
        if not self.class_stack:
            self._process_symbol(node)

        self.class_stack.append(node.name)
        self.generic_visit(node)
        self.class_stack.pop()

    # ID: 0bfa9ab7-a83a-4d58-aa5d-6c6769af4e4f
    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Process a function or method definition."""
        if not self.class_stack:
            self._process_symbol(node)

    # ID: 8e860945-daec-4ffa-a5ac-3c669082ff8a
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Process an async function or method definition."""
        if not self.class_stack:
            self._process_symbol(node)

    def _process_symbol(
        self, node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
    ):
        """Extracts metadata for a single symbol, respecting its context."""
        is_public = not node.name.startswith("_")
        is_dunder = node.name.startswith("__") and node.name.endswith("__")
        if not (is_public and not is_dunder):
            return

        tag_line_index = node.lineno - 2
        symbol_id = None
        if 0 <= tag_line_index < len(self.source_lines):
            line_above = self.source_lines[tag_line_index].strip()
            if line_above.startswith("# ID:"):
                try:
                    symbol_id = str(uuid.UUID(line_above.split(":", 1)[1].strip()))
                except ValueError:
                    return

        if symbol_id:
            if symbol_id in self.seen_uuids:
                console.print(
                    f"[bold red]CRITICAL WARNING: Duplicate UUID '{symbol_id}' found in '{self.file_path}' for symbol '{node.name}'. Skipping.[/bold red]"
                )
                return
            self.seen_uuids.add(symbol_id)

            if self.class_stack:
                class_path = ".".join(self.class_stack)
                symbol_path = f"{self.file_path}::{class_path}"
            else:
                symbol_path = f"{self.file_path}::{node.name}"

            # --- START OF FIX ---
            # Generate the data structure that matches the new 'core.symbols' table schema.
            # We derive 'module', 'qualname', 'kind', etc.
            module_name = self.file_path.replace("src/", "").replace(".py", "").replace("/", ".")
            kind_map = {"ClassDef": "class", "FunctionDef": "function", "AsyncFunctionDef": "function"}
            
            self.symbols.append(
                {
                    "id": uuid.uuid5(uuid.NAMESPACE_DNS, symbol_path), # Use deterministic UUID for primary key
                    "uuid": symbol_id,
                    "symbol_path": symbol_path,
                    "module": module_name,
                    "qualname": node.name,
                    "kind": kind_map.get(type(node).__name__, "function"),
                    "ast_signature": "TBD", # Placeholder for now
                    "fingerprint": calculate_structural_hash(node),
                    "state": "discovered",
                    "is_public": True,
                }
            )
            # --- END OF FIX ---


# ID: b1bfdf4e-f1d6-4ad8-b2ad-f8e65589b618
class SymbolScanner:
    """Scans the codebase to extract symbol information using a hierarchical visitor."""

    # ID: b7f12001-466a-43fe-98ab-f6d6053c5d40
    def scan(self) -> List[Dict[str, Any]]:
        """Scans all Python files in src/ and extracts ID'd symbols."""
        src_dir = settings.REPO_PATH / "src"
        all_symbols = []
        seen_uuids: Set[str] = set()

        for file_path in src_dir.rglob("*.py"):
            try:
                content = file_path.read_text("utf-8")
                source_lines = content.splitlines()
                tree = ast.parse(content, filename=str(file_path))

                rel_path_str = str(file_path.relative_to(settings.REPO_PATH))
                visitor = SymbolVisitor(rel_path_str, source_lines, seen_uuids)
                visitor.visit(tree)
                all_symbols.extend(visitor.symbols)
            except Exception as e:
                console.print(f"[bold red]Error scanning {file_path}: {e}[/bold red]")

        unique_symbols = {s["symbol_path"]: s for s in all_symbols}
        return list(unique_symbols.values())


# ID: 1673589c-8198-494c-9bac-d40fd7d60322
async def run_sync_with_db() -> Dict[str, int]:
    """
    Executes the full, database-centric sync logic using the "smart merge" strategy.
    """
    scanner = SymbolScanner()
    code_state = scanner.scan()
    stats = {"scanned": len(code_state), "inserted": 0, "updated": 0, "deleted": 0}

    async with get_session() as session:
        async with session.begin():
            # 1. Create and populate the staging table with the full code state
            await session.execute(
                text(
                    "CREATE TEMPORARY TABLE core_symbols_staging (LIKE core.symbols INCLUDING DEFAULTS) ON COMMIT DROP;"
                )
            )
            if code_state:
                # --- START OF FIX ---
                # The INSERT statement now matches the new schema and the data generated
                # by the updated SymbolVisitor.
                await session.execute(
                    text(
                        """
                        INSERT INTO core_symbols_staging (id, uuid, symbol_path, module, qualname, kind, ast_signature, fingerprint, state, is_public)
                        VALUES (:id, :uuid, :symbol_path, :module, :qualname, :kind, :ast_signature, :fingerprint, :state, :is_public)
                    """
                    ),
                    code_state,
                )
                # --- END OF FIX ---

            # 2. Get stats for reporting
            deleted_result = await session.execute(
                text(
                    "SELECT COUNT(*) FROM core.symbols WHERE uuid NOT IN (SELECT uuid FROM core_symbols_staging)"
                )
            )
            stats["deleted"] = deleted_result.scalar_one()

            inserted_result = await session.execute(
                text(
                    "SELECT COUNT(*) FROM core_symbols_staging WHERE uuid NOT IN (SELECT uuid FROM core.symbols)"
                )
            )
            stats["inserted"] = inserted_result.scalar_one()

            updated_result = await session.execute(
                text(
                    """
                    SELECT COUNT(*) FROM core.symbols s
                    JOIN core_symbols_staging st ON s.uuid = st.uuid
                    WHERE s.fingerprint != st.fingerprint
                """
                )
            )
            stats["updated"] = updated_result.scalar_one()

            # 3. Apply the "smart merge" logic
            # 3a. Delete symbols that no longer exist in the code
            await session.execute(
                text(
                    "DELETE FROM core.symbols WHERE uuid NOT IN (SELECT uuid FROM core_symbols_staging)"
                )
            )

            # 3b. Nullify key and vector_id for symbols whose structure has changed (using fingerprint)
            await session.execute(
                text(
                    """
                    UPDATE core.symbols
                    SET
                        key = NULL,
                        vector_id = NULL,
                        fingerprint = st.fingerprint,
                        updated_at = NOW()
                    FROM core_symbols_staging st
                    WHERE core.symbols.uuid = st.uuid
                    AND core.symbols.fingerprint != st.fingerprint;
                """
                )
            )

            # 3c. Insert brand new symbols
            await session.execute(
                text(
                    """
                    INSERT INTO core.symbols (id, uuid, symbol_path, module, qualname, kind, ast_signature, fingerprint, state, is_public, created_at, updated_at)
                    SELECT id, uuid, symbol_path, module, qualname, kind, ast_signature, fingerprint, state, is_public, NOW(), NOW()
                    FROM core_symbols_staging
                    WHERE uuid NOT IN (SELECT uuid FROM core.symbols);
                """
                )
            )

    return stats