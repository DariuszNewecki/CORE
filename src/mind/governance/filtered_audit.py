# src/mind/governance/filtered_audit.py
"""
Filtered Constitutional Audit - Run specific rules or policies.

Enables focused remediation by allowing execution of:
- Single rules: --rule linkage.capability.unassigned
- Single policies: --policy standard_code_linkage
- Multiple rules: --rule rule1 --rule rule2
- Rule patterns: --rule-pattern "linkage.*"

This uses the existing dynamic rule execution engine but with filtering.
"""

from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING

from shared.logger import getLogger
from shared.models.audit_models import AuditFinding, AuditSeverity, EvidenceClass


if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext
    from mind.governance.executable_rule import ExecutableRule

logger = getLogger(__name__)


# ID: f8a9b7c6-5d4e-3f2a-1b0c-9d8e7f6a5b4c
class RuleFilter:
    """Filters rules based on user-specified criteria."""

    def __init__(
        self,
        rule_ids: list[str] | None = None,
        policy_ids: list[str] | None = None,
        rule_patterns: list[str] | None = None,
    ):
        self.rule_ids = set(rule_ids or [])
        self.policy_ids = set(policy_ids or [])
        self.rule_patterns = [re.compile(p) for p in (rule_patterns or [])]

    # ID: ee2ebac1-0f32-45ce-ab11-ed0c4106ab20
    def matches(self, rule: ExecutableRule) -> bool:
        """Check if rule matches filter criteria."""
        # If no filters specified, match everything
        if not self.rule_ids and not self.policy_ids and not self.rule_patterns:
            return True

        # Check exact rule ID match
        if self.rule_ids and rule.rule_id in self.rule_ids:
            return True

        # Check policy ID match
        if self.policy_ids and rule.policy_id in self.policy_ids:
            return True

        # Check pattern match
        for pattern in self.rule_patterns:
            if pattern.match(rule.rule_id):
                return True

        return False


# ID: 5872afdb-b32c-48d0-b280-e2403aca3b64
def normalize_file_filter(
    files: list[str] | None,
    repo_path,  # Path-like; quoted to avoid an Iterable hop.
) -> frozenset[str] | None:
    """
    Normalize a CLI --files list to a frozenset of repo-relative POSIX
    paths suitable for execute_rule's file_filter parameter.

    Accepts repo-relative ('src/foo.py'), './'-prefixed
    ('./src/foo.py'), and absolute paths. Paths outside the repo are
    rejected loudly — silently dropping them would mask user error and
    produce a confusing empty audit.

    Returns None when the input is empty/None — the audit runs without
    a file filter (full scope).
    """
    from pathlib import Path

    if not files:
        return None

    repo_root = Path(repo_path).resolve()
    normalized: set[str] = set()
    for raw in files:
        # Always resolve before validating. pathlib's `/` operator drops
        # the LHS when the RHS is absolute, so a single expression handles
        # both repo-relative and absolute inputs. Resolving first
        # normalizes `..` segments and follows symlinks, so the
        # `relative_to(repo_root)` check below is a real boundary, not a
        # lexical one — `/<repo>/x/../../etc/passwd` and `/<repo>/symlink`
        # pointing outside both reject. Closes CodeQL py/path-injection.
        absolute = (repo_root / Path(raw)).resolve()
        try:
            rel = absolute.relative_to(repo_root)
        except ValueError as exc:
            raise ValueError(
                f"--files path {raw!r} is outside the repository root "
                f"{repo_root}: {exc}"
            ) from exc
        normalized.add(str(rel).replace("\\", "/"))

    return frozenset(normalized)


