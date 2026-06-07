# src/mind/governance/shadow_audit.py

"""Shadow audit runner — pre-commit sensation cohort.

A specialisation of `stateless_audit` for the Limb's shadow-workspace
substrate (Octopus paper §3, V2.3-REBIRTH Phase 1). It partitions
**runtime-introspection engines** out of the runnable set, on the
principle that they ask a different question than the Limb needs
answered at proposal time.

The two engine categories CORE's audit conflates:

  Static engines — ast_gate, regex_gate, glob_gate, artifact_gate
    Ask "if the code SAYS this, is it constitutional?" Substrate is the
    file content. Naturally shadow-friendly: pointing the AuditorContext
    at a tempdir whose files have crate overlays answers the question
    correctly for the proposed change.

  Runtime engines — cli_gate, knowledge_gate, runtime_gate, llm_gate
    Ask "does the running SYSTEM have the right shape?" Substrate is
    the imported Typer registry, the DB-backed knowledge graph, the
    live blackboard, or the LLM provider. Each of these reflects the
    state of the deployed system, not the file-level proposition the
    Limb is sensing. Running them against a shadow tempdir either
    silently returns the wrong answer (cli_gate walks the live registry
    built from real-disk imports, not the shadow's would-be commands)
    or has no shadow projection at all (DB graph reflects committed
    state; LLM doesn't know what shadow is).

This split is not a carve-out. It is the recognition that pre-commit
sensation and post-commit verification are different jobs that happen
to share an engine framework. Shadow audits run the pre-commit job.
The post-commit job lives in the regular audit pass against the live
system, after the Limb's change has actually landed.

Boundaries preserved:
  - Mind layer, read-only. No DB writes, no filesystem writes.
  - IntentRepository is the sole path to `.intent/` (CLAUDE.md §6).
  - AuditorContext is built with stateless=True (no DB session needed
    once knowledge_gate is partitioned out).
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mind.governance.audit_context import AuditorContext
from mind.governance.filtered_audit import run_filtered_audit
from mind.governance.rule_extractor import extract_executable_rules
from mind.governance.stateless_audit import _STATELESS_SKIP_ENGINES
from shared.infrastructure.intent.intent_repository import IntentRepository
from shared.logger import getLogger


logger = getLogger(__name__)


# Runtime-introspection engines — see module docstring for the category
# distinction. These engines ask post-commit questions; running them
# against a shadow workspace either lies (cli_gate) or has no shadow
# projection (knowledge_gate, llm_gate, runtime_gate).
_SHADOW_INCOMPATIBLE_ENGINES: frozenset[str] = frozenset(
    {
        "cli_gate",
        "knowledge_gate",
        "llm_gate",
        "runtime_gate",
    }
)


_SHADOW_SKIP_REASONS: dict[str, str] = {
    "cli_gate": (
        "introspects the live Typer command registry (built from real-disk "
        "imports); cannot reflect a shadow workspace's proposed commands"
    ),
    "knowledge_gate": (
        "consumes the DB-backed knowledge graph (reflects committed state); "
        "no shadow projection at the data substrate"
    ),
    "llm_gate": (
        "calls an LLM provider whose context is the deployed codebase; "
        "no shadow projection at the substrate"
    ),
    "runtime_gate": (
        "reads blackboard telemetry from the live daemon; orthogonal to a "
        "pre-commit shadow workspace"
    ),
}


# ID: 420d0c50-a8ed-4a42-8391-7bd5aa94a22b
async def run_shadow_audit(
    intent_repo: IntentRepository,
    repo_path: Path,
    *,
    files: list[str] | None = None,
) -> dict[str, Any]:
    """Run the static-engine cohort of the constitutional audit.

    The shape mirrors `run_stateless_audit` — caller can swap one for the
    other and feed both into `ShadowAuditDiff` — but the runnable cohort
    is narrower: every runtime-introspection engine
    (`_SHADOW_INCOMPATIBLE_ENGINES` plus the existing stateless skips
    from `_STATELESS_SKIP_ENGINES`) is partitioned into `skipped_rules`
    with a reason string the smell-test UI can render verbatim.

    Args:
        intent_repo: IntentRepository carrying the governance content.
            Passed from the caller (the disk-pointed audit and the
            shadow-pointed audit should share the same intent_repo so
            the rule set on both sides is identical).
        repo_path: Filesystem root the audit walks. For the disk run,
            the real repo root. For the shadow run, the tempdir produced
            by `shared.infrastructure.context.shadow_materializer`.
        files: Optional list of file paths scoping per-file rules.

    Returns:
        Same shape as `run_stateless_audit`, with `mode="shadow"` to
        distinguish from CI / pre-commit runs.
    """
    context = AuditorContext(
        repo_path=repo_path,
        intent_repository=intent_repo,
        session_provider=None,
        llm_client=None,
        stateless=True,
    )

    context.reload_governance()
    all_rules = extract_executable_rules(context.policies, context.enforcement_loader)

    runnable_ids: list[str] = []
    skipped_rules: list[dict[str, str]] = []
    for rule in all_rules:
        if rule.engine in _STATELESS_SKIP_ENGINES:
            # Stateless skips win — same reason as the CI/pre-commit
            # path. Shadow runs without DB / LLM for the same reasons.
            skipped_rules.append(
                {
                    "rule_id": rule.rule_id,
                    "engine": rule.engine,
                    "reason": (
                        "requires DB or LLM; not available without daemon, "
                        "Postgres, or Qdrant"
                    ),
                }
            )
            continue
        if rule.engine in _SHADOW_INCOMPATIBLE_ENGINES:
            skipped_rules.append(
                {
                    "rule_id": rule.rule_id,
                    "engine": rule.engine,
                    "reason": _SHADOW_SKIP_REASONS[rule.engine],
                }
            )
            continue
        runnable_ids.append(rule.rule_id)

    logger.info(
        "shadow_audit: %d rules runnable; %d rules skipped "
        "(static-engine cohort only; runtime engines partitioned out)",
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
        "mode": "shadow",
    }


__all__ = ["run_shadow_audit"]
