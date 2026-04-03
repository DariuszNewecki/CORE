# src/will/agents/self_healing_agent.py

"""
Self-Healing Agent — Constitutional Sensing Worker.

Scans Python source files for missing # ID: tags on public symbols
and posts findings to the Blackboard for downstream processing by
ViolationRemediatorWorker.

Sensing only. Does not act. Does not execute. Does not write files.
Acting is delegated to ViolationRemediatorWorker + ProposalConsumerWorker.

Constitutional standing:
- Declaration:      .intent/workers/self_healing_agent.yaml
- Class:            sensing
- Phase:            audit
- Permitted tools:  none — pure AST, no LLM, no file writes
- Approval:         false — findings are observations only
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shared.ast_utility import find_symbol_id_and_def_line
from shared.logger import getLogger
from shared.workers.base import Worker


logger = getLogger(__name__)

# Subject prefix must match ViolationRemediatorWorker's claim filter
_FINDING_SUBJECT_PREFIX = "audit.violation"
_CHECK_ID = "linkage.assign_ids"


@dataclass
# ID: 31556ed7-ce3b-4b63-b649-4f06b611c8de
class IssueDetected:
    """Detected code quality issue in a single file."""

    filepath: str
    missing_count: int
    missing_symbols: list[str]


# ID: 9264b4f0-229a-42ac-8201-e58f01ad44cc
class SelfHealingAgent(Worker):
    """
    Sensing worker. Scans src/ for public symbols missing # ID: tags and
    posts one blackboard finding per affected file.

    Findings are consumed by ViolationRemediatorWorker which maps
    linkage.assign_ids to the assign_missing_ids action handler.
    """

    declaration_name = "self_healing_agent"

    def __init__(
        self,
        core_context: Any = None,
        declaration_name: str = "",
        **kwargs: Any,
    ) -> None:
        super().__init__(declaration_name=declaration_name or self.declaration_name)
        self._core_context = core_context

    # ID: 9e9ce8e4-2e80-46f4-85a1-235fef7a4282
    async def run(self) -> None:
        """
        One sensing cycle:
        1. Post heartbeat.
        2. Resolve scan root from CoreContext.
        3. Scan all src/**/*.py files for missing ID tags.
        4. Post one blackboard finding per affected file.
        5. Post completion report.
        """
        await self.post_heartbeat()

        repo_root = self._resolve_repo_root()
        if not repo_root:
            await self.post_report(
                subject="self_healing_agent.run.complete",
                payload={
                    "scanned": 0,
                    "findings_posted": 0,
                    "reason": "repo_root_unavailable",
                },
            )
            return

        src_root = repo_root / "src"
        if not src_root.exists():
            await self.post_report(
                subject="self_healing_agent.run.complete",
                payload={
                    "scanned": 0,
                    "findings_posted": 0,
                    "reason": "src_root_not_found",
                },
            )
            return

        python_files = list(src_root.rglob("*.py"))
        scanned = 0
        findings_posted = 0

        for filepath in python_files:
            scanned += 1
            issue = self._detect_issues(filepath)
            if issue is None:
                continue

            subject = (
                f"{_FINDING_SUBJECT_PREFIX}::{_CHECK_ID}::"
                f"{filepath.relative_to(repo_root)}"
            )
            await self.post_finding(
                subject=subject,
                payload={
                    "check_id": _CHECK_ID,
                    "file_path": str(filepath.relative_to(repo_root)),
                    "missing_count": issue.missing_count,
                    "missing_symbols": issue.missing_symbols[:10],
                    "message": (
                        f"Missing # ID: tags on {issue.missing_count} "
                        f"public symbol(s) in {filepath.relative_to(repo_root)}"
                    ),
                    "severity": "warning",
                },
            )
            findings_posted += 1
            logger.debug(
                "SelfHealingAgent: finding posted for %s (%d missing)",
                filepath.relative_to(repo_root),
                issue.missing_count,
            )

        await self.post_report(
            subject="self_healing_agent.run.complete",
            payload={
                "scanned": scanned,
                "findings_posted": findings_posted,
            },
        )
        logger.info(
            "SelfHealingAgent: cycle complete — scanned=%d findings_posted=%d",
            scanned,
            findings_posted,
        )

    def _resolve_repo_root(self) -> Path | None:
        """Resolve repository root from CoreContext or cwd."""
        if self._core_context is not None:
            try:
                return Path(self._core_context.git_service.repo_path).resolve()
            except Exception:
                pass
        # Fallback: walk up from cwd looking for .intent/
        candidate = Path.cwd()
        for _ in range(6):
            if (candidate / ".intent").exists():
                return candidate
            candidate = candidate.parent
        return None

    def _detect_issues(self, filepath: Path) -> IssueDetected | None:
        """
        Detect missing # ID: tags on public symbols in a single Python file.

        Returns IssueDetected if any symbols are missing tags, else None.
        Pure AST — no LLM, no file writes, no external calls.
        """
        if filepath.suffix != ".py":
            return None

        try:
            source = filepath.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(filepath))
        except (SyntaxError, OSError):
            return None

        lines = source.splitlines()
        missing: list[str] = []

        for node in ast.walk(tree):
            if not isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                continue
            is_dunder = node.name.startswith("__") and node.name.endswith("__")
            if node.name.startswith("_") or is_dunder:
                continue
            symbol_id, _ = find_symbol_id_and_def_line(lines, node)
            if symbol_id is None:
                missing.append(node.name)

        if not missing:
            return None

        return IssueDetected(
            filepath=str(filepath),
            missing_count=len(missing),
            missing_symbols=missing,
        )
