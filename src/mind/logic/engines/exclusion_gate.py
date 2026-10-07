# src/mind/logic/engines/exclusion_gate.py

"""
Exclusion Gate Engine — every exclude entry must still exempt something.

Hosts one context-level check, ``excludes_exempt_something``: each entry in
an enforcement mapping's ``scope.excludes`` is an exemption from that rule,
and an exemption that exempts nothing is not inert. A glob written for test
files that matches production modules instead, or an entry left behind after
its file was routed onto the sanctioned surface, silently widens the rule's
blind spot for whatever lands under it next (2026-10-07: 126 of 204 entries
were dead; ``src/**/test_*.py`` entries were exempting production modules
named ``test_*``).

An entry is dead when any of these holds:

- it matches no file in the repository;
- every file it matches lies outside the rule's own ``applies_to``;
- the rule's engine is deterministic per-file (``_PROBED_ENGINES``) and none
  of the in-scope files it matches violates the rule when checked without
  the exemption.

Rules on context-level or non-deterministic engines are judged on the first
two conditions only — the third would need the engine's whole-corpus pass or
an LLM call. That is the coverage ceiling, not a pass.

Uses the dispatcher's own rule set (``extract_executable_rules``) and glob
matcher (``_include_matches``), so this check and the audit cannot disagree
about what an entry covers.

CONSTITUTIONAL ALIGNMENT:
- Read-only; rules and mappings come from the AuditorContext.
- Deterministic verdict (ADR-113 PROVEN); one finding per dead entry.
"""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity

from .base import BaseEngine, EngineResult, EvidenceClass


if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext
    from mind.governance.executable_rule import ExecutableRule

logger = getLogger(__name__)

CORE_ROLE = "facade"  # ADR-095 D3

_CHECK = "excludes_exempt_something"
_CHECK_ID = "architecture.intent.excludes_exempt_something"
_MAPPINGS_REL = ".intent/enforcement/mappings"
# Per-file engines whose verify() is a pure function of file content and
# params: probing an excluded file with them is cheap and decisive.
_PROBED_ENGINES = frozenset({"ast_gate", "regex_gate", "glob_gate"})

NO_FILE = "matches no file in the repository"
OUT_OF_SCOPE = "matches only files outside the rule's applies_to"
EXEMPTS_NOTHING = "covers files that would not violate the rule anyway"

# (rule, absolute file path) -> True if the file violates, False if it is
# clean, None if the probe could not decide.
Probe = Callable[["ExecutableRule", Path], Awaitable[bool | None]]


@dataclass(frozen=True)
# ID: da22d886-f9ed-4db8-b6d4-ba1faea1ab40
class DeadExclude:
    """One exclude entry that exempts nothing, and why."""

    rule_id: str
    entry: str
    reason: str


