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
        else:
            runnable_ids.append(rule.rule_id)

    logger.info(
        "stateless_audit: %d rules runnable; %d rules skipped "
        "(knowledge_gate + llm_gate not available without DB)",
        len(runnable_ids),
        len(skipped_rules),
    )

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
    passed = not blocking_findings
    verdict = "PASS" if passed else "FAIL"

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


__all__ = ["run_stateless_audit"]
