#!/usr/-bin/env python3
# tools/build_llm_context.py
import argparse, hashlib, json, os, sys, time, fnmatch, subprocess
from pathlib import Path

TEXT_EXTS = {
    ".py",".pyi",".md",".txt",".yaml",".yml",".toml",".ini",".cfg",".json",".sql",
    ".sh",".bash",".zsh",".ps1",".bat",".gitignore",".dockerignore",".env.example",
    ".rst",".csv"
}
BINARY_EXTS = {
    ".png",".jpg",".jpeg",".gif",".webp",".ico",".bmp",".tiff",".svg",
    ".mp3",".wav",".flac",".ogg",".mp4",".webm",".mov",".avi",
    ".pdf",".zip",".tar",".gz",".xz",".7z",".rar",".whl",".so",".dll",".dylib",
    ".pyc",".pyo"
}
DEFAULT_EXCLUDE_DIRS = {
    ".git",".venv","venv","__pycache__",".pytest_cache",".ruff_cache",".mypy_cache",
    "logs","sandbox","pending_writes","dist","build",".idea",".vscode","demo","work"
}
ROOT_DEFAULTS = ["pyproject.toml","poetry.lock","README.md","LICENSE","Makefile",".gitignore"]

# --- START OF MODIFICATION ---
# We are adding the 'sql' directory to the developer and full profiles
# to ensure the database schema is included in the AI context.
PROFILES = {
    "minimal": {
        "include_dirs": ["src", ".intent", "docs"],
        "root_files": ROOT_DEFAULTS,
    },
    "dev": {
        "include_dirs": ["src", ".intent", "docs", "tests", "sql"], # <-- ADDED 'sql'
        "root_files": ROOT_DEFAULTS,
    },
    "full": {
        "include_dirs": ["src", ".intent", "docs", "tests", "scripts", "tools", "sql"], # <-- ADDED 'sql'
        "root_files": ROOT_DEFAULTS,
    },
    "intent-only": {
        "include_dirs": [".intent"],
        "root_files": [],
    },
}
# --- END OF MODIFICATION ---

def is_probably_binary(path: Path) -> bool:
    if path.suffix.lower() in BINARY_EXTS:
        return True
    try:
        with path.open("rb") as f:
            chunk = f.read(4096)
        if b"\x00" in chunk:
            return True
    except Exception:
        return True
    return False

def sha256_of_bytes(b: bytes) -> str:
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()

def read_text_head(path: Path, max_bytes: int) -> bytes:
    with path.open("rb") as f:
        data = f.read(max_bytes)
    try:
        size = path.stat().st_size
    except Exception:
        size = len(data)
    trailer = b""
    if size > len(data):
        trailer = f"\n[... TRUNCATED: kept first {len(data)} bytes of {size} ...]\n".encode("utf-8")
    return data + trailer

def collect_files(root: Path, include_dirs, extra_paths, exclude_dirs, allow_exts,
                  include_root_files, name_excludes: list[str]):
    files = []
    # add root files if present
    for rf in include_root_files:
        p = root / rf
        if p.exists() and p.is_file():
            files.append(p)

    todo_dirs = []
    for d in include_dirs:
        p = root / d
        if p.exists() and p.is_dir():
            todo_dirs.append(p)

    for extra in extra_paths:
        p = root / extra
        if p.exists():
            if p.is_file():
                files.append(p)
            elif p.is_dir():
                todo_dirs.append(p)

    # Walk allowlisted dirs
    for base in todo_dirs:
        for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
            # prune excluded dirs
            dirnames[:] = [dn for dn in dirnames if dn not in exclude_dirs]
            for fn in filenames:
                # skip by name globs if requested
                if any(fnmatch.fnmatch(fn, pat) for pat in name_excludes):
                    continue
                p = Path(dirpath) / fn
                if p.suffix.lower() in BINARY_EXTS:
                    continue
                if p.suffix.lower() in allow_exts or p.suffix.lower() == "":
                    files.append(p)
                elif p.name in (".env",):
                    # avoid secrets by default
                    continue
    # de-dup + sort deterministically
    uniq = sorted({str(p) for p in files})
    return [Path(u) for u in uniq]

def git_changed_files(since: str) -> set:
    try:
        r = subprocess.run(
            ["git", "diff", "--name-only", since, "HEAD"],
            check=True, capture_output=True, text=True
        )
        return {line.strip() for line in r.stdout.splitlines() if line.strip()}
    except Exception:
        return set()

def write_chunks(outdir: Path, entries, max_chunk_bytes: int):
    outdir.mkdir(parents=True, exist_ok=True)
    chunk_idx = 1
    current = bytearray()
    paths = []

    def flush():
        nonlocal current, chunk_idx, paths
        if not current:
            return None
        name = f"context_{chunk_idx:04d}.txt"
        (outdir / name).write_bytes(current)
        paths.append(name)
        chunk_idx += 1
        current = bytearray()
        return name

    for e in entries:
        block = (
            f"--- START OF FILE {e['path']} ---\n".encode("utf-8")
            + e["bytes"]
            + f"\n--- END OF FILE {e['path']} ---\n\n".encode("utf-8")
        )
        if len(current) + len(block) > max_chunk_bytes and current:
            flush()
        if len(block) > max_chunk_bytes:
            if current:
                flush()
            current.extend(block[:max_chunk_bytes])
            current.extend(b"\n[... CHUNK TRUNCATED ...]\n")
            flush()
        else:
            current.extend(block)
    flush()

    return paths

