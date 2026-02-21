# src/will/self_healing/remediation_pattern_matcher.py
"""Remediation Pattern Matcher.

Matches audit findings to known auto-fix patterns and filters by risk mode.
Single responsibility: pattern matching only, no I/O, no execution.
"""

from __future__ import annotations

from body.self_healing.remediation_models import (
    MatchedPattern,
    RemediationMode,
)
from shared.logger import getLogger
from shared.models import AuditFinding


logger = getLogger(__name__)


# ID: 3a1e1798-e24c-4712-bdfe-c162ddfa0431
class RemediationPatternMatcher:
    """Matches audit findings to deterministic fix patterns."""

    def __init__(self) -> None:
        """Load available fix patterns on construction."""
        self.patterns = self._load_fix_patterns()
        logger.info(
            "RemediationPatternMatcher initialized with %d patterns",
            len(self.patterns),
        )

    def _load_fix_patterns(self) -> list:
        """Load available fix patterns.

        Returns:
            List of AutoFixablePattern objects.
        """
        from body.autonomy.audit_analyzer import AutoFixablePattern

        return [
            AutoFixablePattern(
                check_id_pattern="style.import_order",
                action_handler="sort_imports",
                confidence=0.90,
                risk_level="low",
                description="Sort imports according to PEP 8",
            ),
        ]

    # ID: 9a06afdb-92a9-443a-a55e-f88cee9dd49f
    def match(
        self,
        findings: list[AuditFinding],
        mode: RemediationMode,
        target_pattern: str | None = None,
    ) -> tuple[list[MatchedPattern], list[AuditFinding]]:
        """Match findings to patterns, filtered by mode and optional target.

        Args:
            findings: Audit findings to match.
            mode: Risk tolerance for automatic fixes.
            target_pattern: If provided, only match this pattern.

        Returns:
            Tuple of (matched, unmatched).
        """
        matched: list[MatchedPattern] = []
        unmatched: list[AuditFinding] = []

        for finding in findings:
            pattern = self._find_matching_pattern(finding.check_id, target_pattern)

            if pattern is None or not self._is_allowed(pattern, mode):
                unmatched.append(finding)
                continue

            matched.append(
                MatchedPattern(
                    finding=finding,
                    pattern=pattern,
                    confidence=pattern.confidence,
                    risk_level=pattern.risk_level,
                )
            )

        return matched, unmatched

    def _find_matching_pattern(self, check_id: str, target_pattern: str | None):
        """Find pattern matching this check_id.

        Returns:
            AutoFixablePattern or None.
        """
        for pattern in self.patterns:
            if pattern.check_id_pattern == check_id:
                if target_pattern is None or pattern.check_id_pattern == target_pattern:
                    return pattern

            if pattern.check_id_pattern.endswith("*"):
                prefix = pattern.check_id_pattern[:-1]
                if check_id.startswith(prefix):
                    if target_pattern is None or check_id.startswith(
                        target_pattern.replace("*", "")
                    ):
                        return pattern

        return None

    def _is_allowed(self, pattern, mode: RemediationMode) -> bool:
        """Check if pattern risk level is permitted under current mode.

        Returns:
            True if the pattern is allowed.
        """
        if mode == RemediationMode.SAFE_ONLY:
            return pattern.confidence >= 0.85 and pattern.risk_level == "low"
        if mode == RemediationMode.MEDIUM_RISK:
            return pattern.confidence >= 0.70 and pattern.risk_level in (
                "low",
                "medium",
            )
        if mode == RemediationMode.ALL_DETERMINISTIC:
            return True
        return False