# ID: d5383238-b6d4-48d9-880b-8f48df47d57e
async def run_filtered_audit(
    context: AuditorContext,
    *,
    rule_ids: list[str] | None = None,
    policy_ids: list[str] | None = None,
    rule_patterns: list[str] | None = None,
    executed_rule_ids: set[str] | None = None,
    files: list[str] | None = None,
) -> tuple[list, set[str], dict[str, int]]:
    """
    Execute filtered subset of constitutional rules.

    Args:
        context: AuditorContext with repo and policy info
        rule_ids: Specific rule IDs to execute
        policy_ids: Execute all rules from these policies
        rule_patterns: Regex patterns for rule IDs
        executed_rule_ids: Set to track executed rules (optional)
        files: Optional list of file paths (repo-relative, ./-prefixed,
            or absolute) scoping per-file rules. Context-level rules
            skip gracefully when this is set — they cannot be
            meaningfully scoped to a file list. Closes #279.

    Returns:
        tuple(findings, executed_rules, stats)
    """
    from mind.governance.rule_executor import execute_rule
    from mind.governance.rule_extractor import extract_executable_rules

    if executed_rule_ids is None:
        executed_rule_ids = set()

    # ADR-039: rebuild the filesystem scan once per audit run so files
    # committed since the last cycle are visible to every rule.
    context.reload_governance()
    context.invalidate_file_cache()

    # ADR-044: TTL sweep at audit start. Idempotent per AuditorContext.
    await context.sweep_llm_gate_cache()

    file_filter = normalize_file_filter(files, context.repo_path)

    # Extract all executable rules from policies
    all_rules = extract_executable_rules(context.policies, context.enforcement_loader)

    # Create filter
    rule_filter = RuleFilter(
        rule_ids=rule_ids,
        policy_ids=policy_ids,
        rule_patterns=rule_patterns,
    )

    # Filter rules
    filtered_rules = [r for r in all_rules if rule_filter.matches(r)]

    if not filtered_rules:
        logger.warning(
            "No rules matched filter criteria: rule_ids=%s, policy_ids=%s, patterns=%s",
            rule_ids,
            policy_ids,
            rule_patterns,
        )
        return (
            [],
            executed_rule_ids,
            {
                "total_rules": len(all_rules),
                "filtered_rules": 0,
                "executed_rules": 0,
                "total_findings": 0,
                "skipped_context_level": 0,
            },
        )

    logger.info(
        "Filtered audit: %d rules selected (out of %d total)%s",
        len(filtered_rules),
        len(all_rules),
        (
            f" — file filter active ({len(file_filter)} file(s))"
            if file_filter is not None
            else ""
        ),
    )

    # Execute filtered rules. ADR-043 D3: accumulator carries
    # AuditFinding objects through the loop so requires_findings_from
    # narrowing can read check_id and file_path off them; conversion to
    # dicts is deferred to the return statement so the external contract
    # is unchanged. Rules are topologically sorted by
    # extract_executable_rules.
    all_findings: list[AuditFinding] = []
    failed_rules = []
    skipped_context_level: list[str] = []

    for rule in filtered_rules:
        # ADR-081 Step 2b — cooperative yield at the per-rule boundary so
        # heavy audit cycles can reach a cancellation point between rules.
        # execute_rule itself is sync-dominated (AST walks per file); this
        # yield bounds the worst case to one rule's worth of synchronous
        # work between SIGTERM and Worker.start()'s `finally` block running.
        # Per-engine inner yields are deferred pending Step 0 evidence
        # naming which engines dominate the loop-hold.
        await asyncio.sleep(0)

        # Track skipped-context-level explicitly for stats / operator
        # transparency. execute_rule logs the skip; we count it here.
        if file_filter is not None and rule.is_context_level:
            skipped_context_level.append(rule.rule_id)

        try:
            findings = await execute_rule(
                rule,
                context,
                file_filter=file_filter,
                prior_findings=all_findings,
            )
            all_findings.extend(findings)
            executed_rule_ids.add(rule.rule_id)

            logger.debug(
                "Rule %s: %d findings",
                rule.rule_id,
                len(findings),
            )
        except Exception as e:
            logger.error(
                "Rule %s execution failed: %s",
                rule.rule_id,
                e,
                exc_info=True,
            )
            failed_rules.append(rule.rule_id)
            all_findings.append(
                AuditFinding(
                    check_id="governance.audit_engine.rule_evaluation_failed",
                    severity=AuditSeverity.HIGH,
                    message=(
                        f"Rule '{rule.rule_id}' could not be evaluated: "
                        f"{type(e).__name__}: {e}"
                    ),
                    context={
                        "rule_id": rule.rule_id,
                        "policy_id": getattr(rule, "policy_id", None),
                        "error_type": type(e).__name__,
                        "error": str(e),
                    },
                    evidence_class=EvidenceClass.ATTESTED,
                )
            )

    stats = {
        "total_rules": len(all_rules),
        "filtered_rules": len(filtered_rules),
        "executed_rules": len(executed_rule_ids),
        "failed_rules": len(failed_rules),
        "total_findings": len(all_findings),
        "skipped_context_level": len(skipped_context_level),
    }

    logger.info(
        "Filtered audit complete: %d/%d rules executed, %d findings%s",
        stats["executed_rules"],
        stats["filtered_rules"],
        stats["total_findings"],
        (
            f", {len(skipped_context_level)} context-level rule(s) skipped under --files"
            if skipped_context_level
            else ""
        ),
    )

    if failed_rules:
        logger.warning("Failed rules: %s", ", ".join(failed_rules))

    return [f.as_dict() for f in all_findings], executed_rule_ids, stats