# ID: 2ccf0907-07b6-4ae0-9d8d-28b22343c31a
class ExclusionGateEngine(BaseEngine):
    """Context-level auditor: exclude entries must still exempt something."""

    engine_id = "exclusion_gate"
    evidence_class = EvidenceClass.PROVEN

    @classmethod
    # ID: ee99cc3f-b3fc-4a15-999c-3681843427d8
    def is_context_level_for(cls, check_type: str | None) -> bool:
        """The single check sweeps every mapping, not one file."""
        return check_type == _CHECK

    # ID: fa7e10ec-f50a-4fb3-94b6-5ad3e804c08f
    async def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        """Per-file dispatch is a mis-mapping for this engine; say so."""
        return EngineResult(
            ok=False,
            message=(
                f"exclusion_gate: check_type {params.get('check_type')!r} is "
                "context-level; dispatch via verify_context, not verify"
            ),
            violations=[],
            engine_id=self.engine_id,
        )

    # ID: 527001de-a804-4198-ae26-fa793ee8ddd0
    async def verify_context(
        self, context: AuditorContext, params: dict[str, Any]
    ) -> list[AuditFinding]:
        """One finding per dead exclude entry across every mapping."""
        if params.get("check_type") != _CHECK:
            return [
                AuditFinding(
                    check_id="exclusion_gate.unknown_check_type",
                    severity=AuditSeverity.BLOCK,
                    message=(
                        f"exclusion_gate: unknown check_type "
                        f"{params.get('check_type')!r}; valid: {_CHECK!r}"
                    ),
                    file_path="none",
                )
            ]

        from mind.governance.rule_extractor import extract_executable_rules
        from mind.logic.engines.registry import EngineRegistry

        repo_root = Path(context.repo_path)
        rules = [
            r
            for r in extract_executable_rules(
                context.policies, context.enforcement_loader
            )
            if r.rule_id != _CHECK_ID
        ]

        async def _probe(rule: ExecutableRule, path: Path) -> bool | None:
            try:
                result = await EngineRegistry.get(rule.engine).verify(path, rule.params)
            except Exception as exc:
                logger.debug(
                    "exclusion_gate: probe of %s on %s failed: %s",
                    rule.rule_id,
                    path,
                    exc,
                )
                return None
            return bool(result.violations) or not result.ok

        dead = await find_dead_excludes(
            rules, _repo_files(repo_root), repo_root, _probe
        )
        return [
            AuditFinding(
                check_id=_CHECK_ID,
                severity=AuditSeverity.MEDIUM,
                message=(
                    f"{d.rule_id}: exclude entry {d.entry!r} {d.reason}. "
                    "An exemption that exempts nothing widens the rule's blind "
                    "spot for whatever lands under it next — remove the entry."
                ),
                file_path=_MAPPINGS_REL,
                context={"rule_id": d.rule_id, "entry": d.entry, "reason": d.reason},
            )
            for d in dead
        ]


# ID: a6f9a952-809e-4fa5-90a9-ff3774300c1a
async def find_dead_excludes(
    rules: Iterable[ExecutableRule],
    repo_files: Sequence[str],
    repo_root: Path,
    probe: Probe,
) -> list[DeadExclude]:
    """Judge every exclude entry of every rule (public for tests).

    ``repo_files`` are repo-relative POSIX paths. ``probe`` is consulted only
    for rules on ``_PROBED_ENGINES`` that are not context-level; an entry is
    reported as exempting nothing only when every probe returned False — a
    probe that could not decide (None) keeps the entry.
    """
    from mind.governance.audit_context import _include_matches

    dead: list[DeadExclude] = []
    for rule in rules:
        scope = rule.scope or []
        for entry in rule.exclusions or []:
            matched = [f for f in repo_files if _include_matches(f, entry)]
            if not matched:
                dead.append(DeadExclude(rule.rule_id, entry, NO_FILE))
                continue
            in_scope = [
                f for f in matched if any(_include_matches(f, s) for s in scope)
            ]
            if not in_scope:
                dead.append(DeadExclude(rule.rule_id, entry, OUT_OF_SCOPE))
                continue
            if rule.is_context_level or rule.engine not in _PROBED_ENGINES:
                continue
            if await _none_violate(rule, in_scope, repo_root, probe):
                dead.append(DeadExclude(rule.rule_id, entry, EXEMPTS_NOTHING))
    return dead


async def _none_violate(
    rule: ExecutableRule, files: Sequence[str], repo_root: Path, probe: Probe
) -> bool:
    """True only if every file was probed and found clean."""
    for rel in files:
        verdict = await probe(rule, repo_root / rel)
        if verdict is not False:
            return False
    return True


def _repo_files(repo_root: Path) -> list[str]:
    """Every file under ``repo_root`` (repo-relative POSIX), structural dirs pruned.

    Same prune set as the audit walker (ADR-076 D5); deliberately no
    rule-scope filter, since an exclude may name files no rule walks.
    """
    from mind.governance.audit_context import _STRUCTURAL_DIR_PARTS

    files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = [d for d in dirnames if d not in _STRUCTURAL_DIR_PARTS]
        rel_dir = Path(dirpath).relative_to(repo_root)
        files.extend((rel_dir / name).as_posix() for name in filenames)
    return files
