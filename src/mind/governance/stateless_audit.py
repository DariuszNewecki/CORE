# src/mind/governance/stateless_audit.py

"""F-10.1a — Stateless audit runner.

The DB-free audit path for the CI/CD gate (F-10), pre-commit hook
(F-10.5), and any external invocation that must run without
core-api / core-daemon / Postgres / Qdrant.

ADR-085 §D1 routes engineering capacity here as the foundation of
F-10 (the operational-completeness gate's top-of-funnel item). ADR-084
D7 §1 (the completeness honesty commitment) makes a complete open
audit primitive load-bearing: until this path exists, the open base
does not actually ship an audit that an external repo can install
"with no daemon, database, or workers" per Tiers paper §3.1.

Architecture (Option A from F-10.1 recon, 2026-06-02):

  Stateless mode covers the rule subset that does NOT require the
  knowledge graph or the LLM. Specifically:

    - knowledge_gate engine rules — would read symbols_map /
      knowledge_graph from the Postgres-backed graph; unavailable
      without a DB session.
    - llm_gate engine rules — would call out to an LLM provider per
      rule per file. The latency cost violates Tiers §3.1's "first
      findings within minutes" criterion and the cache (also DB-
      backed) is absent here.

  These rules are partitioned out before dispatch and returned in a
  `skipped_rules` field of the result so the caller (typically a CLI
  consumer like F-10.1b) can surface the skip honestly rather than
  silently degrading rule coverage.

The remaining rule engines (ast_gate, regex_gate, glob_gate, cli_gate,
workflow_gate, artifact_gate, …) execute identically to their
daemon-driven counterparts. AuditorContext built with stateless=True
short-circuits load_knowledge_graph and sweep_llm_gate_cache as a
defence-in-depth measure; the partition here is the primary mechanism.

Boundaries this module preserves:

- Mind layer, read-only. No filesystem writes. No DB access (that's
  the whole point). No worker dispatch.
- IntentRepository is the only path to `.intent/` (CLAUDE.md §6).
- AuditorContext is built with stateless=True; the rest of the
  contract matches AuditorContext as constructed by the daemon and
  CLI today.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mind.governance.audit_context import AuditorContext
from mind.governance.filtered_audit import run_filtered_audit
from mind.governance.rule_extractor import extract_executable_rules
from shared.infrastructure.intent.audit_verdict import load_audit_verdict_policy
from shared.infrastructure.intent.intent_repository import IntentRepository
from shared.logger import getLogger


logger = getLogger(__name__)


# Engines whose rules require the knowledge graph or an LLM provider
# and therefore cannot run in stateless mode. Documented in
# `.specs/papers/CORE-Features.md#F-10` (stateless subset).
_STATELESS_SKIP_ENGINES: frozenset[str] = frozenset({"knowledge_gate", "llm_gate"})


# Skip-reason strings keyed by engine name. The CLI consumer (F-10.1b)
# surfaces these verbatim in the `--json` output's `skipped_rules`
# array so an external operator reading CI logs understands why the
# rule's verdict is absent.
_SKIP_REASONS: dict[str, str] = {
    "knowledge_gate": (
        "requires knowledge graph; not available in stateless mode "
        "(CI / pre-commit / no-DB)"
    ),
    "llm_gate": (
        "requires LLM provider + verdict cache; not available in stateless "
        "mode (CI / pre-commit / no-DB)"
    ),
}


# Individual rule_ids that structurally require db_session even though
# their owning engine also dispatches DB-independent check_types, so the
# coarser per-engine skip above doesn't apply to the whole engine. #856
# made runtime.worker_max_interval_within_observed fail closed with a
# BLOCK ENFORCEMENT_UNAVAILABLE finding whenever db_session is absent --
# which it always is in this stateless path (AuditorContext is built with
# session_provider=None a few lines below). Left unpartitioned, this rule
# would manufacture that finding on every stateless run, permanently
# capping CI's severity-based exit-code gate (audit.py::_run_offline_audit)
# at a false "compliance unknown" block instead of an honest skip. This is
# additive to the DEGRADED verdict handling further down (driven by
# .intent/enforcement/config/audit_verdict.yaml's ignored_finding_types),
# which stays exactly as-is for online audits where db_session can
# genuinely disappear mid-run for reasons other than "stateless mode never
# has one."
_STATELESS_SKIP_RULE_IDS: frozenset[str] = frozenset(
    {"runtime.worker_max_interval_within_observed"}
)


_SKIP_REASONS_BY_RULE_ID: dict[str, str] = {
    "runtime.worker_max_interval_within_observed": (
        "requires db_session (blackboard heartbeat aggregation); not "
        "available in stateless mode (CI / pre-commit / no-DB)"
    ),
}


# ID: 99361806-768b-45c2-ac9e-4e7cef1098cd
async def run_stateless_audit(
    intent_repo: IntentRepository,
    repo_path: Path,
    *,
    files: list[str] | None = None,
) -> dict[str, Any]:
    """Execute the constitutional audit without database access.

    The DB-free counterpart to `will.governance.audit_runner.run_sync_audit`.
    Used by the F-10 CI/CD gate, the F-10.5 pre-commit hook, and any
    other external invocation that cannot or should not reach the
    daemon / Postgres / Qdrant.

    Args:
        intent_repo: IntentRepository loaded for the target repo.
            Provides constitutional content; replaces the implicit
            `get_intent_repository()` AuditorContext would otherwise use.
        repo_path: Filesystem root of the repo being audited.
        files: Optional list of file paths (repo-relative, ./-prefixed,
            or absolute) scoping per-file rules. Context-level rules
            skip gracefully when this is set — same semantics as
            run_filtered_audit's existing file filter.

    Returns:
        A dict mirroring the shape `run_sync_audit` returns for filtered
        runs, plus a `skipped_rules` field:

            {
                "verdict": "PASS" | "FAIL",
                "passed": bool,
                "stats": {total_rules, executed_rules, skipped_rules_count, ...},
                "findings": [...],
                "executed_rule_ids": [...],
                "skipped_rules": [{"rule_id": "...", "engine": "...", "reason": "..."}, ...],
                "duration_sec": float,
                "run_id": None,
                "finished_at": ISO-8601 string,
                "mode": "stateless",
            }

        `run_id` is always None — stateless runs are not persisted.
        `mode` is always "stateless" — distinguishes from sync API runs
        whose payload shape this method intentionally mirrors.
    """
    context = AuditorContext(
        repo_path=repo_path,
        intent_repository=intent_repo,
        session_provider=None,
        llm_client=None,
        stateless=True,
    )

    # Partition before dispatch. Rules requiring the graph or LLM go
    # into skipped_rules; the rest are passed to run_filtered_audit as
    # an explicit allowlist.
    context.reload_governance()
    all_rules = extract_executable_rules(context.policies, context.enforcement_loader)

    runnable_ids: list[str] = []
    skipped_rules: list[dict[str, str]] = []
    for rule in all_rules:
        if rule.engine in _STATELESS_SKIP_ENGINES:
            skipped_rules.append(
                {
                    "rule_id": rule.rule_id,
                    "engine": rule.engine,
                    "reason": _SKIP_REASONS[rule.engine],
                }
            )
        elif rule.rule_id in _STATELESS_SKIP_RULE_IDS:
            skipped_rules.append(
                {
                    "rule_id": rule.rule_id,
                    "engine": rule.engine,
                    "reason": _SKIP_REASONS_BY_RULE_ID[rule.rule_id],
                }
            )
        else:
            runnable_ids.append(rule.rule_id)

    logger.info(
        "stateless_audit: %d rules runnable; %d rules skipped "
        "(knowledge_gate + llm_gate engines, plus %d rule(s) requiring "
        "db_session individually)",
        len(runnable_ids),
        len(skipped_rules),
        len(_STATELESS_SKIP_RULE_IDS),
    )

    # ADR-108 D4 / governance.no_governance_bypass: fail closed on governance
    # collapse. If the constitution declares rules but ZERO of them mapped to
    # an enforceable engine, the gate can evaluate nothing — returning PASS
    # would be a false-green (the BYOR root-split or an empty/unreachable
    # enforcement directory). Distinct "ERROR" verdict so the caller blocks on
    # operator action (the governance setup is broken), not developer action.
    # Boundary: this fires only on TOTAL collapse. A partial declared-only set
    # (CORE's Class-A unmapped rules) and the all-skipped-in-stateless case
    # (rules mapped but every engine is knowledge/llm) are both honest and stay
    # non-blocking — they are surfaced as coverage, not failure.
    declared_rule_count = _count_declared_rules(context.policies)
    if declared_rule_count > 0 and not all_rules:
        logger.error(
            "stateless_audit: governance collapse — %d rule(s) declared but 0 "
            "mapped to an enforceable engine; refusing to PASS "
            "(no_governance_bypass)",
            declared_rule_count,
        )
        return {
            "verdict": "ERROR",
            "passed": False,
            "stats": {
                "total_rules": 0,
                "runnable_rules": 0,
                "skipped_rules_count": len(skipped_rules),
                "declared_rules": declared_rule_count,
            },
            "findings": [],
            "executed_rule_ids": [],
            "skipped_rules": skipped_rules,
            "error": (
                f"governance collapse: {declared_rule_count} rule(s) declared but "
                "none map to an enforceable engine (enforcement mappings "
                "unreachable or empty); the audit can enforce nothing"
            ),
            "duration_sec": 0.0,
            "run_id": None,
            "finished_at": datetime.now(UTC).isoformat(),
            "mode": "stateless",
        }

    start_time = time.perf_counter()
    raw_findings, executed_ids, stats_dict = await run_filtered_audit(
        context,
        rule_ids=runnable_ids,
        files=files,
    )
    duration = time.perf_counter() - start_time

    findings_dicts = [f.as_dict() if hasattr(f, "as_dict") else f for f in raw_findings]

    blocking_findings = [
        f
        for f in findings_dicts
        if str(f.get("severity", "")).lower() in {"blocking", "block", "high"}
    ]

    # #847/#856: this path built its own PASS/FAIL-only verdict, entirely
    # independent of ConstitutionalAuditor._determine_verdict's DEGRADED
    # semantics and ignored_finding_types carve-out. That gap is
    # significant here specifically: db_session is *always* absent in the
    # stateless/offline path (this function builds AuditorContext with no
    # session_provider), so ENFORCEMENT_UNAVAILABLE findings for
    # runtime.worker_max_interval_within_observed — and pre-existing
    # ENFORCEMENT_FAILURE crash findings — are a real, common outcome of
    # exactly this CLI path (core-admin code audit --offline), not a
    # theoretical one. Reuses the same governed
    # .intent/enforcement/config/audit_verdict.yaml ignored_finding_types
    # vocabulary ConstitutionalAuditor consults, rather than inventing a
    # second closed vocabulary. Governor ruling 3/4: an unavailable
    # dependency or a crash makes the verdict DEGRADED, never silently
    # folded into an ordinary FAIL (which reads as "known non-compliant"
    # code, not "compliance unknown").
    #
    # Exit-code behavior is unchanged either way: the CLI's blocking-gate
    # decision (src/cli/resources/code/audit.py::_run_offline_audit) is
    # severity-based, not verdict-string-based, so this is a truthfulness
    # fix to the "verdict"/"passed" label, not a change to whether CI
    # blocks.
    verdict_policy = load_audit_verdict_policy()
    ignored_types = (
        set(verdict_policy.get("ignored_finding_types", []))
        if not verdict_policy.get("_error")
        else {"ENFORCEMENT_FAILURE", "ENFORCEMENT_UNAVAILABLE"}
    )
    degraded_findings = [
        f
        for f in blocking_findings
        if (f.get("context") or {}).get("finding_type") in ignored_types
    ]
    genuine_blocking_findings = [
        f for f in blocking_findings if f not in degraded_findings
    ]

    if verdict_policy.get("_error") or degraded_findings:
        verdict = "DEGRADED"
        passed = False
    elif genuine_blocking_findings:
        verdict = "FAIL"
        passed = False
    else:
        verdict = "PASS"
        passed = True

    return {
        "verdict": verdict,
        "passed": passed,
        "stats": {
            **stats_dict,
            "total_rules": len(all_rules),
            "runnable_rules": len(runnable_ids),
            "skipped_rules_count": len(skipped_rules),
        },
        "findings": findings_dicts,
        "executed_rule_ids": sorted(executed_ids),
        "skipped_rules": skipped_rules,
        "duration_sec": duration,
        "run_id": None,
        "finished_at": datetime.now(UTC).isoformat(),
        "mode": "stateless",
    }


def _count_declared_rules(policies: dict[str, Any]) -> int:
    """Count canonical rules declared across all loaded policies.

    Distinguishes "the constitution is empty" (legitimately nothing to
    enforce — PASS) from "rules are declared but none mapped to an engine"
    (governance collapse — fail closed). See ADR-108 D4.
    """
    total = 0
    for policy_data in policies.values():
        if not isinstance(policy_data, dict):
            continue
        rules = policy_data.get("rules", [])
        if isinstance(rules, list):
            total += sum(1 for r in rules if isinstance(r, dict) and r.get("id"))
    return total


__all__ = ["run_stateless_audit"]
