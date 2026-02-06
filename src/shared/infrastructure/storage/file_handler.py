# src/shared/infrastructure/storage/file_handler.py

"""
Provides safe, auditable file operations with staged writes
requiring confirmation for traceability and rollback capabilities.

Extended:
- FileHandler is the ONLY approved mutation surface for filesystem writes/deletes/moves.
- IntentGuard is enforced on every mutation (CORE must never write to .intent/**).
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from body.governance.intent_guard import IntentGuard
from shared.logger import getLogger
from shared.path_resolver import PathResolver


logger = getLogger(__name__)


@dataclass(frozen=True)
# ID: fe5be006-30f5-4d69-bfd6-c34a9708eb4d
class FileOpResult:
    status: str
    message: str
    detail: str


# ID: 9e64f98a-0740-4c5b-bc0e-f253b6a0af1e
class FileHandler:
    """
    Central class for safe, auditable file operations in CORE.

    Policy:
      - All filesystem mutations must go through FileHandler (or governed CLI).
      - IntentGuard is enforced on every mutation (NO WRITES to .intent/**).
    """

    # ID: storage.file_handler.init
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path).resolve()
        if not self.repo_path.is_dir():
            raise ValueError(f"Invalid repository path provided: {repo_path}")

        # Align to PathResolver canonical runtime layout: var/*
        self.log_dir = self.repo_path / "var" / "logs"
        self.pending_dir = self.repo_path / "var" / "workflows" / "pending_writes"

        path_resolver = PathResolver.from_repo(
            repo_root=self.repo_path, intent_root=self.repo_path / ".intent"
        )
        self._guard = IntentGuard(self.repo_path, path_resolver)

        # Ensure internal runtime dirs exist (mkdir counts => FileHandler owns it)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.pending_dir.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    # ID: storage.file_handler._resolve_repo_path
    def _resolve_repo_path(self, rel_path: str) -> Path:
        rel_path = str(rel_path).lstrip("./")
        candidate = (self.repo_path / rel_path).resolve()
        if not candidate.is_relative_to(self.repo_path):
            raise ValueError(f"Attempted to escape repository boundary: {rel_path}")
        return candidate

    # ID: storage.file_handler._guard_paths
    def _guard_paths(self, rel_paths: list[str], impact: str | None = None) -> None:
        cleaned: list[str] = []
        for p in rel_paths:
            cleaned.append(str(p).lstrip("./"))

        allowed, violations = self._guard.check_transaction(cleaned, impact=impact)
        if allowed:
            return
        msg = violations[0].message if violations else "Blocked by IntentGuard."
        raise ValueError(f"Blocked by IntentGuard: {msg}")

    # ID: storage.file_handler._atomic_write_text
    def _atomic_write_text(self, abs_path: Path, content: str) -> None:
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = abs_path.with_suffix(abs_path.suffix + ".tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(abs_path)

    # ID: storage.file_handler._atomic_write_bytes
    def _atomic_write_bytes(self, abs_path: Path, content: bytes) -> None:
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = abs_path.with_suffix(abs_path.suffix + ".tmp")
        tmp.write_bytes(content)
        tmp.replace(abs_path)

    # -------------------------------------------------------------------------
    # Staged mutation API (pending_writes)
    # -------------------------------------------------------------------------

    # ID: storage.file_handler.add_pending_write
    # ID: a0de0635-8e35-44d7-9afc-78d23ccfe4bb
    def add_pending_write(self, prompt: str, suggested_path: str, code: str) -> str:
        suggested_path = suggested_path.strip().lstrip("./")
        self._guard_paths([suggested_path])

        payload = {
            "prompt": prompt,
            "suggested_path": suggested_path,
            "code": code,
        }
        fname = f"pw-{abs(hash(suggested_path + prompt))}.json"
        out = self.pending_dir / fname
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return str(out)

    # -------------------------------------------------------------------------
    # Runtime mutation API (guarded, but not staged)
    # -------------------------------------------------------------------------

    # ID: storage.file_handler.ensure_dir
    # ID: f718a177-bfe9-48fa-84d6-33e0dbc19945
    def ensure_dir(self, rel_dir: str) -> FileOpResult:
        rel_dir = rel_dir.strip().strip("/").lstrip("./")
        self._guard_paths([rel_dir + "/"])
        abs_dir = self._resolve_repo_path(rel_dir)
        abs_dir.mkdir(parents=True, exist_ok=True)
        return FileOpResult("success", "Directory ensured", rel_dir)

    # ID: storage.file_handler.write_runtime_text
    # ID: f0c8fd37-1d1a-4163-8a07-367df0aefbe5
    def write_runtime_text(
        self, rel_path: str, content: str, impact: str | None = None
    ) -> FileOpResult:
        rel_path = rel_path.strip().lstrip("./")
        self._guard_paths([rel_path], impact=impact)
        abs_path = self._resolve_repo_path(rel_path)
        self._atomic_write_text(abs_path, content)
        return FileOpResult("success", "Wrote runtime text", rel_path)

    # ID: storage.file_handler.write_runtime_bytes
    # ID: c19ed087-96be-4bde-91a5-c0055a0cf7aa
    def write_runtime_bytes(self, rel_path: str, content: bytes) -> FileOpResult:
        rel_path = rel_path.strip().lstrip("./")
        self._guard_paths([rel_path])
        abs_path = self._resolve_repo_path(rel_path)
        self._atomic_write_bytes(abs_path, content)
        return FileOpResult("success", "Wrote runtime bytes", rel_path)

    # ID: storage.file_handler.write_runtime_json
    # ID: 2c255d3e-8db9-45d6-9b3b-8f4de2c6c6a7
    def write_runtime_json(self, rel_path: str, payload: Any) -> FileOpResult:
        rel_path = rel_path.strip().lstrip("./")
        self._guard_paths([rel_path])
        abs_path = self._resolve_repo_path(rel_path)
        self._atomic_write_text(abs_path, json.dumps(payload, indent=2))
        return FileOpResult("success", "Wrote runtime json", rel_path)

    # ID: storage.file_handler.remove_file
    # ID: 3e7a13aa-7f4c-4e2b-b1b4-4b8c85c1c6f1
    def remove_file(self, rel_path: str) -> FileOpResult:
        rel_path = rel_path.strip().lstrip("./")
        self._guard_paths([rel_path])
        abs_path = self._resolve_repo_path(rel_path)
        abs_path.unlink(missing_ok=True)
        return FileOpResult("success", "File removed", rel_path)

    # ID: storage.file_handler.remove_tree
    # ID: c1177e72-1430-4ab0-a187-845a08374be3
    def remove_tree(self, rel_dir: str) -> FileOpResult:
        rel_dir = rel_dir.strip().strip("/").lstrip("./")
        self._guard_paths([rel_dir + "/"])
        abs_dir = self._resolve_repo_path(rel_dir)
        if abs_dir.exists():
            shutil.rmtree(abs_dir, ignore_errors=True)
        return FileOpResult("success", "Tree removed", rel_dir)

    # -------------------------------------------------------------------------
    # Copy/move utilities (guarded)
    # -------------------------------------------------------------------------

    # ID: storage.file_handler.copy_tree
    # ID: 43d136fb-d205-45c6-82a0-864af943b333
    def copy_tree(self, rel_src_dir: str, rel_dst_dir: str) -> FileOpResult:
        rel_src_dir = rel_src_dir.strip().strip("/").lstrip("./")
        rel_dst_dir = rel_dst_dir.strip().strip("/").lstrip("./")
        self._guard_paths([rel_src_dir + "/", rel_dst_dir + "/"])

        abs_src = self._resolve_repo_path(rel_src_dir)
        abs_dst = self._resolve_repo_path(rel_dst_dir)

        if abs_dst.exists():
            shutil.rmtree(abs_dst, ignore_errors=True)

        shutil.copytree(abs_src, abs_dst)
        return FileOpResult("success", "Copied tree", f"{rel_src_dir} -> {rel_dst_dir}")

    # ID: storage.file_handler.copy_repo_snapshot
    # ID: 8d0d9a7b-1e41-4cf9-b0d1-3d2a2f37c1ad
    def copy_repo_snapshot(
        self,
        rel_dst_dir: str,
        exclude_top_level: Iterable[str] = ("var", ".git", "__pycache__", ".venv"),
    ) -> FileOpResult:
        """
        Copy a snapshot of the repository into rel_dst_dir.

        This exists specifically to support canary environments *inside* the repo (under var/),
        without recursively copying the destination into itself.

        Implementation:
        - Copies self.repo_path -> abs_dst
        - Ignores top-level directories listed in exclude_top_level (default includes 'var')
        """
        rel_dst_dir = rel_dst_dir.strip().strip("/").lstrip("./")
        self._guard_paths([rel_dst_dir + "/"])

        abs_dst = self._resolve_repo_path(rel_dst_dir)
        if abs_dst.exists():
            shutil.rmtree(abs_dst, ignore_errors=True)
        abs_dst.parent.mkdir(parents=True, exist_ok=True)

        exclude_set = {str(x).strip("/").strip() for x in exclude_top_level}

        def _ignore(dirpath: str, names: list[str]) -> set[str]:
            p = Path(dirpath)
            # Only apply ignore rules at repo root.
            if p.resolve() != self.repo_path:
                return set()
            return {n for n in names if n in exclude_set}

        shutil.copytree(self.repo_path, abs_dst, ignore=_ignore)
        return FileOpResult("success", "Copied repo snapshot", f". -> {rel_dst_dir}")
