# src/shared/infrastructure/storage/file_handler.py
"""
Safe, auditable file operations with staged writes.
"""

from __future__ import annotations

import ast
import json
import shutil
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from body.governance.intent_guard import get_intent_guard
from mind.governance.violation_report import ConstitutionalViolationError
from shared.config import settings
from shared.governance_token import current_capability
from shared.infrastructure.intent.operational_mode import current_mode
from shared.infrastructure.intent.target_class import resolve_target_class
from shared.logger import getLogger
from shared.path_resolver import PathResolver
from shared.utils.common_knowledge import ensure_trailing_newline


logger = getLogger(__name__)


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

    # ID: 6f4d8a72-9c31-4e85-b297-1a3e9f5d6b08
    def write(
        self,
        rel_path: str,
        content: str | bytes,
        *,
        impact: str | None = None,
    ) -> FileOpResult:
        """Single-channel filesystem write (ADR-097 D4).

        Resolves the target class from ``rel_path`` and applies the
        ADR-097 D3 behavior matrix:

        - ``repo-source`` (src/, tests/, top-level repo files): syntax
          check on .py; ``# ID:`` anchor injection for new public defs;
          trailing newline; IntentGuard repo-source tier.
        - ``runtime-output`` (reports/, var/cache/, var/logs/,
          var/workflows/): no source-shape transforms; trailing
          newline for text; IntentGuard runtime tier.
        - ``ephemeral-scratch`` (var/tmp/): no source-shape transforms,
          no schema/syntax gates; trailing newline for text; IntentGuard
          ephemeral tier (capability-checked, policy rules bypassed).
        - ``governed-artifact`` (.intent/, .specs/): no source-shape
          transforms (the META/API path runs validation upstream of
          this call in step 6); IntentGuard governed-artifact tier,
          which today is the hard invariant block on .intent/ writes.

        ``content`` may be ``str`` (text path) or ``bytes`` (bytes
        path). Bytes content skips source-shape transforms regardless
        of target class — the transforms are text-only.

        Existing public methods (write_runtime_text, write_runtime_bytes,
        write_runtime_json, write_validated_bytes, ensure_dir,
        remove_file/_tree, copy_tree, copy_repo_snapshot) remain
        unchanged in step 3 — they are migrated to delegate through
        this entry in step 4 of the ADR-097 Migration.
        """
        rel_path = rel_path.strip().removeprefix("./")
        # Target-class boundaries are constitutional (ADR-097 D2) — read
        # from the canonical CORE install (resolve_default_repo_path)
        # rather than from this FileHandler's repo_path, which in a
        # consumer-repo deployment is the user's project root and may
        # not carry CORE's .intent/ tree.
        target_class = resolve_target_class(rel_path)

        self._guard_paths(
            [rel_path],
            impact=impact,
            target_classes={rel_path: target_class},
        )

        abs_path = self._resolve_repo_path(rel_path)
        if isinstance(content, str):
            # Source-shape transforms apply only to repo-source paths.
            if rel_path.endswith(".py") and target_class == "repo-source":
                try:
                    ast.parse(content)
                except SyntaxError as e:
                    logger.error(
                        "Refusing to write invalid Python to %s: %s", rel_path, e
                    )
                    raise ValueError(
                        f"Syntax Error in generated code for {rel_path}: {e}"
                    )
                content = self._ensure_id_anchors(content)
            content = ensure_trailing_newline(content)
            self._atomic_write_text(abs_path, content)
        else:
            self._atomic_write_bytes(abs_path, content)
        return FileOpResult("success", "Wrote file", rel_path)

    # ID: dea4534e-f63a-4b02-81fc-67cb12bf8fb8
    def write_runtime_text(
        self,
        rel_path: str,
        content: str,
        impact: str | None = None,
    ) -> FileOpResult:
        """Thin wrapper over the unified ``write`` entry (ADR-097 step 4).

        Behavior is now derived from the resolved target class instead
        of from the substring ``"src/"`` in ``rel_path``. The substring
        bug — a path like ``var/tmp/.../src/foo.py`` getting ID anchor
        injection mid-flight — is structurally foreclosed because that
        path classifies as ``ephemeral-scratch`` and the ID anchor
        injection only fires for ``repo-source``.

        The return shape preserves the legacy ``message`` for callers
        that inspect ``FileOpResult.message`` directly.
        """
        result = self.write(rel_path, content, impact=impact)
        return FileOpResult(result.status, "Wrote runtime text", result.detail)

    # ID: 9170fbe6-887f-4793-9e54-e1124b568dad
    def write_runtime_bytes(self, rel_path: str, content: bytes) -> FileOpResult:
        """Thin wrapper over the unified ``write`` entry (ADR-097 step 4).

        Bytes content skips source-shape transforms in ``write`` regardless
        of target class, so this wrapper's behavior is identical to its
        pre-flip form.
        """
        result = self.write(rel_path, content)
        return FileOpResult(result.status, "Wrote runtime bytes", result.detail)

    # ID: d21ce0ee-5d6c-4030-b294-3cd33715c41a
    def write_validated_bytes(self, rel_path: str, content: bytes) -> FileOpResult:
        """Atomic byte-write that bypasses IntentGuard.

        Used by ActionExecutor's worktree-sandbox propagation step
        (ADR-071 D2.2): the content was already governance-validated by
        the action that produced it inside the sandbox, so re-running
        IntentGuard here would duplicate work. Path-escape protection
        is still enforced via _resolve_repo_path. NOT a general write
        surface — actions must use write_runtime_text / _bytes.
        """
        rel_path = rel_path.strip().removeprefix("./")
        abs_path = self._resolve_repo_path(rel_path)
        self._atomic_write_bytes(abs_path, content)
        return FileOpResult("success", "Wrote validated bytes", rel_path)

    # ID: 9e9e41dc-9dc2-451b-940f-15199f23d548
    def write_runtime_json(self, rel_path: str, payload: Any) -> FileOpResult:
        """Thin wrapper over the unified ``write`` entry (ADR-097 step 4).

        Behavior change from pre-flip: the JSON output now gains a
        trailing newline via ``write``'s text-path ``ensure_trailing_newline``
        normalization. The pre-flip form wrote ``json.dumps(...)``
        verbatim, ending mid-brace. The new behavior is POSIX-friendly
        and diff-minimal; it matches every other text-write through
        FileHandler.
        """
        result = self.write(rel_path, json.dumps(payload, indent=2))
        return FileOpResult(result.status, "Wrote runtime json", result.detail)

    # ID: 84aa153b-1651-4ca8-abf3-f15a57fe6b80
    def add_pending_write(self, prompt: str, suggested_path: str, code: str) -> str:
        suggested_path = suggested_path.strip().removeprefix("./")
        self._guard_paths([suggested_path], op_class="create")
        payload = {"prompt": prompt, "suggested_path": suggested_path, "code": code}
        fname = f"pw-{abs(hash(suggested_path + prompt))}.json"
        out = self.pending_dir / fname
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return str(out)

    # ID: 5c958c3b-d6bb-4c30-ad37-5b1abcaac762
    def ensure_dir(self, rel_dir: str) -> FileOpResult:
        rel_dir = rel_dir.strip().removeprefix("./").strip("/")
        self._guard_paths([rel_dir + "/"], op_class="create")
        abs_dir = self._resolve_repo_path(rel_dir)
        abs_dir.mkdir(parents=True, exist_ok=True)
        return FileOpResult("success", "Directory ensured", rel_dir)

    # ID: 5f626d7b-5ce4-46c8-adc6-6228eef7c41a
    def remove_file(self, rel_path: str) -> FileOpResult:
        rel_path = rel_path.strip().removeprefix("./")
        self._guard_paths([rel_path], op_class="delete")
        abs_path = self._resolve_repo_path(rel_path)
        abs_path.unlink(missing_ok=True)
        return FileOpResult("success", "File removed", rel_path)

    # ID: 443bb5d6-306d-4d03-ab69-762cc14b1eb3
    def remove_tree(self, rel_dir: str) -> FileOpResult:
        rel_dir = rel_dir.strip().removeprefix("./").strip("/")
        self._guard_paths([rel_dir + "/"], op_class="delete")
        abs_dir = self._resolve_repo_path(rel_dir)
        if abs_dir.exists():
            shutil.rmtree(abs_dir, ignore_errors=True)
        return FileOpResult("success", "Tree removed", rel_dir)

    # ID: c05980dd-b125-49a3-9e9b-0a0c4e1e33b9
    def copy_tree(self, rel_src_dir: str, rel_dst_dir: str) -> FileOpResult:
        rel_src_dir = rel_src_dir.strip().removeprefix("./").strip("/")
        rel_dst_dir = rel_dst_dir.strip().removeprefix("./").strip("/")
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
        rel_dst_dir = rel_dst_dir.strip().removeprefix("./").strip("/")
        self._guard_paths([rel_dst_dir + "/"], op_class="create")
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
        """Resolve a repo-relative path to an absolute path, refusing escapes.

        Uses ``removeprefix("./")`` (prefix strip) rather than ``lstrip("./")``
        (character-set strip). The latter silently coerces adversarial or
        confused inputs — ``../evil`` → ``evil``, ``.intent/foo`` →
        ``intent/foo`` — defeating both the ``is_relative_to`` escape-boundary
        check below and IntentGuard's tier-1 hard invariant on ``.intent/``
        writes.
        """
        rel_path = str(rel_path).removeprefix("./")
        candidate = (self.repo_path / rel_path).resolve()
        if not candidate.is_relative_to(self.repo_path):
            raise ValueError(f"Attempted to escape repository boundary: {rel_path}")
        return candidate

    def _guard_paths(
        self,
        rel_paths: list[str],
        impact: str | None = None,
        op_class: str = "write",
        target_classes: Mapping[str, str] | None = None,
    ) -> None:
        """Run a transaction's paths through IntentGuard, raising on rejection.

        Uses ``removeprefix("./")`` rather than ``lstrip("./")`` so that
        ``.intent/…`` paths retain their leading dot and correctly trigger
        IntentGuard's tier-1 hard invariant — ``lstrip("./")`` strips the
        leading ``.`` as a character-set member and silently redirects the
        write target.

        ADR-079 stage 1: this gateway also reads the calling capability
        (``current_capability()``) and the operational mode
        (``current_mode()``) once per transaction and derives a per-path
        op-class (D3), then passes all three to ``check_transaction`` so
        the chokepoint capability tier can emit advisory ``would-deny``
        log lines. The tier is log-only in stage 1 — this method's raise
        contract is unchanged.

        Raises:
            ConstitutionalViolationError: Subclass of ``ValueError``. Carries
                the full structured ``list[ViolationReport]`` so downstream
                handlers can persist ``rule_name`` / ``path`` /
                ``source_policy`` into ``ActionResult.data`` →
                ``proposal.execution_results``. Existing ``except ValueError``
                and ``except Exception`` handlers continue to catch this
                unchanged; ``str(exc)`` preserves the legacy
                ``"Blocked by IntentGuard: {msg}"`` one-liner verbatim.
        """
        cleaned: list[str] = [str(p).removeprefix("./") for p in rel_paths]
        op_classes = self._derive_op_classes(cleaned, op_class)
        calling_capability = current_capability()
        mode = current_mode()
        result = self._guard.check_transaction(
            cleaned,
            impact=impact,
            op_classes=op_classes,
            calling_capability=calling_capability,
            current_mode=mode,
            target_classes=target_classes,
        )
        if result.is_valid:
            return
        raise ConstitutionalViolationError(result.violations)

    def _derive_op_classes(
        self, cleaned_paths: list[str], op_class_hint: str
    ) -> dict[str, str]:
        """Resolve per-path op-class for the chokepoint tier (ADR-079 D3).

        For the ``"write"`` hint, stat each path: ``"modify"`` if the
        target exists, ``"create"`` otherwise. For ``"create"`` and
        ``"delete"`` hints the op-class is structurally fixed by the
        calling method's intent and is returned verbatim. The
        stat-before-decide carries a TOCTOU caveat (ADR-079 D3) that is
        benign under CORE's single-trust-boundary threat model.
        """
        if op_class_hint == "write":
            resolved: dict[str, str] = {}
            for p in cleaned_paths:
                abs_p = self.repo_path / p.rstrip("/")
                resolved[p] = "modify" if abs_p.exists() else "create"
            return resolved
        return {p: op_class_hint for p in cleaned_paths}

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
