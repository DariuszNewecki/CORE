# src/features/maintenance/scripts/context_export.py

"""
Export a complete, compact operational snapshot of CORE:
- Mind (.intent)  -> zipped + manifest
- Body (src)      -> zipped + symbol_index.json
- State (DB)      -> schema-only SQL + small samples (optional)
- Vectors (Qdrant)-> collection schema + small payload samples (optional)
- Runtime         -> runtime_context.yaml
- Top manifest    -> core_context_manifest.yaml (hashes, versions, pointers)

✅ CORE UX principle:
By default, this script reads its configuration from the live CORE environment
(no arguments needed) and writes to ./_exports/core_export_<timestamp>/.

Quick run:
  python3 scripts/export_core_context.py

Optional overrides:
  python3 scripts/export_core_context.py --output-dir /opt/exports
  python3 scripts/export_core_context.py --db-url postgresql://user:pass@host:5432/core
  python3 scripts/export_core_context.py --qdrant-url http://127.0.0.1:6333 --qdrant-collection core_capabilities

Environment fallbacks (used if args not passed):
  DATABASE_URL, QDRANT_URL, QDRANT_COLLECTION_NAME

Outputs (under output-dir/TIMESTAMP/):
  - .intent.tar.gz
  - intent_manifest.yaml
  - src.tar.gz
  - symbol_index.json
  - db_schema.sql              (if DB available)
  - db_samples.json            (if DB available)
  - qdrant_schema.yaml         (if Qdrant available)
  - qdrant_samples.json        (if Qdrant available)
  - runtime_context.yaml
  - core_context_manifest.yaml (top-level manifest & checksums)
"""

from __future__ import annotations

import argparse
import ast
import dataclasses
import datetime as dt
import getpass
import hashlib
import json
import os
import re
import subprocess
import sys
import tarfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

# ---------------------------
# Helpers
# ---------------------------


# ID: 5db35538-9a12-43ef-9a09-3d359df0d2d0
def now_utc_iso() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


# ID: e40eea40-fdc4-42c1-8022-b6306c23efab
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


# ID: 3c91eb52-a5e1-42b4-86e7-19dab7bdd556
def redacted_url(url: str) -> str:
    if not url or "@" not in url:
        return url
    # Redact credentials: scheme://user:pass@host -> scheme://***@host
    return re.sub(r"//([^/@:]+)(:[^/@]+)?@", "//***@", url)


# ID: 221808d8-f133-4bb2-92f8-4ce9c8a7ac97
def run_cmd(
    args: list[str], cwd: Path | None = None, timeout: int = 60
) -> tuple[int, str, str]:
    proc = subprocess.Popen(
        args,
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
    return proc.returncode, out, err


# ID: e8d3a370-90b9-4526-9196-7b30c71bb69e
def tar_dir(
    src_dir: Path, out_path: Path, exclude_globs: list[str] | None = None
) -> None:
    """
    Create a .tar.gz archive (stdlib-only; portable & compact).
    """
    mode = "w:gz"
    with tarfile.open(out_path, mode) as tar:
        for root, _, files in os.walk(src_dir):
            root_p = Path(root)
            for name in files:
                p = root_p / name
                rel = p.relative_to(src_dir)
                if exclude_globs and any(rel.match(g) for g in exclude_globs):
                    continue
                tar.add(p, arcname=str(rel))


# ID: f56e2728-a4bd-4392-81e4-84474efb7548
def safe_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ID: 582df9bd-10a3-4120-9a00-f7e5592eabd3
def safe_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------
# Git info (optional)
# ---------------------------


# ID: 20a1dbf6-bc0a-47aa-a4f3-9944ad7f3efc
def git_info(repo_root: Path) -> dict[str, Any]:
    info = {}
    code, out, _ = run_cmd(["git", "rev-parse", "HEAD"], cwd=repo_root)
    if code == 0:
        info["commit"] = out.strip()
    code, out, _ = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root)
    if code == 0:
        info["branch"] = out.strip()
    code, out, _ = run_cmd(["git", "status", "--porcelain"], cwd=repo_root)
    if code == 0:
        info["dirty"] = bool(out.strip())
    return info


# ---------------------------
# AST scan for symbol index
# ---------------------------


@dataclasses.dataclass
# ID: d751eeec-bb80-4ab7-bac3-53d4801520ca
class Symbol:
    module: str
    kind: str  # "class" | "function"
    name: str
    lineno: int
    signature: str
    doc: str | None


# ID: a3a8a571-4b76-426c-9f36-90fe4eb6ad90
def build_signature_from_ast(node: ast.AST) -> str:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return ""
    args = []
    for a in node.args.args:
        args.append(a.arg)
    if node.args.vararg:
        args.append("*" + node.args.vararg.arg)
    for a in node.args.kwonlyargs:
        args.append(a.arg + "=")
    if node.args.kwarg:
        args.append("**" + node.args.kwarg.arg)
    return f"({', '.join(args)})"


