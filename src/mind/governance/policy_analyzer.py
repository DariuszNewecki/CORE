# src/mind/governance/policy_analyzer.py
"""
Constitutional Policy Analyzer.

Analyzes constitutional documents to extract atomic rules, detect duplicates,
find conflicts, and identify orphaned rules.
"""

from __future__ import annotations

import difflib
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import yaml

from shared.logger import getLogger


logger = getLogger(__name__)


@dataclass
# ID: 1858b8fd-3787-4ded-a2c7-eccd8e25cd81
class AtomicRule:
    """A single atomic governance rule extracted from constitution."""

    source_file: str
    principle_id: str
    rule_text: str
    scope: list[str]
    enforcement_method: str


@dataclass
# ID: f5d13215-1e3f-4ede-a987-0ff6dc605205
class PolicyAnalysisReport:
    """Complete analysis report for constitutional policies."""

    total_rules: int
    duplicate_rules: list[tuple[AtomicRule, AtomicRule]]
    conflicting_rules: list[tuple[AtomicRule, AtomicRule]]
    orphaned_rules: list[AtomicRule]
    rule_distribution: dict[str, int]


# ID: ea0cbf03-b399-4885-a86d-8b5582cec77e
class PolicyAnalyzer:
    """
    Analyzes constitutional policies for quality and consistency.

    Detects:
    - Duplicate rules (70%+ text similarity)
    - Conflicting rules (contradictory statements)
    - Orphaned rules (no code references)
    """

    def __init__(self, constitution_path: Path = Path(".intent/charter/constitution")):
        """
        Initialize policy analyzer.

        Args:
            constitution_path: Path to constitution directory
        """
        self.constitution_path = constitution_path
        self.rules: list[AtomicRule] = []

    # ID: defaa181-6b20-470c-8171-6ad9c2bcfdf6
    def analyze(self) -> PolicyAnalysisReport:
        """
        Analyze all constitutional policies.

        Returns:
            PolicyAnalysisReport with findings
        """
        logger.info("🔍 Analyzing constitutional policies...")

        self.rules.clear()
        self._extract_rules()

        duplicates = self._find_duplicates()
        conflicts = self._find_conflicts()
        orphaned = self._find_orphaned_rules()
        distribution = self._calculate_distribution()

        return PolicyAnalysisReport(
            total_rules=len(self.rules),
            duplicate_rules=duplicates,
            conflicting_rules=conflicts,
            orphaned_rules=orphaned,
            rule_distribution=distribution,
        )

    def _extract_rules(self):
        """Extract all atomic rules from constitutional documents."""
        for yaml_file in self.constitution_path.glob("*.yaml"):
            if "META" in yaml_file.name.upper():
                continue

            try:
                content = yaml.safe_load(yaml_file.read_text())
            except Exception as e:
                logger.warning("Failed to parse {yaml_file.name}: %s", e)
                continue

            if "principles" not in content:
                continue

            for principle_id, principle_data in content["principles"].items():
                if not isinstance(principle_data, dict):
                    continue

                statement = principle_data.get("statement", "")
                scope = principle_data.get("scope", [])
                enforcement = principle_data.get("enforcement", {})
                method = enforcement.get("method", "unknown")

                rule = AtomicRule(
                    source_file=yaml_file.name,
                    principle_id=principle_id,
                    rule_text=statement,
                    scope=scope,
                    enforcement_method=method,
                )
                self.rules.append(rule)

    def _find_duplicates(self) -> list[tuple[AtomicRule, AtomicRule]]:
        """Find duplicate rules (70%+ text similarity)."""
        duplicates = []

        for i, rule1 in enumerate(self.rules):
            for rule2 in self.rules[i + 1 :]:
                similarity = self._text_similarity(rule1.rule_text, rule2.rule_text)

                if similarity > 0.7:
                    duplicates.append((rule1, rule2))

        return duplicates

    def _find_conflicts(self) -> list[tuple[AtomicRule, AtomicRule]]:
        """Find conflicting rules (contradictory statements)."""
        conflicts = []

        conflict_keywords = [
            ("must", "must not"),
            ("required", "prohibited"),
            ("allowed", "blocked"),
            ("autonomous", "human approval"),
        ]

        for i, rule1 in enumerate(self.rules):
            for rule2 in self.rules[i + 1 :]:
                if self._are_conflicting(rule1, rule2, conflict_keywords):
                    conflicts.append((rule1, rule2))

        return conflicts

    def _find_orphaned_rules(self) -> list[AtomicRule]:
        """Find rules with no code references."""
        orphaned = []

        codebase = self._load_codebase()

        for rule in self.rules:
            if not self._has_code_reference(rule, codebase):
                orphaned.append(rule)

        return orphaned

    def _calculate_distribution(self) -> dict[str, int]:
        """Calculate rule distribution by enforcement method."""
        distribution = defaultdict(int)

        for rule in self.rules:
            distribution[rule.enforcement_method] += 1

        return dict(distribution)

    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity ratio (0.0 to 1.0)."""
        return difflib.SequenceMatcher(None, text1, text2).ratio()

    def _are_conflicting(
        self, rule1: AtomicRule, rule2: AtomicRule, keywords: list[tuple[str, str]]
    ) -> bool:
        """Check if two rules are conflicting."""
        text1 = rule1.rule_text.lower()
        text2 = rule2.rule_text.lower()

        scope_overlap = set(rule1.scope) & set(rule2.scope)
        if not scope_overlap:
            return False

        for positive, negative in keywords:
            if positive in text1 and negative in text2:
                return True
            if negative in text1 and positive in text2:
                return True

        return False

    def _load_codebase(self) -> str:
        """Load entire codebase as text for reference checking."""
        all_code = ""
        src_path = Path("src")

        if not src_path.exists():
            return all_code

        for py_file in src_path.rglob("*.py"):
            try:
                all_code += py_file.read_text()
            except Exception:
                pass

        return all_code

    def _has_code_reference(self, rule: AtomicRule, codebase: str) -> bool:
        """Check if rule has any code reference."""
        keywords = rule.principle_id.split("_")
        keywords.extend(rule.rule_text.lower().split())

        unique_keywords = [k for k in keywords if len(k) > 4 and k.isalpha()]

        if not unique_keywords:
            return True

        for keyword in unique_keywords[:3]:
            if keyword in codebase.lower():
                return True

        return False


# ID: cc48e198-1932-499b-b281-738b3da38dc0
def format_analysis_report(report: PolicyAnalysisReport) -> str:
    """
    Format analysis report for console output.

    Args:
        report: PolicyAnalysisReport to format

    Returns:
        Formatted string ready for printing
    """
    lines = []
    lines.append("=" * 80)
    lines.append("CONSTITUTIONAL POLICY ANALYSIS REPORT")
    lines.append("=" * 80)
    lines.append("")
    lines.append(f"Total Rules: {report.total_rules}")
    lines.append(f"Duplicate Rules: {len(report.duplicate_rules)}")
    lines.append(f"Conflicting Rules: {len(report.conflicting_rules)}")
    lines.append(f"Orphaned Rules: {len(report.orphaned_rules)}")
    lines.append("")

    lines.append("Rule Distribution by Enforcement Method:")
    lines.append("-" * 80)
    for method, count in sorted(report.rule_distribution.items()):
        lines.append(f"  {method}: {count}")
    lines.append("")

    if report.duplicate_rules:
        lines.append("⚠️  DUPLICATE RULES")
        lines.append("-" * 80)
        for rule1, rule2 in report.duplicate_rules:
            lines.append(f"\n{rule1.source_file}#{rule1.principle_id}")
            lines.append(f"  ↔ {rule2.source_file}#{rule2.principle_id}")
        lines.append("")

    if report.conflicting_rules:
        lines.append("❌ CONFLICTING RULES")
        lines.append("-" * 80)
        for rule1, rule2 in report.conflicting_rules:
            lines.append(f"\n{rule1.source_file}#{rule1.principle_id}")
            lines.append(f"  ⚡ {rule2.source_file}#{rule2.principle_id}")
        lines.append("")

    lines.append("=" * 80)
    return "\n".join(lines)


if __name__ == "__main__":
    analyzer = PolicyAnalyzer()
    report = analyzer.analyze()
    logger.info(format_analysis_report(report))
