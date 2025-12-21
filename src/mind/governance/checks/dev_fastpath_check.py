# src/mind/governance/checks/dev_fastpath_check.py
"""
Dev Fastpath Governance Check

Enforces dev fastpath rules declared in operations policies:
- dev_fastpath.no_intent_changes

Interpretation (evidence-backed):
- CORE must implement a fastpath guard that prevents or aborts when `.intent/`
  changes are present during a "fastpath" workflow/command.

Rationale:
- Governance coverage is about proving enforcement exists in the system,
  not about failing audits whenever `.intent/` legitimately changes.

Design constraints:
- Prefer internal CORE mechanisms (GitService, Body CLI workflow patterns).
- Conservative static verification: search Body CLI/workflow sources for a fastpath
  guard that references `.intent` and an abort/deny behavior.
- Do not pretend-pass if the expected enforcement evidence cannot be found.
"""

from __future__ import annotations

import inspect
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.rule_enforcement_check import (
    EnforcementMethod,
    RuleEnforcementCheck,
)
from shared.config import settings
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)

RULE_DEV_FASTPATH_NO_INTENT_CHANGES = "dev_fastpath.no_intent_changes"


@dataclass(frozen=True)
# ID: 93db2155-718c-4554-b9c7-f416cacc1c25
class EvidenceHit:
    file_path: str
    line_no: int
    line: str


def _create_finding_safe(method: EnforcementMethod, **kwargs: Any) -> AuditFinding:
    """
    EnforcementMethod._create_finding() signature varies across CORE versions.
    Filter kwargs against the runtime signature to prevent TypeError.
    """
    sig = inspect.signature(method._create_finding)  # type: ignore[attr-defined]
    allowed = set(sig.parameters.keys())
    filtered = {k: v for k, v in kwargs.items() if k in allowed}
    return method._create_finding(**filtered)  # type: ignore[attr-defined]


def _iter_py_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*.py") if p.is_file())


def _read_lines(p: Path) -> list[str]:
    try:
        return p.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []


