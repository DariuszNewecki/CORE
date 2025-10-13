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
    """
    An AST visitor that discovers top-level public symbols and their immediate methods,
    while correctly ignoring nested functions and classes as implementation details.
    """

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.symbols: List[Dict[str, Any]] = []
        self.class_stack: List[str] = []

    # ID: 0b1d3e2c-5f6a-7b8c-9d0e-1f2a3b4c5d6e
    def visit_ClassDef(self, node: ast.ClassDef):
        # Only process top-level classes. Nested classes are implementation details.
        if not self.class_stack:
            self._process_symbol(node)
            self.class_stack.append(node.name)
            # Visit children to find methods of this class.
            self.generic_visit(node)
            self.class_stack.pop()

    # ID: 2d3e4f5a-6b7c-8d9e-0f1a2b3c4d5e
    # ID: 4a14b3db-a724-487f-bcb4-fa020583ae73
    def visit_FunctionDef(self, node: ast.FunctionDef):
        # Process the function only if it's top-level or a direct method of a class.
        if len(self.class_stack) <= 1:
            self._process_symbol(node)
        # Do NOT call generic_visit here to prevent descending into nested helper functions.

    # ID: 4e5f6a7b-8c9d-0e1f-2a3b4c5d6e7f
    # ID: 6e4cfc45-18a3-4d82-b554-eb4615eefea8
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        # Process the async function only if it's top-level or a direct method of a class.
        if len(self.class_stack) <= 1:
            self._process_symbol(node)
        # Do NOT call generic_visit here to prevent descending into nested helper functions.

    def _process_symbol(
        self, node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
    ):
        """Extracts metadata for a single symbol, respecting its context."""
        is_public = not node.name.startswith("_")
        is_dunder = node.name.startswith("__") and node.name.endswith("__")
        if not (is_public and not is_dunder):
            return

        path_components = self.class_stack + [node.name]
        symbol_path = f"{self.file_path}::{'.'.join(path_components)}"
        qualname = ".".join(path_components)

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
                "qualname": qualname,
                "kind": kind_map.get(type(node).__name__, "function"),
                "ast_signature": "TBD",
                "fingerprint": calculate_structural_hash(node),
                "state": "discovered",
                "is_public": True,
            }
        )


# ID: da739a48-f3c2-4c27-b870-51ddb224bc32
class SymbolScanner:
    """Scans the codebase to extract symbol information."""

    # ID: 1c60168e-3d83-4c72-b4be-390554f51b18
    def scan(self) -> List[Dict[str, Any]]:
        """Scans all Python files in src/ and extracts symbols."""
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
            # 1. Create a temporary table
            await session.execute(
                text(
                    "CREATE TEMPORARY TABLE core_symbols_staging (LIKE core.symbols INCLUDING DEFAULTS) ON COMMIT DROP;"
                )
            )

            # 2. Populate the temporary table
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

            # 3. Calculate stats
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

            # 4. Delete obsolete symbols
            await session.execute(
                text(
                    "DELETE FROM core.symbols WHERE symbol_path NOT IN (SELECT symbol_path FROM core_symbols_staging)"
                )
            )

            # 5. Update changed symbols
            await session.execute(
                text(
                    """
                    UPDATE core.symbols
                    SET
                        fingerprint = st.fingerprint,
                        last_modified = NOW(),
                        last_embedded = NULL,
                        updated_at = NOW()
                    FROM core_symbols_staging st
                    WHERE core.symbols.symbol_path = st.symbol_path
                    AND core.symbols.fingerprint != st.fingerprint;
                """
                )
            )

            # 6. Insert new symbols
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