# ID: 8b3f5ac1-958f-43a6-9043-c558d18de672
def scan_python_symbols(src_root: Path) -> dict[str, Any]:
    symbols: list[Symbol] = []
    imports: list[dict[str, Any]] = []
    for py in src_root.rglob("*.py"):
        rel_mod = str(py.relative_to(src_root)).replace(os.sep, ".")[:-3]
        try:
            txt = py.read_text(encoding="utf-8")
        except Exception:
            continue
        try:
            tree = ast.parse(txt)
        except Exception:
            continue

        # Imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append({"from": rel_mod, "to": alias.name})
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append({"from": rel_mod, "to": node.module})

        # Top-level symbols
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                doc = ast.get_docstring(node)
                symbols.append(
                    Symbol(
                        rel_mod,
                        "class",
                        node.name,
                        getattr(node, "lineno", 0),
                        "(…)",
                        doc,
                    )
                )
                # public methods
                for ch in node.body:
                    if isinstance(
                        ch, (ast.FunctionDef, ast.AsyncFunctionDef)
                    ) and not ch.name.startswith("_"):
                        doc_m = ast.get_docstring(ch)
                        sig = build_signature_from_ast(ch)
                        symbols.append(
                            Symbol(
                                f"{rel_mod}.{node.name}",
                                "function",
                                ch.name,
                                getattr(ch, "lineno", 0),
                                sig,
                                doc_m,
                            )
                        )
            elif isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef)
            ) and not node.name.startswith("_"):
                doc = ast.get_docstring(node)
                sig = build_signature_from_ast(node)
                symbols.append(
                    Symbol(
                        rel_mod,
                        "function",
                        node.name,
                        getattr(node, "lineno", 0),
                        sig,
                        doc,
                    )
                )

    modules: dict[str, dict[str, Any]] = {}
    for s in symbols:
        modules.setdefault(s.module, {"classes": {}, "functions": []})
        if s.kind == "class":
            modules[s.module]["classes"].setdefault(
                s.name, {"doc": s.doc, "methods": []}
            )
        else:
            modules[s.module]["functions"].append(
                {
                    "name": s.name,
                    "lineno": s.lineno,
                    "signature": s.signature,
                    "doc": s.doc,
                }
            )

    idx = {
        "generated_at": now_utc_iso(),
        "root": str(src_root),
        "modules": modules,
        "imports": imports,
        "note": "Public functions/classes only; docstrings captured at definition sites.",
    }
    return idx


# ---------------------------
# DB: schema + samples (best-effort)
# ---------------------------


# ID: 00e570fa-d48f-4bcc-800b-643cefb6ed80
def export_db_schema(db_url: str, out_sql: Path) -> str | None:
    code, _, _ = run_cmd(["pg_dump", "--version"], timeout=10)
    if code == 0:
        code, out, err = run_cmd(
            ["pg_dump", "--schema-only", "--no-owner", "--no-privileges", db_url]
        )
        if code == 0:
            safe_write_text(out_sql, out)
            return "pg_dump"
        else:
            safe_write_text(out_sql, f"-- pg_dump failed:\n{err}")
            return None
    safe_write_text(
        out_sql, "-- pg_dump not available; provide schema via admin tools.\n"
    )
    return None