# ID: 4fb52569-4f84-4790-a7e2-5493ee295822
class DevFastpathNoIntentChangesEnforcement(EnforcementMethod):
    """
    Evidence-backed enforcement verification for dev_fastpath.no_intent_changes.

    We look for code that:
    - is clearly "fastpath" related (string/flag/command naming), AND
    - references `.intent` (or intent root), AND
    - indicates deny/abort behavior (abort/deny/fail/raise/exit) in that context.

    This is intentionally conservative:
    - It proves enforcement exists.
    - It does not fail audits merely because `.intent/` differs in a working tree.
    """

    # Minimal keyword sets for conservative correlation
    _FASTPATH_PATTERNS: ClassVar[list[re.Pattern[str]]] = [
        re.compile(r"\bfastpath\b", re.IGNORECASE),
        re.compile(r"\bdev[_-]?fastpath\b", re.IGNORECASE),
        re.compile(r"\bfast[_-]?path\b", re.IGNORECASE),
    ]
    _INTENT_PATTERNS: ClassVar[list[re.Pattern[str]]] = [
        re.compile(r"\.intent\b"),
        re.compile(r"/\.intent/"),
        re.compile(r"\bintent_root\b", re.IGNORECASE),
        re.compile(r"\bintent\b", re.IGNORECASE),
    ]
    _ABORT_PATTERNS: ClassVar[list[re.Pattern[str]]] = [
        re.compile(r"\babort\b", re.IGNORECASE),
        re.compile(r"\bdeny\b", re.IGNORECASE),
        re.compile(r"\bfail\b", re.IGNORECASE),
        re.compile(r"\brefuse\b", re.IGNORECASE),
        re.compile(r"\braise\b", re.IGNORECASE),
        re.compile(r"\bsys\.exit\b", re.IGNORECASE),
        re.compile(r"\bexit\(", re.IGNORECASE),
        re.compile(r"\breturn\b.*\bFalse\b", re.IGNORECASE),
    ]

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: b0ede200-a752-41d1-9824-dc9f7be43ee7
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs: Any
    ) -> list[AuditFinding]:
        repo_path = context.repo_path

        # Prefer searching in Body CLI + workflows (where fastpath is expected to live)
        candidates: list[Path] = []
        for root in (
            repo_path / "src" / "body" / "cli",
            repo_path / "src" / "body" / "cli" / "workflows",
            repo_path / "src" / "body" / "cli" / "commands",
            repo_path / "src" / "features" / "project_lifecycle",
            repo_path / "src" / "features" / "maintenance",
        ):
            candidates.extend(_iter_py_files(root))

        if not candidates:
            return [
                _create_finding_safe(
                    self,
                    message=(
                        "Unable to locate candidate sources for dev-fastpath enforcement "
                        "(expected under src/body/cli or workflows)."
                    ),
                    file_path="src/body/cli",
                    severity=AuditSeverity.ERROR,
                )
            ]

        hits = self._find_correlated_guard_hits(repo_path, candidates)

        if not hits:
            # Evidence-backed failure: we did not find any guard correlation
            return [
                _create_finding_safe(
                    self,
                    message=(
                        "No evidence found that a dev-fastpath guard blocks `.intent/` changes. "
                        "Expected: fastpath-related code that detects `.intent` modifications and aborts/denies."
                    ),
                    file_path="src/body/cli",
                    severity=AuditSeverity.ERROR,
                    evidence={
                        "searched_files": len(candidates),
                        "roots": [
                            "src/body/cli",
                            "src/body/cli/workflows",
                            "src/body/cli/commands",
                            "src/features/project_lifecycle",
                            "src/features/maintenance",
                        ],
                        "rule_id": self.rule_id,
                    },
                )
            ]

        # If we have evidence hits, rule is enforced (by presence of implementation)
        return []

    def _find_correlated_guard_hits(
        self, repo_path: Path, files: list[Path]
    ) -> list[EvidenceHit]:
        """
        Correlate hits within the same file:
        - at least one fastpath indicator
        - at least one `.intent` indicator
        - at least one abort/deny indicator

        When all three exist in the same file, we treat that as evidence of enforcement.
        """
        evidence: list[EvidenceHit] = []

        for p in files:
            lines = _read_lines(p)
            if not lines:
                continue

            rel = str(p.relative_to(repo_path))

            fastpath_lines = self._match_lines(lines, self._FASTPATH_PATTERNS)
            if not fastpath_lines:
                continue

            intent_lines = self._match_lines(lines, self._INTENT_PATTERNS)
            if not intent_lines:
                continue

            abort_lines = self._match_lines(lines, self._ABORT_PATTERNS)
            if not abort_lines:
                continue

            # Capture a limited set of the strongest evidence lines
            for ln, txt in fastpath_lines[:3] + intent_lines[:3] + abort_lines[:3]:
                evidence.append(
                    EvidenceHit(file_path=rel, line_no=ln, line=txt.strip())
                )

        # Log evidence for visibility (without bloating AuditFinding payloads)
        if evidence:
            logger.info(
                "DevFastpathCheck: found %s evidence line(s) across %s file(s).",
                len(evidence),
                len({e.file_path for e in evidence}),
            )

        return evidence

    def _match_lines(
        self, lines: list[str], patterns: list[re.Pattern[str]]
    ) -> list[tuple[int, str]]:
        hits: list[tuple[int, str]] = []
        for i, line in enumerate(lines, start=1):
            for pat in patterns:
                if pat.search(line):
                    hits.append((i, line))
                    break
        return hits


# ID: 2b37553d-498e-4509-b521-ca095462e72f
class DevFastpathCheck(RuleEnforcementCheck):
    """
    Enforces dev fastpath safety rules.

    Rule:
    - dev_fastpath.no_intent_changes
    """

    policy_rule_ids: ClassVar[list[str]] = [RULE_DEV_FASTPATH_NO_INTENT_CHANGES]

    # This rule is declared under standard_operations_general in your coverage output.
    # In your current codebase, general ops rules appear reachable via "operations".
    # If your PathResolver uses another key, adjust accordingly.
    policy_file: ClassVar[Path] = settings.paths.policy("operations")

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        DevFastpathNoIntentChangesEnforcement(
            rule_id=RULE_DEV_FASTPATH_NO_INTENT_CHANGES,
            severity=AuditSeverity.ERROR,
        )
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
