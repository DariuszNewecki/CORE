# scripts/find_unvectorized_symbols.py
"""
Unvectorized Symbol Inspector (diagnostic-only)

Lists symbols in `core.symbols` that do NOT have a vector link yet.
This version is updated for the link-table model:

  - core.symbols(id UUID, symbol_path TEXT, module TEXT, fingerprint TEXT, ...)
  - core.symbol_vector_links(symbol_id UUID, vector_id TEXT, ...)

Usage examples:
  poetry run python3 scripts/find_unvectorized_symbols.py
  poetry run python3 scripts/find_unvectorized_symbols.py --limit 50
  poetry run python3 scripts/find_unvectorized_symbols.py --count
  poetry run python3 scripts/find_unvectorized_symbols.py --csv > unvectorized.csv

Notes:
- Reads the database URL from $DATABASE_URL (async URL: postgresql+asyncpg://…)
- Diagnostic-only; not part of CORE’s runtime.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import os
import sys
from typing import Tuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

SQL_SELECT = text(
    """
    SELECT
        s.symbol_path,
        s.module AS file_path,
        s.fingerprint AS structural_hash
    FROM core.symbols AS s
    WHERE NOT EXISTS (
        SELECT 1
        FROM core.symbol_vector_links AS l
        WHERE l.symbol_id = s.id
    )
    ORDER BY s.module, s.symbol_path
    LIMIT :limit
    """
)

SQL_COUNT = text(
    """
    SELECT COUNT(*) AS cnt
    FROM core.symbols AS s
    WHERE NOT EXISTS (
        SELECT 1
        FROM core.symbol_vector_links AS l
        WHERE l.symbol_id = s.id
    )
    """
)


def _fmt_row(row: Tuple[str, str, str], widths: Tuple[int, int, int]) -> str:
    s, f, h = row
    w1, w2, w3 = widths
    s = (s[: w1 - 1] + "…") if len(s) > w1 else s
    f = (f[: w2 - 1] + "…") if len(f) > w2 else f
    h = (h[: w3 - 1] + "…") if len(h) > w3 else h
    return f"{s:<{w1}}  {f:<{w2}}  {h:<{w3}}"


async def _run(limit: int, want_count: bool, as_csv: bool) -> int:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("❌ DATABASE_URL is not set.", file=sys.stderr)
        return 2
    engine = create_async_engine(db_url, future=True)

    try:
        async with engine.begin() as conn:
            if want_count:
                res = await conn.execute(SQL_COUNT)
                count = int(res.scalar() or 0)
                print(count)
                return 0

            res = await conn.execute(SQL_SELECT, {"limit": limit})
            rows = [(r[0], r[1], r[2]) for r in res]

        if as_csv:
            writer = csv.writer(sys.stdout)
            writer.writerow(["symbol_path", "file_path", "structural_hash"])
            writer.writerows(rows)
            return 0

        # pretty print
        widths = (68, 56, 16)
        header = _fmt_row(("symbol_path", "file_path", "structural_hash"), widths)
        print(header)
        print("-" * len(header))
        for row in rows:
            print(_fmt_row(row, widths))

        return 0

    except Exception as e:
        print(f"❌ Query failed: {e}", file=sys.stderr)
        return 1

    finally:
        await engine.dispose()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=100, help="Rows to list")
    ap.add_argument("--count", action="store_true", help="Print only the count")
    ap.add_argument("--csv", action="store_true", help="Emit CSV to stdout")
    args = ap.parse_args()

    raise SystemExit(asyncio.run(_run(args.limit, args.count, args.csv)))


if __name__ == "__main__":
    main()