# ID: d5a14bbb-c044-4bd2-bf3e-4c39d6179101
def try_db_samples(db_url: str, out_json: Path, max_rows: int = 5) -> None:
    # Try psycopg
    try:
        import psycopg  # type: ignore

        with psycopg.connect(db_url) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
                ORDER BY 1,2
                LIMIT 25;
            """
            )
            tables = cur.fetchall()
            data = {"samples": {}, "limit": max_rows}
            for schema, table in tables:
                q = f'SELECT * FROM "{schema}"."{table}" LIMIT {max_rows};'
                try:
                    cur.execute(q)
                    rows = cur.fetchall()
                    cols = [d[0] for d in cur.description] if cur.description else []
                    data["samples"][f"{schema}.{table}"] = {
                        "columns": cols,
                        "rows": rows,
                    }
                except Exception as e:
                    data["samples"][f"{schema}.{table}"] = {"error": str(e)}
            safe_write_json(out_json, data)
            return
    except Exception:
        pass

    # Try psql
    code, out, _ = run_cmd(["psql", db_url, "-c", "\\dt"], timeout=15)
    if code == 0:
        safe_write_json(
            out_json,
            {"psql_dt": out, "note": "Install psycopg for structured samples."},
        )
        return

    safe_write_json(out_json, {"note": "No psycopg/psql available; skip DB samples."})


# ---------------------------
# Qdrant: schema + samples (stdlib HTTP)
# ---------------------------


# ID: 4ef11fbe-602d-4bc9-ba16-f0c1d05fc45a
def http_get_json(url: str, timeout: int = 10) -> dict[str, Any] | None:
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        TimeoutError,
        json.JSONDecodeError,
    ):
        return None


# ID: 5040d90f-77d6-4cfa-b7c9-03db223ca4ed
def export_qdrant(
    qdrant_url: str,
    collection: str,
    schema_out: Path,
    samples_out: Path,
    sample_limit: int = 3,
) -> None:
    base = qdrant_url.rstrip("/")
    col = urllib.parse.quote(collection)
    info = http_get_json(f"{base}/collections/{col}")
    if info is None:
        safe_write_text(schema_out, "# Qdrant not reachable or collection missing.\n")
        safe_write_json(samples_out, {"note": "Qdrant not reachable."})
        return

    details = info.get("result", {})
    schema_lines = [
        "collection:",
        f"  name: {collection}",
        f"  vectors: {details.get('vectors')}",
        f"  hnsw_config: {details.get('hnsw_config')}",
        f"  quantization_config: {details.get('quantization_config')}",
        f"  on_disk_payload: {details.get('on_disk_payload')}",
        f"  replication_factor: {details.get('replication_factor')}",
        f"  write_consistency_factor: {details.get('write_consistency_factor')}",
        f"  shard_number: {details.get('shard_number')}",
    ]
    safe_write_text(schema_out, "\n".join(schema_lines) + "\n")

    # Sample points via scroll
    body = json.dumps({"limit": sample_limit}).encode("utf-8")
    try:
        req = urllib.request.Request(
            f"{base}/collections/{col}/points/scroll",
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            safe_write_json(samples_out, result)
    except Exception:
        safe_write_json(
            samples_out,
            {"note": "Could not fetch sample points (scroll).", "limit": sample_limit},
        )


# ---------------------------
# Minimal YAML emitter (avoid external deps)
# ---------------------------


# ID: c3dc5c1f-9a52-49f2-92d0-09af54615570
def to_yaml(data: Any, indent: int = 0) -> str:
    sp = "  " * indent
    if data is None:
        return "null"
    if isinstance(data, bool):
        return "true" if data else "false"
    if isinstance(data, (int, float)):
        return str(data)
    if isinstance(data, str):
        if re.search(r"[:#\-\n']", data):
            return "'" + data.replace("'", "''") + "'"
        return data
    if isinstance(data, list):
        lines = []
        for item in data:
            v = to_yaml(item, indent + 1)
            lines.append(
                f"{sp}- {v if '\n' not in v else '\n' + '  ' * (indent+1) + v}"
            )
        return "\n".join(lines) if lines else "[]"
    if isinstance(data, dict):
        lines = []
        for k, v in data.items():
            val = to_yaml(v, indent + 1)
            if "\n" in val:
                lines.append(f"{sp}{k}:\n{ '  ' * (indent+1)}{val}")
            else:
                lines.append(f"{sp}{k}: {val}")
        return "\n".join(lines) if lines else "{}"
    return to_yaml(str(data), indent)


# ---------------------------
# Runtime context builder
# ---------------------------


# ID: ecc2831b-86e4-4388-960c-7b01d5b09483
def build_runtime_context(
    repo_root: Path,
    db_url: str | None,
    qdrant_url: str | None,
    qdrant_collection: str | None,
) -> dict[str, Any]:
    git = git_info(repo_root)
    ctx = {
        "generated_at": now_utc_iso(),
        "user": getpass.getuser(),
        "repo_root": str(repo_root),
        "git": git,
        "database_url": redacted_url(db_url) if db_url else None,
        "qdrant_url": qdrant_url,
        "qdrant_collection": qdrant_collection,
        "autonomy_level": "A1",  # informational
    }
    return ctx


# ---------------------------
# Main
# ---------------------------


# ID: 3e5f4876-b6a2-438f-a256-51ff4adb4e64
def main():
    p = argparse.ArgumentParser(
        description="Export CORE operational context (Mind/Body/State/Vectors/Runtime)."
    )
    p.add_argument("--repo-root", default=".", help="Repository root (default: .)")
    p.add_argument(
        "--intent-dir", default=".intent", help="Path to .intent/ relative to repo root"
    )
    p.add_argument(
        "--src-dir", default="src", help="Path to src/ relative to repo root"
    )
    # ✅ Make output-dir optional with sensible default
    p.add_argument(
        "--output-dir",
        default="./scripts/exports",
        help="Directory to write export bundle into (default: ./_exports)",
    )
    p.add_argument(
        "--db-url",
        default=os.environ.get("DATABASE_URL"),
        help="PostgreSQL URL (or env DATABASE_URL)",
    )
    p.add_argument(
        "--qdrant-url",
        default=os.environ.get("QDRANT_URL"),
        help="Qdrant base URL (or env QDRANT_URL)",
    )
    p.add_argument(
        "--qdrant-collection",
        default=os.environ.get("QDRANT_COLLECTION_NAME"),
        help="Qdrant collection (or env QDRANT_COLLECTION_NAME)",
    )
    p.add_argument(
        "--db-sample-rows",
        type=int,
        default=5,
        help="Max sample rows per table for DB samples",
    )
    args = p.parse_args()

    repo_root = Path(args.repo_root).resolve()
    intent_dir = (repo_root / args.intent_dir).resolve()
    src_dir = (repo_root / args.src_dir).resolve()

    if not intent_dir.exists():
        print(f"[WARN] .intent directory not found at {intent_dir}", file=sys.stderr)
    if not src_dir.exists():
        print(f"[WARN] src directory not found at {src_dir}", file=sys.stderr)

    ts = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    # ✅ default output root if user didn't override
    base_out = Path(args.output_dir).expanduser().resolve()
    out_root = base_out / f"core_export_{ts}"
    out_root.mkdir(parents=True, exist_ok=True)

    # 1) Mind (.intent)
    intent_tar = out_root / ".intent.tar.gz"
    if intent_dir.exists():
        tar_dir(
            intent_dir,
            intent_tar,
            exclude_globs=["**/__pycache__/**", "**/*.pyc", "**/*.log", "**/.DS_Store"],
        )
    intent_manifest = {
        "generated_at": now_utc_iso(),
        "root": str(intent_dir),
        "note": "Full .intent tree archived; per-policy dependencies can be added later.",
    }
    safe_write_text(out_root / "intent_manifest.yaml", to_yaml(intent_manifest))

    # 2) Body (src) + symbol index
    src_tar = out_root / "src.tar.gz"
    if src_dir.exists():
        tar_dir(
            src_dir,
            src_tar,
            exclude_globs=["**/__pycache__/**", "**/*.pyc", "**/*.log", "**/.DS_Store"],
        )
        symbol_index = scan_python_symbols(src_dir)
        safe_write_json(out_root / "symbol_index.json", symbol_index)
    else:
        safe_write_json(
            out_root / "symbol_index.json", {"note": "src directory missing"}
        )

    # 3) DB schema + samples (best-effort)
    db_schema_path = out_root / "db_schema.sql"
    db_samples_path = out_root / "db_samples.json"
    if args.db_url:
        export_db_schema(args.db_url, db_schema_path)
        try_db_samples(args.db_url, db_samples_path, max_rows=args.db_sample_rows)
    else:
        safe_write_text(db_schema_path, "-- DATABASE_URL not provided.\n")
        safe_write_json(db_samples_path, {"note": "DATABASE_URL not provided"})

    # 4) Qdrant
    qdrant_schema = out_root / "qdrant_schema.yaml"
    qdrant_samples = out_root / "qdrant_samples.json"
    if args.qdrant_url and args.qdrant_collection:
        export_qdrant(
            args.qdrant_url, args.qdrant_collection, qdrant_schema, qdrant_samples
        )
    else:
        safe_write_text(qdrant_schema, "# Qdrant URL/collection not provided.\n")
        safe_write_json(qdrant_samples, {"note": "Qdrant URL/collection not provided"})

    # 5) Runtime context
    runtime_ctx = build_runtime_context(
        repo_root, args.db_url, args.qdrant_url, args.qdrant_collection
    )
    safe_write_text(out_root / "runtime_context.yaml", to_yaml(runtime_ctx))

    # 6) Top-level manifest with checksums
    artifacts = [
        intent_tar,
        out_root / "intent_manifest.yaml",
        src_tar,
        out_root / "symbol_index.json",
        db_schema_path,
        db_samples_path,
        qdrant_schema,
        qdrant_samples,
        out_root / "runtime_context.yaml",
    ]
    artifact_list = []
    for pth in artifacts:
        entry = {"path": str(pth.name)}
        if pth.exists():
            entry["sha256"] = sha256_file(pth)
            entry["size_bytes"] = pth.stat().st_size
        else:
            entry["missing"] = True
        artifact_list.append(entry)

    core_manifest = {
        "generated_at": now_utc_iso(),
        "export_dir": str(out_root),
        "artifacts": artifact_list,
        "lane_default": "strict",  # informational for future CML integration
        "notes": [
            "This manifest ties together all exported components.",
            "Checksums allow reproducibility/audit of what was shared.",
        ],
    }
    safe_write_text(out_root / "core_context_manifest.yaml", to_yaml(core_manifest))

    print(f"[OK] Export complete in: {out_root}")


if __name__ == "__main__":
    main()
