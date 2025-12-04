# src/features/introspection/sync_service.py
"""Provides functionality for the sync_service module."""

from __future__ import annotations

import ast
import json
import uuid
from typing import Any

from services.database.session_manager import get_session
from shared.ast_utility import FunctionCallVisitor, calculate_structural_hash
from shared.config import settings
from shared.logger import getLogger
from sqlalchemy import text

logger = getLogger(__name__)


# ID: 2082848a-e1e3-48fa-aeb5-8d1b63f8d687
class SymbolVisitor(ast.NodeVisitor):
    """
    An AST visitor that discovers top-level public symbols, their immediate methods,
    and the symbols they call.
    """

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        self.symbols: list[dict[str, Any]] = []
        self.class_stack: list[str] = []

    # ID: 8ed3d0b6-d777-4927-b63b-5ed864045d39
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if not self.class_stack:
            self._process_symbol(node)
            self.class_stack.append(node.name)
            self.generic_visit(node)
            self.class_stack.pop()

    # ID: 7932462c-64cf-4987-979e-7d748e99ac73
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if len(self.class_stack) <= 1:
            self._process_symbol(node)

    # ID: de6530a7-200e-4932-9244-273e2a3e4308
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        if len(self.class_stack) <= 1:
            self._process_symbol(node)

    def _process_symbol(
        self, node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        """Extracts metadata for a single symbol, including its outbound calls."""
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

        call_visitor = FunctionCallVisitor()
        call_visitor.visit(node)

        # `calls` is serialized as JSON for storage in the DB
        calls = sorted(list(call_visitor.calls))

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
                "calls": json.dumps(calls),
            }
        )


# ID: ca6a48d2-acbe-4ebd-9e06-2a8d0428aa56
class SymbolScanner:
    """Scans the codebase to extract symbol information."""

    # ID: bab1a94f-8a2d-4c12-95fe-6822f19ba634
    def scan(self) -> list[dict[str, Any]]:
        """Scans all Python files in src/ and extracts symbols."""
        src_dir = settings.REPO_PATH / "src"
        all_symbols: list[dict[str, Any]] = []

        for file_path in src_dir.rglob("*.py"):
            try:
                content = file_path.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(file_path))
                rel_path_str = str(file_path.relative_to(settings.REPO_PATH))
                visitor = SymbolVisitor(rel_path_str)
                visitor.visit(tree)
                all_symbols.extend(visitor.symbols)
            except Exception as exc:  # noqa: BLE001
                logger.error("Error scanning %s: %s", file_path, exc)

        # Deduplicate by symbol_path (last one wins)
        unique_symbols = {s["symbol_path"]: s for s in all_symbols}
        return list(unique_symbols.values())


# ID: f6cedf76-ff2c-48bd-9847-3a65c07edb2e
async def run_sync_with_db() -> dict[str, int]:
    """
    Executes the full, database-centric sync logic using the "smart merge" strategy.
    This is the single source of truth for updating the symbols table from the codebase.
    """
    logger.info("Starting symbol sync with database")
    scanner = SymbolScanner()
    code_state = scanner.scan()
    stats: dict[str, int] = {
        "scanned": len(code_state),
        "inserted": 0,
        "updated": 0,
        "deleted": 0,
    }

    async with get_session() as session:
        async with session.begin():
            await session.execute(
                text(
                    """
                    CREATE TEMPORARY TABLE core_symbols_staging
                    (LIKE core.symbols INCLUDING DEFAULTS)
                    ON COMMIT DROP;
                    """
                )
            )

            if code_state:
                insert_stmt = text(
                    """
                    INSERT INTO core_symbols_staging (
                        id,
                        symbol_path,
                        module,
                        qualname,
                        kind,
                        ast_signature,
                        fingerprint,
                        state,
                        is_public,
                        calls
                    ) VALUES (
                        :id,
                        :symbol_path,
                        :module,
                        :qualname,
                        :kind,
                        :ast_signature,
                        :fingerprint,
                        :state,
                        :is_public,
                        :calls
                    )
                    """
                )
                await session.execute(insert_stmt, code_state)

            deleted_result = await session.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM core.symbols
                    WHERE symbol_path NOT IN (
                        SELECT symbol_path FROM core_symbols_staging
                    )
                    """
                )
            )
            stats["deleted"] = deleted_result.scalar_one()

            inserted_result = await session.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM core_symbols_staging
                    WHERE symbol_path NOT IN (
                        SELECT symbol_path FROM core.symbols
                    )
                    """
                )
            )
            stats["inserted"] = inserted_result.scalar_one()

            updated_result = await session.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM core.symbols s
                    JOIN core_symbols_staging st
                        ON s.symbol_path = st.symbol_path
                    WHERE
                        s.fingerprint != st.fingerprint
                        OR s.calls::text != st.calls::text
                    """
                )
            )
            stats["updated"] = updated_result.scalar_one()

            await session.execute(
                text(
                    """
                    DELETE FROM core.symbols
                    WHERE symbol_path NOT IN (
                        SELECT symbol_path FROM core_symbols_staging
                    )
                    """
                )
            )

            await session.execute(
                text(
                    """
                    UPDATE core.symbols
                    SET
                        fingerprint   = st.fingerprint,
                        calls         = st.calls,
                        last_modified = NOW(),
                        last_embedded = NULL,
                        updated_at    = NOW()
                    FROM core_symbols_staging st
                    WHERE core.symbols.symbol_path = st.symbol_path
                    AND (
                        core.symbols.fingerprint != st.fingerprint
                        OR core.symbols.calls::text != st.calls::text
                    );
                    """
                )
            )

            await session.execute(
                text(
                    """
                    INSERT INTO core.symbols (
                        id,
                        symbol_path,
                        module,
                        qualname,
                        kind,
                        ast_signature,
                        fingerprint,
                        state,
                        is_public,
                        calls,
                        created_at,
                        updated_at,
                        last_modified,
                        first_seen,
                        last_seen
                    )
                    SELECT
                        id,
                        symbol_path,
                        module,
                        qualname,
                        kind,
                        ast_signature,
                        fingerprint,
                        state,
                        is_public,
                        calls,
                        NOW(),
                        NOW(),
                        NOW(),
                        NOW(),
                        NOW()
                    FROM core_symbols_staging
                    ON CONFLICT (symbol_path) DO NOTHING;
                    """
                )
            )

    logger.info(
        "Sync complete. Scanned: %d, Inserted: %d, Updated: %d, Deleted: %d",
        stats["scanned"],
        stats["inserted"],
        stats["updated"],
        stats["deleted"],
    )
    return stats