def main():
    ap = argparse.ArgumentParser(description="Build compact, chunked LLM context from a repo.")
    ap.add_argument("--profile", choices=PROFILES.keys(), default="minimal")
    ap.add_argument("--paths", help="Comma-separated extra paths to include (files or dirs).", default="")
    ap.add_argument("--exclude-dirs", help="Comma-separated dirs to exclude in addition to defaults.", default="")
    ap.add_argument("--names-exclude", help="Comma-separated filename globs to exclude (e.g. '*.md,*.csv')", default="")
    ap.add_argument("--max-file-bytes", type=int, default=300_000, help="Max bytes per file to capture.")
    ap.add_argument("--max-chunk-bytes", type=int, default=12_000_000, help="Max bytes per output chunk.")
    ap.add_argument("--max-files", type=int, default=0, help="Stop after N files (0 = no limit).")
    ap.add_argument("--outdir", default="llm_context", help="Output directory.")
    ap.add_argument("--since", help="Only include files changed since this git ref (e.g. v0.2.0)", default=None)
    ap.add_argument("--print-summary", action="store_true")
    args = ap.parse_args()

    root = Path.cwd()
    prof = PROFILES[args.profile]
    include_dirs = prof["include_dirs"]
    include_root_files = prof["root_files"]

    extra_paths = [p.strip() for p in args.paths.split(",") if p.strip()]
    exclude_dirs = set(DEFAULT_EXCLUDE_DIRS)
    exclude_dirs |= {d.strip() for d in args.exclude_dirs.split(",") if d.strip()}
    name_excludes = [p.strip() for p in args.names_exclude.split(",") if p.strip()]

    candidates = collect_files(
        root, include_dirs, extra_paths, exclude_dirs, TEXT_EXTS, include_root_files, name_excludes
    )

    if args.since:
        changed = git_changed_files(args.since)
        if changed:
            candidates = [p for p in candidates if str(p.relative_to(root)) in changed]
        else:
            candidates = []

    # Deterministic order, then cap if needed
    candidates = sorted(candidates, key=lambda p: str(p))
    if args.max_files and args.max_files > 0:
        candidates = candidates[: args.max_files]

    entries = []
    total_bytes = 0
    total_files = 0
    skipped_binaries = []
    unreadable = 0
    for p in candidates:
        try:
            if is_probably_binary(p):
                skipped_binaries.append(str(p))
                continue
            data = read_text_head(p, args.max_file_bytes)
            total_bytes += len(data)
            total_files += 1
            entries.append({
                "path": str(p.relative_to(root)),
                "sha256": sha256_of_bytes(data),
                "size_bytes_captured": len(data),
                "bytes": data,
            })
        except Exception:
            unreadable += 1
            continue

    entries.sort(key=lambda e: e["path"])
    outdir = Path(args.outdir)
    chunk_paths = write_chunks(outdir, entries, args.max_chunk_bytes)

    manifest = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "root": str(root),
        "profile": args.profile,
        "include_dirs": include_dirs,
        "extra_paths": extra_paths,
        "exclude_dirs": sorted(list(exclude_dirs)),
        "names_exclude": name_excludes,
        "max_file_bytes": args.max_file_bytes,
        "max_chunk_bytes": args.max_chunk_bytes,
        "max_files": args.max_files,
        "total_files": total_files,
        "total_bytes_captured": total_bytes,
        "chunks": chunk_paths,
        "files": [{"path": e["path"], "sha256": e["sha256"], "size_bytes_captured": e["size_bytes_captured"]} for e in entries],
        "skipped_binary_like": skipped_binaries[:200],
        "unreadable_count": unreadable,
    }
    (outdir / "index.json").write_text(json.dumps(manifest, indent=2))

    # Write a brief human summary
    (outdir / "summary.txt").write_text(
        "\n".join([
            f"Created: {manifest['created_at']}",
            f"Profile: {manifest['profile']}",
            f"Files captured: {total_files}",
            f"Bytes captured: {total_bytes}",
            f"Chunks: {len(chunk_paths)}",
            f"Skipped (binary-like): {len(skipped_binaries)}",
            f"Unreadable: {unreadable}",
            f"Outdir: {outdir}",
        ]) + "\n"
    )

    if args.print_summary:
        mb = total_bytes / (1024*1024)
        print(f"[OK] Captured {total_files} files, {mb:.2f} MiB into {len(chunk_paths)} chunk(s):")
        for c in chunk_paths:
            print(f"  - {c}")
        print(f"Manifest: {outdir/'index.json'}")
        print(f"Summary : {outdir/'summary.txt'}")

if __name__ == "__main__":
    sys.exit(main())