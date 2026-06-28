from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Importing via the package __init__ triggers all sub-module imports, registering
# every ORM-mapped table with Base.metadata — including classes not re-exported in
# __all__ (FixRun, DecoratorRegistry, RefusalRecord, etc.).
import shared.infrastructure.database.models as _models_pkg  # noqa: F401
from shared.infrastructure.database.models import Base


pytestmark = [pytest.mark.integration]

_FIX_CMD = "ssh <db-server> 'bash /opt/dev/CORE/infra/scripts/reset_test_db.sh'"


async def test_core_test_schema_matches_orm(db_session: AsyncSession) -> None:
    """
    Detects when core_test has drifted from the ORM schema.

    Resolves the failure mode from #656: missing columns surface as opaque
    'column does not exist' errors mid-suite rather than a clear diagnosis.
    Checks every ORM-declared table in schema 'core'; extra DB tables not
    mapped by the ORM are ignored.
    """
    expected: dict[str, set[str]] = {
        table.name: {col.name for col in table.columns}
        for table in Base.metadata.tables.values()
        if table.schema == "core"
    }

    rows = (
        await db_session.execute(
            text(
                "SELECT table_name, column_name"
                " FROM information_schema.columns"
                " WHERE table_schema = 'core'"
            )
        )
    ).fetchall()

    actual: dict[str, set[str]] = {}
    for table_name, column_name in rows:
        actual.setdefault(table_name, set()).add(column_name)

    missing_tables = sorted(expected.keys() - actual.keys())
    missing_cols: dict[str, list[str]] = {
        tbl: sorted(expected[tbl] - actual[tbl])
        for tbl in sorted(expected.keys() & actual.keys())
        if expected[tbl] - actual[tbl]
    }

    if not missing_tables and not missing_cols:
        return

    lines = [
        "core_test schema has drifted from the ORM. Fix with:",
        f"  {_FIX_CMD}",
        "",
    ]
    if missing_tables:
        lines.append(
            f"Tables missing entirely ({len(missing_tables)}): {missing_tables}"
        )
    for tbl, cols in missing_cols.items():
        lines.append(f"  core.{tbl}: missing columns {cols}")

    pytest.fail("\n".join(lines))
