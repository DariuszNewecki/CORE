# src/features/maintenance/scripts/context_export.py
# ID: af5abbe5-0304-4f54-9eb0-596d71791b41

"""
Export a complete, compact operational snapshot of CORE.
Refactored to use canonical services (FileHandler, GitService, Settings).

CONSTITUTIONAL FIX:
- Aligned with 'governance.artifact_mutation.traceable'.
- Replaced direct tarfile writes with governed FileHandler mutations.
- Uses io.BytesIO to buffer archives before persisting via the mutation surface.
- Ensures all exported artifacts are recorded in the action ledger.
"""

from __future__ import annotations

import ast
import asyncio
import dataclasses
import hashlib
import io
import json
import tarfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from shared.config import settings
from shared.infrastructure.git_service import GitService
from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger
from shared.time import now_iso


logger = getLogger(__name__)


@dataclasses.dataclass
# ID: fc33426e-cb3d-461d-b20f-a02b90f2408f
class Symbol:
    module: str
    kind: str
    name: str
    lineno: int
    signature: str
    doc: str | None


# ---------------------------
# Helpers
# ---------------------------


# ID: 772bd5da-7fcf-4aa1-a23c-3d5889d0c149
def sha256_file(path: Path) -> str:
    """Pure helper for file hashing."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


# ID: 377f784e-516c-404b-8b36-ccd4346d299f
def build_signature_from_ast(node: ast.AST) -> str:
    """Pure helper for AST signature extraction."""
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return ""
    args = [a.arg for a in node.args.args]
    if node.args.vararg:
        args.append("*" + node.args.vararg.arg)
    for a in node.args.kwonlyargs:
        args.append(a.arg + "=")
    if node.args.kwarg:
        args.append("**" + node.args.kwarg.arg)
    return f"({', '.join(args)})"


# ---------------------------
# Governed Export Logic
# ---------------------------


# ID: 6c005976-a799-446d-aea4-2d04782c6b76
class ContextExporter:
    """Orchestrates the system snapshot using governed services."""

    def __init__(self, output_base: Path | None = None):
        self.repo_root = settings.REPO_PATH
        self.output_base = output_base or (self.repo_root / "var" / "exports")
        self.timestamp = now_iso().replace(":", "-").split(".")[0]
        self.export_rel_dir = f"var/exports/core_export_{self.timestamp}"

        # Mutation surface
        self.fh = FileHandler(str(self.repo_root))
        self.git = GitService(self.repo_root)

    # ID: 2f5bda9b-4da0-486d-8748-c2c0a75a42dc
    async def run(self) -> str:
        """Execute the full export pipeline."""
        logger.info("🚀 Starting CORE Context Export...")

        # Ensure export directory
        self.fh.ensure_dir(self.export_rel_dir)

        # 1. Body (src) and Mind (.intent) Bundling
        self._bundle_directories()

        # 2. Symbol Analysis
        await self._generate_symbol_index()

        # 3. Database Metadata (State)
        await self._export_db_schema()

        # 4. Vector Metadata (Memory)
        await self._export_qdrant_metadata()

        # 5. Runtime & Manifest
        await self._finalize_manifest()

        logger.info("✅ Export complete: %s", self.export_rel_dir)
        return self.export_rel_dir

    def _bundle_directories(self):
        """Create .tar.gz archives of key directories via FileHandler."""
        logger.info("📦 Bundling src/ and .intent/...")

        for folder in ["src", ".intent"]:
            out_name = f"{folder.replace('.', '')}.tar.gz"
            rel_out_path = f"{self.export_rel_dir}/{out_name}"

            # CONSTITUTIONAL FIX:
            # We create the archive in memory using io.BytesIO instead of opening
            # the filesystem directly. This allows us to pass the final bytes
            # to the FileHandler for a governed write.
            buffer = io.BytesIO()
            with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
                src_path = self.repo_root / folder
                if src_path.exists():
                    tar.add(src_path, arcname=folder)

            # Persist the archive via the approved mutation surface
            self.fh.write_runtime_bytes(rel_out_path, buffer.getvalue())
            logger.debug("   -> Governed Archive Created: %s", rel_out_path)

    async def _generate_symbol_index(self):
        """Scan Python symbols and write index via FileHandler."""
        logger.info("🔍 Scanning Python symbols...")
        symbols = []
        src_root = self.repo_root / "src"

        for py in src_root.rglob("*.py"):
            rel_mod = str(py.relative_to(src_root)).replace("/", ".")[:-3]
            try:
                txt = py.read_text(encoding="utf-8")
                tree = ast.parse(txt)
                for node in tree.body:
                    if isinstance(node, ast.ClassDef):
                        symbols.append(
                            Symbol(
                                rel_mod,
                                "class",
                                node.name,
                                node.lineno,
                                "(...)",
                                ast.get_docstring(node),
                            )
                        )
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if not node.name.startswith("_"):
                            sig = build_signature_from_ast(node)
                            symbols.append(
                                Symbol(
                                    rel_mod,
                                    "function",
                                    node.name,
                                    node.lineno,
                                    sig,
                                    ast.get_docstring(node),
                                )
                            )
            except Exception:
                continue

        index_data = {
            "generated_at": now_iso(),
            "symbols": [dataclasses.asdict(s) for s in symbols],
        }
        self.fh.write_runtime_json(
            f"{self.export_rel_dir}/symbol_index.json", index_data
        )

    async def _export_db_schema(self):
        """Capture DB schema using subprocess, persisted via FileHandler."""
        logger.info("🗄️ Capturing Database Schema...")
        db_url = settings.DATABASE_URL

        try:
            # Note: requires pg_dump installed on host
            proc = await asyncio.create_subprocess_exec(
                "pg_dump",
                "--schema-only",
                "--no-owner",
                db_url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            if stdout:
                self.fh.write_runtime_text(
                    f"{self.export_rel_dir}/db_schema.sql", stdout.decode()
                )
        except Exception as e:
            logger.warning("Could not export DB schema: %s", e)

    async def _export_qdrant_metadata(self):
        """Fetch Qdrant collection info via HTTP."""
        logger.info("🧠 Capturing Qdrant Metadata...")
        q_url = settings.QDRANT_URL.rstrip("/")
        q_col = settings.QDRANT_COLLECTION_NAME

        try:
            # Use urllib for standard-lib compliance in scripts
            url = f"{q_url}/collections/{q_col}"
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                self.fh.write_runtime_json(
                    f"{self.export_rel_dir}/qdrant_info.json", data
                )
        except Exception as e:
            logger.warning("Could not export Qdrant metadata: %s", e)

    async def _finalize_manifest(self):
        """Create the top-level manifest and checksums."""
        logger.info("📄 Finalizing Export Manifest...")

        manifest = {
            "export_id": f"core_export_{self.timestamp}",
            "generated_at": now_iso(),
            "core_version": "1.0.0",
            "git_info": {
                "commit": (
                    self.git.get_current_commit() if self.git.is_git_repo() else "none"
                ),
                "branch": "unknown",
            },
            "environment": settings.CORE_ENV,
            "checksums": {},
        }

        # Calculate checksums for the bundles we created
        export_path = self.repo_root / self.export_rel_dir
        for bundle in export_path.glob("*.tar.gz"):
            manifest["checksums"][bundle.name] = sha256_file(bundle)

        self.fh.write_runtime_json(
            f"{self.export_rel_dir}/core_context_manifest.json", manifest
        )


# ---------------------------
# CLI Entrypoint
# ---------------------------


# ID: a13aecdf-8b7f-4649-bcd7-e42aab66b0bc
async def main():
    exporter = ContextExporter()
    await exporter.run()


if __name__ == "__main__":
    asyncio.run(main())
