# src/features/introspection/sync_service.py
from __future__ import annotations

import ast
import uuid
from typing import Any, Dict, List

from rich.console import Console
from services.database.session_manager import get_session
from shared.ast_utility import calculate_structural_hash
from shared.config import settings
from sqlalchemy import text

console = Console()


# ID: 2fc08ba1-31ee-42cd-84cf-f68f81013acf
class SymbolVisitor(ast.NodeVisitor):
    """An AST visitor that discovers symbols and their hierarchical paths."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.symbols: List[Dict[str, Any]] = []
        self.class_stack: List[str] = []

    # ID: 05ab6a68-f66e-4571-9372-47c17ad4b72f
    def visit_ClassDef(self, node: ast.ClassDef):
        """Process a class definition and its children (methods)."""
        if not self.class_stack:
            self._process_symbol(node)

        self.class_stack.append(node.name)
        self.generic_visit(node)
        self.class_stack.pop()

    # ID: f69596a9-b1b5-4292-ab20-ef62c063b867
    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Process a function or method definition."""
        if not self.class_stack:
            self._process_symbol(node)

    # ID: 4d6bf114-b4cd-466a-83ec-584202c69fcd
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

        symbol_path = f"{self.file_path}::{node.name}"

        module_name = (
            self.file_path.replace("src/", "").replace(".py", "").replace("/", ".")
        )
        kind_map = {
            "ClassDef": "class",
            "FunctionDef": "function",
            "AsyncFunctionDef": "function",
        }

        self.symbols.append(
            {
                "id": uuid.uuid5(uuid.NAMESPACE_DNS, symbol_path),
                "symbol_path": symbol_path,
                "module": module_name,
                "qualname": node.name,
                "kind": kind_map.get(type(node).__name__, "function"),
                "ast_signature": "TBD",
                "fingerprint": calculate_structural_hash(node),
                "state": "discovered",
                "is_public": True,
            }
        )


# ID: da739a48-f3c2-4c27-b870-51ddb224bc32
class SymbolScanner:
    """Scans the codebase to extract symbol information using a hierarchical visitor."""

    # ID: 1c60168e-3d83-4c72-b4be-390554f51b18
    def scan(self) -> List[Dict[str, Any]]:
        """Scans all Python files in src/ and extracts ID'd symbols."""
        src_dir = settings.REPO_PATH / "src"
        all_symbols = []

        for file_path in src_dir.rglob("*.py"):
            try:
                content = file_path.read_text("utf-8")
                tree = ast.parse(content, filename=str(file_path))

                rel_path_str = str(file_path.relative_to(settings.REPO_PATH))
                visitor = SymbolVisitor(rel_path_str)
                visitor.visit(tree)
                all_symbols.extend(visitor.symbols)
            except Exception as e:
                console.print(f"[bold red]Error scanning {file_path}: {e}[/bold red]")

        unique_symbols = {s["symbol_path"]: s for s in all_symbols}
        return list(unique_symbols.values())


# ID: 5ca33e91-947b-435c-9756-c74a22f37a2b
async def run_sync_with_db() -> Dict[str, int]:
    """
    Executes the full, database-centric sync logic using the "smart merge" strategy.
    This is the single source of truth for updating the symbols table from the codebase.
    """
    scanner = SymbolScanner()
    code_state = scanner.scan()
    stats = {"scanned": len(code_state), "inserted": 0, "updated": 0, "deleted": 0}

    async with get_session() as session:
        async with session.begin():
            # 1. Create a temporary table to hold the current state from the code scan
            await session.execute(
                text(
                    "CREATE TEMPORARY TABLE core_symbols_staging (LIKE core.symbols INCLUDING DEFAULTS) ON COMMIT DROP;"
                )
            )

            # 2. Populate the temporary table with the symbols found in the code
            if code_state:
                await session.execute(
                    text(
                        """
                        INSERT INTO core_symbols_staging (id, symbol_path, module, qualname, kind, ast_signature, fingerprint, state, is_public)
                        VALUES (:id, :symbol_path, :module, :qualname, :kind, :ast_signature, :fingerprint, :state, :is_public)
                    """
                    ),
                    code_state,
                )

            # 3. Calculate stats before making changes
            deleted_result = await session.execute(
                text(
                    "SELECT COUNT(*) FROM core.symbols WHERE symbol_path NOT IN (SELECT symbol_path FROM core_symbols_staging)"
                )
            )
            stats["deleted"] = deleted_result.scalar_one()

            inserted_result = await session.execute(
                text(
                    "SELECT COUNT(*) FROM core_symbols_staging WHERE symbol_path NOT IN (SELECT symbol_path FROM core.symbols)"
                )
            )
            stats["inserted"] = inserted_result.scalar_one()

            updated_result = await session.execute(
                text(
                    """
                    SELECT COUNT(*) FROM core.symbols s
                    JOIN core_symbols_staging st ON s.symbol_path = st.symbol_path
                    WHERE s.fingerprint != st.fingerprint
                """
                )
            )
            stats["updated"] = updated_result.scalar_one()

            # 4. Delete symbols from the main table that no longer exist in the code
            await session.execute(
                text(
                    "DELETE FROM core.symbols WHERE symbol_path NOT IN (SELECT symbol_path FROM core_symbols_staging)"
                )
            )

            # 5. Update symbols that have changed (and nullify their embedding status)
            await session.execute(
                text(
                    """
                    UPDATE core.symbols
                    SET
                        fingerprint = st.fingerprint,
                        last_modified = NOW(),
                        last_embedded = NULL, -- This is the key change to trigger re-vectorization
                        updated_at = NOW()
                    FROM core_symbols_staging st
                    WHERE core.symbols.symbol_path = st.symbol_path
                    AND core.symbols.fingerprint != st.fingerprint;
                """
                )
            )

            # 6. Insert brand new symbols
            await session.execute(
                text(
                    """
                    INSERT INTO core.symbols (id, symbol_path, module, qualname, kind, ast_signature, fingerprint, state, is_public, created_at, updated_at, last_modified, first_seen, last_seen)
                    SELECT id, symbol_path, module, qualname, kind, ast_signature, fingerprint, state, is_public, NOW(), NOW(), NOW(), NOW(), NOW()
                    FROM core_symbols_staging
                    ON CONFLICT (symbol_path) DO NOTHING;
                """
                )
            )

    return stats
