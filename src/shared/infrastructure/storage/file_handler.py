# src/shared/infrastructure/storage/file_handler.py
# ID: 9e64f98a-0740-4c5b-bc0e-f253b6a0af1e
"""
Safe, auditable file operations with staged writes.
"""

from __future__ import annotations

import ast
import json
import shutil
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from body.governance.intent_guard import get_intent_guard
from shared.config import settings
from shared.logger import getLogger
from shared.path_resolver import PathResolver


logger = getLogger(__name__)


# ID: fe5be006-30f5-4d69-bfd6-c34a9708eb4d
@dataclass(frozen=True)
# ID: 0521c538-949d-4203-9ff3-5ba8934b297e
class FileOpResult:
    status: str
    message: str
    detail: str


# ID: 4684ec9b-095a-428b-95bc-60e5003dc7f7
class FileHandler:
    """Central class for safe, auditable file operations in CORE."""

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path).resolve()
        if not self.repo_path.is_dir():
            raise ValueError(f"Invalid repository path provided: {repo_path}")

        self.log_dir = self.repo_path / "var" / "logs"
        self.pending_dir = self.repo_path / "var" / "workflows" / "pending_writes"

        path_resolver = PathResolver.from_repo(
            repo_root=self.repo_path,
            intent_root=self.repo_path / ".intent",
        )

        self._guard = get_intent_guard(
            repo_path=self.repo_path,
            path_resolver=path_resolver,
            strict_mode=settings.CORE_STRICT_MODE,
        )

        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.pending_dir.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------------------
    # Internal Logic: The Paperwork (Auto-ID Generation)
    # ---------------------------------------------------------------------

    def _ensure_id_anchors(self, content: str) -> str:
        """Injects missing # ID: tags for public symbols automatically."""
        lines = content.splitlines()
        new_lines: list[str] = []

        for i, line in enumerate(lines):
            stripped = line.strip()
            is_def = (
                stripped.startswith("def ")
                or stripped.startswith("async def ")
                or stripped.startswith("class ")
            )
            # Ignore private symbols
            is_private = stripped.startswith("_") or " _" in stripped

            if is_def and not is_private:
                prev_line = lines[i - 1].strip() if i > 0 else ""
                if not prev_line.startswith("# ID:"):
                    indent = " " * (len(line) - len(line.lstrip()))
                    new_id = str(uuid.uuid4())
                    new_lines.append(f"{indent}# ID: {new_id}")

            new_lines.append(line)

        return "\n".join(new_lines) + ("\n" if content.endswith("\n") else "")

    # ---------------------------------------------------------------------
    # Mutation APIs
    # ---------------------------------------------------------------------

    # ID: dea4534e-f63a-4b02-81fc-67cb12bf8fb8
    def write_runtime_text(
        self,
        rel_path: str,
        content: str,
        impact: str | None = None,
    ) -> FileOpResult:
        rel_path = rel_path.strip().lstrip("./")

        # 1. THE GUARD: Constitutional boundary check (Path access)
        self._guard_paths([rel_path], impact=impact)

        # 2. THE IRON HAND: Syntax Gate (Structural Integrity)
        if rel_path.endswith(".py"):
            try:
                ast.parse(content)
            except SyntaxError as e:
                logger.error("Refusing to write invalid Python to %s: %s", rel_path, e)
                raise ValueError(f"Syntax Error in generated code for {rel_path}: {e}")

            # 3. THE PAPERWORK: Metadata finalization
            # (Note: Uniqueness check is DELEGATED to Feature layer Step 2)
            if "src/" in rel_path:
                content = self._ensure_id_anchors(content)

        # 4. THE EXECUTION: Atomic write
        abs_path = self._resolve_repo_path(rel_path)
        self._atomic_write_text(abs_path, content)
        return FileOpResult("success", "Wrote runtime text", rel_path)

    # ID: 9170fbe6-887f-4793-9e54-e1124b568dad
    def write_runtime_bytes(self, rel_path: str, content: bytes) -> FileOpResult:
        rel_path = rel_path.strip().lstrip("./")
        self._guard_paths([rel_path])
        abs_path = self._resolve_repo_path(rel_path)
        self._atomic_write_bytes(abs_path, content)
        return FileOpResult("success", "Wrote runtime bytes", rel_path)

    # ID: 9e9e41dc-9dc2-451b-940f-15199f23d548
    def write_runtime_json(self, rel_path: str, payload: Any) -> FileOpResult:
        rel_path = rel_path.strip().lstrip("./")
        self._guard_paths([rel_path])
        abs_path = self._resolve_repo_path(rel_path)
        self._atomic_write_text(abs_path, json.dumps(payload, indent=2))
        return FileOpResult("success", "Wrote runtime json", rel_path)

    # ID: 84aa153b-1651-4ca8-abf3-f15a57fe6b80
    def add_pending_write(self, prompt: str, suggested_path: str, code: str) -> str:
        suggested_path = suggested_path.strip().lstrip("./")
        self._guard_paths([suggested_path])
        payload = {"prompt": prompt, "suggested_path": suggested_path, "code": code}
        fname = f"pw-{abs(hash(suggested_path + prompt))}.json"
        out = self.pending_dir / fname
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return str(out)

    # ID: 5c958c3b-d6bb-4c30-ad37-5b1abcaac762
    def ensure_dir(self, rel_dir: str) -> FileOpResult:
        rel_dir = rel_dir.strip().strip("/").lstrip("./")
        self._guard_paths([rel_dir + "/"])
        abs_dir = self._resolve_repo_path(rel_dir)
        abs_dir.mkdir(parents=True, exist_ok=True)
        return FileOpResult("success", "Directory ensured", rel_dir)

    # ID: 5f626d7b-5ce4-46c8-adc6-6228eef7c41a
    def remove_file(self, rel_path: str) -> FileOpResult:
        rel_path = rel_path.strip().lstrip("./")
        self._guard_paths([rel_path])
        abs_path = self._resolve_repo_path(rel_path)
        abs_path.unlink(missing_ok=True)
        return FileOpResult("success", "File removed", rel_path)

    # ID: 443bb5d6-306d-4d03-ab69-762cc14b1eb3
    def remove_tree(self, rel_dir: str) -> FileOpResult:
        rel_dir = rel_dir.strip().strip("/").lstrip("./")
        self._guard_paths([rel_dir + "/"])
        abs_dir = self._resolve_repo_path(rel_dir)
        if abs_dir.exists():
            shutil.rmtree(abs_dir, ignore_errors=True)
        return FileOpResult("success", "Tree removed", rel_dir)

    # ID: c05980dd-b125-49a3-9e9b-0a0c4e1e33b9
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

    # ID: 6a9927f8-4467-4b95-989a-fdafcc8a4615
    def copy_repo_snapshot(
        self,
        rel_dst_dir: str,
        exclude_top_level: Iterable[str] = ("var", ".git", "__pycache__", ".venv"),
    ) -> FileOpResult:
        rel_dst_dir = rel_dst_dir.strip().strip("/").lstrip("./")
        self._guard_paths([rel_dst_dir + "/"])
        abs_dst = self._resolve_repo_path(rel_dst_dir)
        if abs_dst.exists():
            shutil.rmtree(abs_dst, ignore_errors=True)
        abs_dst.parent.mkdir(parents=True, exist_ok=True)

        exclude_set = {str(x).strip("/").strip() for x in exclude_top_level}

        def _ignore(dirpath: str, names: list[str]) -> set[str]:
            p = Path(dirpath)
            if p.resolve() != self.repo_path.resolve():
                return set()
            return {n for n in names if n in exclude_set}

        shutil.copytree(self.repo_path, abs_dst, ignore=_ignore)
        return FileOpResult("success", "Copied repo snapshot", f". -> {rel_dst_dir}")

    # ---------------------------------------------------------------------
    # Path + Guard Helpers
    # ---------------------------------------------------------------------

    def _resolve_repo_path(self, rel_path: str) -> Path:
        rel_path = str(rel_path).lstrip("./")
        candidate = (self.repo_path / rel_path).resolve()
        if not candidate.is_relative_to(self.repo_path):
            raise ValueError(f"Attempted to escape repository boundary: {rel_path}")
        return candidate

    def _guard_paths(self, rel_paths: list[str], impact: str | None = None) -> None:
        cleaned: list[str] = [str(p).lstrip("./") for p in rel_paths]
        result = self._guard.check_transaction(cleaned, impact=impact)
        if result.is_valid:
            return
        msg = (
            result.violations[0].message
            if result.violations
            else "Blocked by IntentGuard."
        )
        raise ValueError(f"Blocked by IntentGuard: {msg}")

    def _atomic_write_text(self, abs_path: Path, content: str) -> None:
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = abs_path.with_suffix(abs_path.suffix + ".tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(abs_path)

    def _atomic_write_bytes(self, abs_path: Path, content: bytes) -> None:
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = abs_path.with_suffix(abs_path.suffix + ".tmp")
        tmp.write_bytes(content)
        tmp.replace(abs_path)
