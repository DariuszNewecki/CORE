# src/mind/governance/fast_verdict.py

"""The fast verdict: producer feedback on a change, honest about its scope (ADR-168 D4.3).

An assistant consults this before acting; it is not the authoritative audit.
The full audit (the commit hook, CI) stays authoritative and unchanged
(ADR-168 third review: fast producer feedback stays distinct from
authoritative repository enforcement).

What it does:

- **Scope** is the change: every path that differs from HEAD, untracked files
  included, or an explicit file list.
- **Per-file rules** run on the files in scope, through the same stateless
  audit the offline gate uses, so the rules and their findings are identical.
- **Everything not evaluated is named**: whole-repository (context-level)
  rules, which a file-scoped run cannot evaluate; rules that need services;
  rules that failed; checks that reported themselves unavailable.

Vocabulary: ``BLOCKED`` (at least one blocking violation in scope),
``CLEAR_IN_SCOPE`` (none among the rules evaluated, with the not-evaluated
list alongside), ``NO_CHANGES`` (nothing in scope). It never says PASS: PASS is
reserved for the authoritative full audit, so partial feedback cannot be
mistaken for it (#952, #956).

Read-only: no writes, no database, no LLM.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mind.governance.stateless_audit import run_stateless_audit
from shared.infrastructure.git_service import GitService
from shared.infrastructure.intent.errors import GovernanceError
from shared.infrastructure.intent.intent_repository import IntentRepository
from shared.logger import getLogger
from shared.models.audit_rendering import NOT_EVALUATED_FINDING_TYPES


logger = getLogger(__name__)

BLOCKED = "BLOCKED"
CLEAR_IN_SCOPE = "CLEAR_IN_SCOPE"
NO_CHANGES = "NO_CHANGES"

_BLOCKING = {"block", "blocking"}
_AUTHORITY_NOTE = (
    "Producer feedback, not the authoritative verdict. PASS is given only by the "
    "full audit (the commit hook and CI), which evaluates every rule."
)


# ID: 0ce6eb98-da64-44f3-a8dd-37e4d5dbfeda
async def run_fast_verdict(
    intent_repo: IntentRepository,
    repo_path: Path,
    *,
    files: list[str] | None = None,
) -> dict[str, Any]:
    """Judge the change in ``repo_path`` (or ``files``) against the per-file
    rules, and name every rule this run did not evaluate."""
    repo_path = Path(repo_path).resolve()
    changed = list(files) if files is not None else _changed_paths(repo_path)
    in_scope = sorted(p for p in changed if (repo_path / p).is_file())
    removed = sorted(p for p in changed if not (repo_path / p).exists())

    if not in_scope:
        return {
            "verdict": NO_CHANGES,
            "authoritative": False,
            "note": _AUTHORITY_NOTE,
            "scope": {"files": [], "removed": removed},
            "blocking": [],
            "not_evaluated": {},
        }

    result = await run_stateless_audit(intent_repo, repo_path, files=in_scope)
    findings = result.get("findings") or []
    stats = result.get("stats") or {}

    blocking = [
        _finding_summary(f)
        for f in findings
        if str(f.get("severity", "")).lower() in _BLOCKING and not _not_evaluated(f)
    ]
    unavailable = sorted(
        {
            str(f.get("check_id"))
            for f in findings
            if _not_evaluated(f) and f.get("check_id")
        }
    )
    not_evaluated = {
        "context_level": [
            _with_enforcement(intent_repo, rule_id)
            for rule_id in stats.get("skipped_context_level_ids") or []
        ],
        "needs_services": [
            {"rule_id": s.get("rule_id"), "enforcement": s.get("enforcement")}
            for s in result.get("skipped_rules") or []
        ],
        "failed": list(stats.get("failed_rule_ids") or []),
        "unavailable": unavailable,
    }
    law = result.get("law_state") or {}

    return {
        "verdict": BLOCKED if blocking else CLEAR_IN_SCOPE,
        "authoritative": False,
        "note": _AUTHORITY_NOTE,
        "scope": {"files": in_scope, "removed": removed},
        "blocking": blocking,
        "not_evaluated": not_evaluated,
        "law": {
            "relationship": law.get("relationship"),
            "drift_paths": law.get("drift_paths") or [],
        },
        "error": result.get("error"),
    }


def _changed_paths(repo_path: Path) -> list[str]:
    """Paths that differ from HEAD, untracked included. A repository with no
    commit yet has every file untracked, which ``status`` reports as such."""
    git = GitService(repo_path)
    try:
        return git.changed_paths(".")
    except RuntimeError as exc:
        logger.debug("fast verdict: change scope unavailable: %s", exc)
        return []


def _not_evaluated(finding: dict[str, Any]) -> bool:
    context = finding.get("context") or {}
    return context.get("finding_type") in NOT_EVALUATED_FINDING_TYPES


def _finding_summary(finding: dict[str, Any]) -> dict[str, Any]:
    return {
        "rule_id": finding.get("check_id"),
        "file": finding.get("file_path"),
        "line": finding.get("line_number"),
        "message": finding.get("message"),
    }


def _with_enforcement(intent_repo: IntentRepository, rule_id: str) -> dict[str, Any]:
    try:
        enforcement = intent_repo.get_rule(rule_id).content.get("enforcement")
    except GovernanceError:
        enforcement = None
    return {"rule_id": rule_id, "enforcement": enforcement}
