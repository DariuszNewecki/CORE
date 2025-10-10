# scripts/find_unvectorized_symbols.py
"""
Unvectorized Symbol Inspector (diagnostic-only)

Lists symbols in `core.symbols` that do NOT have a vector assigned yet
(i.e., rows where `vector_id IS NULL`), using your current database schema.

Schema columns used:
- symbol_path (TEXT)
- module       (TEXT)  -> shown as file_path
- fingerprint  (TEXT)  -> shown as structural_hash

Usage examples:
  poetry run python3 scripts/find_unvectorized_symbols.py
  poetry run python3 scripts/find_unvectorized_symbols.py --limit 50
  poetry run python3 scripts/find_unvectorized_symbols.py --count
  poetry run python3 scripts/find_unvectorized_symbols.py --csv > unvectorized.csv

Notes:
- Reads the database URL from $DATABASE_URL (must be async, e.g. postgresql+asyncpg://…)
- This script is *diagnostic only* and not part of CORE’s runtime.
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
        symbol_path,
        module AS file_path,
        fingerprint AS structural_hash
    FROM core.symbols
    WHERE vector_id IS NULL
    ORDER BY module, symbol_path
    LIMIT :limit
    """
)

SQL_COUNT = text(
    """
    SELECT COUNT(*) AS cnt
    FROM core.symbols
    WHERE vector_id IS NULL
    """
)


def _fmt_row(row: Tuple[str, str, str], widths: Tuple[int, int, int]) -> str:
    s, f, h = row
    w1, w2, w3 = widths
    s = (s[: w1 - 1] + "…") if len(s) > w1 else s
    f = (f[: w2 - 1] + "…") if len(f) > w2 else f
    h = (h[: w3 - 1] + "…") if len(h) > w3 else h
    return f"{s:<{w1}}  {f:<{w2}}  {h:<{w3}}"


async def _run_async(limit: int, as_csv: bool, do_count: bool) -> int:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ DATABASE_URL is not set.", file=sys.stderr)
        return 2
    if not db_url.startswith("postgresql+asyncpg://"):
        print(
            "❌ DATABASE_URL must be an async URL (e.g. postgresql+asyncpg://…)",
            file=sys.stderr,
        )
        return 2

    engine = create_async_engine(db_url, pool_pre_ping=True)
    try:
        async with engine.begin() as conn:
            # Optional count-only mode
            if do_count:
                res = await conn.execute(SQL_COUNT)
                count = res.scalar_one()
                print(count)
                return 0

            res = await conn.execute(SQL_SELECT, {"limit": limit})
            rows = [(r[0] or "", r[1] or "", r[2] or "") for r in res.fetchall()]

            if as_csv:
                writer = csv.writer(sys.stdout)
                writer.writerow(["symbol_path", "file_path", "structural_hash"])
                writer.writerows(rows)
                return 0

            if not rows:
                print("--- Unvectorized Symbol Inspector ---")
                print("✅ No unvectorized symbols found. (vector_id IS NULL = 0)")
                return 0

            # Pretty table
            print("--- Unvectorized Symbol Inspector ---")
            print(f"✅ Connected to DB: {db_url.split('@')[-1]}")
            print(f"📦 Rows: {len(rows)} (showing up to {limit})\n")

            # Choose friendly widths
            w_symbol = 60
            w_file = 48
            w_hash = 40
            widths = (w_symbol, w_file, w_hash)

            header = _fmt_row(("symbol_path", "file_path", "structural_hash"), widths)
            sep = "-" * len(header)
            print(header)
            print(sep)
            for row in rows:
                print(_fmt_row(row, widths))

            print("\nℹ️ Tip: Use --csv to export, or --count to just get the number.")
            return 0
    except Exception as exc:  # pragma: no cover (diagnostic)
        print("❌ Error while querying unvectorized symbols:\n", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="List symbols without vectors (vector_id IS NULL) from core.symbols."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Max rows to display (default: 200)",
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        help="Output CSV (columns: symbol_path,file_path,structural_hash)",
    )
    parser.add_argument(
        "--count",
        action="store_true",
        help="Print only the count of unvectorized symbols and exit.",
    )
    args = parser.parse_args()

    return asyncio.run(_run_async(args.limit, args.csv, args.count))


if __name__ == "__main__":
    raise SystemExit(main())
