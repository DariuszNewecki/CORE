# scripts/rehydrate_qdrant_from_db.py
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
from typing import Any, Dict, List, Optional

import requests
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# CORRECTED: This query now correctly JOINS the symbols and links table to get the vector_id.
SQL_PAGE = text(
    """
    SELECT
        s.id          AS symbol_id,
        s.symbol_path AS symbol_path,
        l.vector_id   AS vector_id
    FROM core.symbols AS s
    JOIN core.symbol_vector_links AS l ON s.id = l.symbol_id
    ORDER BY s.id
    LIMIT :limit OFFSET :offset
"""
)

# Try a few common vector column names in your vectors table
VECTOR_COL_CANDIDATES = ["vector", "values", "embedding", "data", "vec"]
DIM_COL_CANDIDATES = ["dim", "size", "length", "ndim"]


def make_vector_queries(vector_table: str) -> List[str]:
    stmts: List[str] = []
    for col in VECTOR_COL_CANDIDATES:
        for dim_col in DIM_COL_CANDIDATES:
            stmts.append(
                f"SELECT {col} AS v, {dim_col} AS d FROM {vector_table} WHERE id = :vid"
            )
        stmts.append(
            f"SELECT {col} AS v, NULL::INT AS d FROM {vector_table} WHERE id = :vid"
        )
    return stmts


def qdrant_upsert_points(
    qdrant_url: str, collection: str, points: List[Dict[str, Any]], *, timeout: int = 30
) -> None:
    if not points:
        return
    url = f"{qdrant_url.rstrip('/')}/collections/{collection}/points?wait=true"
    payload = {"points": points}
    r = requests.put(
        url,
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload),
        timeout=timeout,
    )
    if r.status_code >= 300:
        raise RuntimeError(f"Qdrant upsert failed [{r.status_code}]: {r.text}")


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rehydrate Qdrant from DB-stored vectors."
    )
    parser.add_argument(
        "--batch", type=int, default=500, help="Batch size for upserts (default: 500)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Do not write to Qdrant; just report."
    )
    parser.add_argument(
        "--vector-table",
        default="core.vectors",
        help="Table that stores vectors (default: core.vectors)",
    )
    args = parser.parse_args()

    db_url = os.getenv("DATABASE_URL")
    qdrant_url = os.getenv("QDRANT_URL")
    collection = os.getenv("QDRANT_COLLECTION_NAME", "core_capabilities")
    expected_dim_env = os.getenv("LOCAL_EMBEDDING_DIM")

    if not db_url or not qdrant_url:
        print("❌ DATABASE_URL or QDRANT_URL is not set.", file=sys.stderr)
        return 2
    if not db_url.startswith("postgresql+asyncpg://"):
        print(
            "❌ DATABASE_URL must be async (postgresql+asyncpg://...)", file=sys.stderr
        )
        return 2

    expected_dim = int(expected_dim_env) if (expected_dim_env or "").isdigit() else None

    engine = create_async_engine(db_url, pool_pre_ping=True)
    total = 0
    written = 0

    print(f"🔗 DB: {db_url.split('@')[-1]}")
    print(f"📦 Qdrant: {qdrant_url}  collection={collection}")
    if expected_dim:
        print(f"📐 Expected vector dim: {expected_dim}")

    try:
        async with engine.begin() as conn:
            res = await conn.execute(
                text("SELECT COUNT(*) FROM core.symbol_vector_links")
            )
            total = int(res.scalar_one())
            if total == 0:
                print("✅ Nothing to rehydrate (no symbols with vector links).")
                return 0

            print(f"🧮 Found {total} symbols with vectors. Starting rehydrate...")

            pages = math.ceil(total / args.batch)
            offset = 0
            vector_sqls = [text(s) for s in make_vector_queries(args.vector_table)]

            for page in range(pages):
                res = await conn.execute(
                    SQL_PAGE, {"limit": args.batch, "offset": offset}
                )
                rows = res.fetchall()
                offset += len(rows)

                out_points: List[Dict[str, Any]] = []

                # CORRECTED: The loop variables now match the corrected SQL query.
                for symbol_id, symbol_path, vector_id in rows:
                    # Always treat IDs as strings (handles UUIDs).
                    sid = str(symbol_id) if symbol_id is not None else None
                    vid = str(vector_id) if vector_id is not None else None
                    if not sid or not vid:
                        continue

                    vector: Optional[List[float]] = None
                    dim: Optional[int] = None

                    for stmt in vector_sqls:
                        try:
                            r = await conn.execute(stmt, {"vid": vid})
                            rec = r.fetchone()
                            if not rec:
                                continue
                            v, d = rec[0], (rec[1] if len(rec) > 1 else None)
                            if v is None:
                                continue

                            # Normalize to list[float]
                            try:
                                vec_list = list(v) if not isinstance(v, list) else v
                            except Exception:
                                continue

                            dim_val = int(d) if d is not None else len(vec_list)
                            if expected_dim and dim_val != expected_dim:
                                # dimension mismatch; skip this one
                                continue

                            vector = [float(x) for x in vec_list]
                            dim = dim_val
                            break
                        except Exception:
                            # Try next candidate
                            continue

                    if vector is None:
                        continue

                    # Unnamed vector collection: send a plain list
                    out_points.append(
                        {
                            "id": sid,  # Qdrant accepts string IDs
                            "vector": vector,
                            "payload": {
                                "symbol_path": symbol_path,
                                "vector_id": vid,
                                "dim": dim,
                            },
                        }
                    )

                    if len(out_points) >= args.batch:
                        if not args.dry_run:
                            qdrant_upsert_points(qdrant_url, collection, out_points)
                            written += len(out_points)
                        out_points.clear()

                # flush remaining
                if out_points:
                    if not args.dry_run:
                        qdrant_upsert_points(qdrant_url, collection, out_points)
                        written += len(out_points)

                print(
                    f"✅ Page {page+1}/{pages} processed. Total written so far: {written}"
                )

        if args.dry_run:
            print("🔎 Dry run complete. No writes were made.")
        else:
            print(f"🎉 Rehydrate finished. Wrote {written} vectors to Qdrant.")
        return 0

    except Exception as e:
        print(f"❌ Rehydrate failed: {e}", file=sys.stderr)
        return 1
    finally:
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
