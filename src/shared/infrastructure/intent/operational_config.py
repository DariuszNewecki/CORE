# src/shared/infrastructure/intent/operational_config.py
"""
Loader for .intent/enforcement/config/operational_config.yaml (ADR-040).

Every runtime-behavior knob that previously lived as a literal in src/ is
declared in operational_config.yaml; this module reads the file via
IntentRepository and returns a tree of frozen dataclasses callers can
consume. On any failure — missing file, parse error, malformed section —
the loader logs a warning and falls back to defaults that match the
shipped YAML values. It never raises, so the daemon can boot and the
remediation loop can keep running while a governor reviews the failure.

Pattern mirrors src/will/workers/circuit_breaker.py: one frozen dataclass
per top-level YAML section, plus a single public load_*_config function.
The workers section is nested — each sub-key becomes its own Worker*Config
collected into WorkersConfig.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, get_origin, get_type_hints

from shared.infrastructure.intent.intent_repository import get_intent_repository
from shared.logger import getLogger


logger = getLogger(__name__)

CORE_ROLE = "catalog"  # ADR-095 D3


# ---------------------------------------------------------------------------
# Coercion helpers
# ---------------------------------------------------------------------------


def _section(raw: dict[str, Any] | None, name: str) -> dict[str, Any]:
    if not raw:
        return {}
    sub = raw.get(name)
    if sub is None:
        return {}
    if not isinstance(sub, dict):
        logger.warning(
            "operational_config: section %r is not a mapping — using fallback defaults.",
            name,
        )
        return {}
    return sub


def _get_int(sec: dict[str, Any], key: str, default: int) -> int:
    val = sec.get(key)
    if val is None:
        return default
    try:
        return int(val)
    except (TypeError, ValueError):
        logger.warning(
            "operational_config: %s should be int, got %r — using fallback %d.",
            key,
            val,
            default,
        )
        return default


def _get_float(sec: dict[str, Any], key: str, default: float) -> float:
    val = sec.get(key)
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        logger.warning(
            "operational_config: %s should be float, got %r — using fallback %r.",
            key,
            val,
            default,
        )
        return default


# ID: 4d2a8e4c-1a8b-4b6e-9c2a-3f0e7a8b5d11
def _get_bool(sec: dict[str, Any], key: str, default: bool) -> bool:
    val = sec.get(key)
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    logger.warning(
        "operational_config: %s should be bool, got %r — using fallback %r.",
        key,
        val,
        default,
    )
    return default


# ID: 9b4f3e2c-7a8d-4e1f-b3c5-2d6e9f0a1b8c
def _get_str_tuple(
    sec: dict[str, Any], key: str, default: tuple[str, ...]
) -> tuple[str, ...]:
    val = sec.get(key)
    if val is None:
        return default
    if isinstance(val, list) and all(isinstance(x, str) for x in val):
        return tuple(val)
    logger.warning(
        "operational_config: %s should be a list of strings, got %r — using fallback %r.",
        key,
        val,
        default,
    )
    return default


# ---------------------------------------------------------------------------
# Section dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
# ID: d077c23b-94b9-48eb-966c-92ade3d25d5c
class LLMConfig:
    default_max_tokens: int = 4096
    default_max_length: int = 4096
    http_timeout_sec: int = 60
    request_timeout_sec: int = 300
    provider_timeout_sec: int = 180


@dataclass(frozen=True)
# ID: 570aadb4-d174-4abc-bb31-dbb578c80401
class EmbeddingConfig:
    chunk_size: int = 512
    chunk_overlap: int = 50
    max_chars: int = 20000
    provider_request_timeout_sec: float = 120.0
    provider_connect_timeout_sec: float = 10.0
    utils_request_timeout_sec: float = 30.0


@dataclass(frozen=True)
# ID: 4b29ce9f-d734-44ff-9bc3-f9b956878f4a
class ChunkingConfig:
    max_chunk_chars: int = 1500


@dataclass(frozen=True)
# ID: dee98ce9-d8e4-4ad7-bc41-f0c9a2291389
class BlackboardConfig:
    """Blackboard hygiene + ADR-082 writer-as-sensor retention knobs.

    sla_default_seconds — fallback SLA tier when entry_type is unmapped.

    ADR-082 retention policy — two sweep mechanisms hosted in
    BlackboardShopManager:

    - Mechanism 1 (terminal telemetry): hard DELETE rows whose subject
      starts with one of telemetry_subject_prefixes, status is already
      terminal, and created_at is older than telemetry_ttl_days.
    - Mechanism 2 (DELEGATE OPEN findings): transition status open →
      resolved for rows whose subject is in delegate_finding_subjects
      and created_at is older than delegate_finding_ttl_days. The
      writer's run.complete report preserves the event payload, so
      auto-resolution is information-preserving.

    sweep_batch_max — row cap per sweep run (rails per
    feedback_destructive_autonomous_needs_rails_first). Also caps the
    ADR-104 orphaned-claim reaper sweep.

    reclaim_cap_n — ADR-104 D3 reclaim rail. After an orphaned claim has
    been released this many times (orphan_release_count), the entry is
    abandoned (terminal) instead of re-opened, breaking a crash -> reclaim
    -> crash loop on an unprocessable finding. The orphaned-claim grace
    window and liveness threshold are NOT separate knobs here: per ADR-104
    ratification #2 they ARE HealthConfig.worker_alive_threshold_sec (one
    clock, no second number to drift).

    remediation_cap_n — ADR-104 D9 (#637) remediation-attempt rail, the D3
    abandon-at-cap principle applied to the *remediation-failure* loop (a
    different trigger from the orphaned-claim loop). After a finding has
    been revived from this many failed proposals
    (payload.remediation_attempt_count), it is abandoned (terminal Type-B)
    instead of routed back to awaiting_reaudit, breaking a
    generate -> fail -> revive -> regenerate loop on a perpetually-failing
    remediation. Reuses D3's "tolerate two transient failures" calibration
    but is its own knob — a perpetually-failing generation is a distinct
    phenomenon from a crashing worker and may want independent tuning.
    """

    sla_default_seconds: int = 3600
    telemetry_ttl_days: int = 7
    telemetry_subject_prefixes: tuple[str, ...] = ("loop_hold.sample::",)
    delegate_finding_ttl_days: int = 7
    delegate_finding_subjects: tuple[str, ...] = (
        "coherence.violation_executor.blast_bound",
        "coherence.repo_artifacts.drift",
    )
    sweep_batch_max: int = 500
    reclaim_cap_n: int = 3
    remediation_cap_n: int = 3
    # #568: count-based retention for slow-callback telemetry. Time-based
    # TTL over-prunes well-behaved workers (rare emitters lose their entire
    # window) while leaving hot emitters with hundreds of rows. Keep the
    # last N samples per subject instead. The default of 100 matches the
    # typical 24h sample volume for active workers (ADR-082 evidence:
    # ~100 samples/24h); the ADR-082 query safety cap (2000) is rarely
    # reached in practice.
    telemetry_keep_last_per_worker: int = 100


@dataclass(frozen=True)
# ID: eeee047a-d8a0-46d7-858a-1c6bb47079b5
class HealthLogConfig:
    stale_threshold_seconds: int = 3600
    convergence_rolling_window: int = 30


@dataclass(frozen=True)
# ID: d6b4d3bb-cb67-4a62-90a7-1a6ca68e50e0
class DaemonConfig:
    one_shot_interval_sec: int = 300
    # ADR-081 Step 0 — loop-hold instrumentation. Defaults are the OFF state
    # so a YAML revert returns to clean baseline. Step 3a-telemetry subscribes
    # a structured handler to the slow-callback warnings these settings emit.
    slow_callback_duration_sec: float = 0.1
    set_debug: bool = False
    startup_jitter_cap_sec: int = 30
    systemctl_timeout_sec: float = 30.0


@dataclass(frozen=True)
# ID: 7e8f9a0b-1c2d-3e4f-5a6b-7c8d9e0f1a2b
class WorkerClassificationConfig:
    """ADR-081 D7 / ADR-082 — gates for the runtime.worker_process_classification rule.

    The rule consumes loop_hold.sample blackboard entries (Step 3a-telemetry)
    and fires advisory findings when observed loop-hold contradicts the
    declared requires_dedicated_process state on a worker.

    ADR-082 replaces the rolling-N cycle_window with time-bucketed windows:
    escalation looks at the worst hold in the last loop_hold_escalation_hours
    (24h default); de-escalation requires loop_hold_deescalation_hours (168h)
    of sustained cleanliness plus heartbeat activity proof. Correct for
    event-driven sparse sampling — loop_hold.sample rows post only when
    slow_callback_duration is tripped.
    """

    loop_hold_escalation_sec: float = 5.0
    loop_hold_deescalation_sec: float = 1.0
    loop_hold_escalation_hours: int = 24
    loop_hold_deescalation_hours: int = 168
    min_samples_for_escalation: int = 3
    min_active_heartbeats_for_deescalation: int = 10


@dataclass(frozen=True)
# ID: 546c1ad9-c7b5-43a7-af49-d2083f7fe865
class ProposalsConfig:
    list_limit: int = 100
    pending_limit: int = 50


@dataclass(frozen=True)
# ID: 367521a6-1521-4fb1-89f1-f1ac6c01a1a1
class ConsequenceLogConfig:
    default_lookback_seconds: int = 3600


@dataclass(frozen=True)
# ID: 4d2c1a90-8e6b-4f37-9c05-3b1e2a7d6f84
class LogMaintenanceConfig:
    """ADR-052 — core.llm_exchange_log DDL partition-maintenance policy.

    - advance_months: how many future monthly partitions the maintenance
      action pre-creates ahead of ``today`` so inserts never hit a missing
      partition.
    - default_retention_months: fallback retention horizon when a caller
      does not pass an explicit value — partitions older than this are
      detached and archived.
    """

    advance_months: int = 3
    default_retention_months: int = 24


@dataclass(frozen=True)
# ID: 8b3c6f4e-2a91-43d7-b582-7e1d4a9c0f6b
class AuditConfig:
    """ADR-044 — incremental llm_gate verdict cache knobs.

    - llm_gate_verdict_cache_ttl_days: rows older than this are swept at
      the start of each audit run. TTL is hygiene, not correctness —
      content + rule hash mismatches are the correctness mechanism.
    - llm_gate_cache_staleness_threshold_seconds: when the crawler's
      repo_artifacts.last_crawled_at is older than this, the engine
      recomputes file_content_hash inline rather than trusting the
      stored value. Bounds the window in which a stale crawler hash
      could produce an incorrect cache hit.
    """

    llm_gate_verdict_cache_ttl_days: int = 30
    llm_gate_cache_staleness_threshold_seconds: int = 3600


@dataclass(frozen=True)
# ID: 3101bd97-4957-40cc-85f5-96fa0e874cd4
class CoverageConfig:
    gap_threshold_pct: float = 75.0
    warn_pct: int = 75
    low_bucket_pct: int = 50
    gap_list_limit: int = 10
    collect_timeout_sec: int = 120
    full_run_timeout_sec: int = 300
    quality_min_pct: int = 75
    watcher_required_pct: float = 75.0
    watcher_rescan_hours: int = 24
    batch_remediation_threshold_pct: float = 75.0
    batch_remediation_partial_success_pct: int = 50
    single_file_target_pct: float = 75.0


@dataclass(frozen=True)
# ID: c1625d9c-2e4a-44a4-a009-55e2a75e07fe
class WorkflowGateConfig:
    linter_timeout_sec: float = 30.0
    quality_timeout_sec: float = 60.0
    ruff_format_timeout_sec: float = 60.0
    import_timeout_sec: float = 60.0


@dataclass(frozen=True)
# ID: e37c8ce2-6a3a-45d7-a63e-f9b3ec810b14
class ContextConfig:
    score_target_file: int = 100
    score_target_path: int = 80
    score_target_symbol: int = 120
    score_has_content: int = 30
    vector_top_k: int = 10
    db_provider_max_items: int = 100
    token_estimate_overhead: int = 300
    cache_ttl_hours: int = 24
    db_recent_packets_limit: int = 10


@dataclass(frozen=True)
# ID: a77084a2-9655-4884-a17a-95d0d3f16d91
class HealthConfig:
    worker_alive_threshold_sec: int = 600
    worker_warn_threshold_sec: int = 3600
    long_lookback_hours: int = 24
    medium_lookback_minutes: int = 60
    short_lookback_minutes: int = 30
    recent_lookback_minutes: int = 10
    # ADR-104 D8 — the liveness lease. A worker refreshes worker_registry
    # .last_heartbeat on this cadence for as long as its run() executes, so a
    # claim-holder whose single run exceeds worker_alive_threshold_sec is not
    # mistaken for dead and reaped by the orphaned-claim reaper (ADR-104 D1).
    # MUST stay comfortably below worker_alive_threshold_sec; 240 < 600 gives
    # ~2.5x margin against a missed renewal.
    worker_lease_renew_interval_sec: int = 240


@dataclass(frozen=True)
# ID: a199bb79-5c14-408c-a116-256f72347d9f
class TestingConfig:
    pytest_collection_timeout_sec: int = 30
    pytest_execution_timeout_sec: int = 300
    sandbox_timeout_sec: int = 30
    executor_timeout_sec: int = 60
    metrics_timeout_sec: int = 30
    simple_gen_timeout_sec: float = 20.0
    context_aware_gen_timeout_sec: float = 15.0
    runtime_validator_timeout_sec: int = 60
    max_failures: int = 10
    snippet_max_lines: int = 20


@dataclass(frozen=True)
# ID: 399b9dd7-d2cf-4be5-9721-b8e020e51250
class StrategySelectorConfig:
    min_recommended_score: int = 15
    score_role_preferred: int = 25
    score_role_discouraged: int = 25
    score_generalized_match: int = 16
    score_rule_preferred: int = 12
    score_rule_discouraged: int = 12
    score_size_bonus: int = 10
    score_size_penalty: int = 10
    score_strong_split: int = 14
    score_cluster_count_bonus: int = 8
    score_cluster_count_penalty: int = 8
    score_constraint_role_bonus: int = 9
    score_constraint_role_penalty: int = 8
    score_conservatism_bias_bonus: int = 8
    score_conservatism_structural_bonus: int = 5
    large_file_lines: int = 400
    small_file_lines: int = 200
    strong_split_lines: int = 450


@dataclass(frozen=True)
# ID: cea759ac-b5e2-4204-adb3-c0c5c6c1bab1
class AnalyzersConfig:
    file_complexity_high_threshold: int = 15
    class_methods_high_threshold: int = 10
    function_body_high_threshold: int = 25
    function_body_low_threshold: int = 10
    max_file_lines: int = 400
    max_function_lines: int = 50
    max_module_lines: int = 400


@dataclass(frozen=True)
# ID: ba518c5d-cb6b-4871-a145-5b7e55668a96
class ModularityConfig:
    """fix.modularity confidence gate (ADR-040).

    Relocated from governance_paths.yaml so the knob is read through the
    IntentRepository-backed operational_config projection instead of a raw
    file read. Default matches the shipped YAML value.
    """

    split_confidence_threshold: float = 0.75


@dataclass(frozen=True)
# ID: 046dc166-28df-4900-9c59-0dcf5eece8df
class RefactorConfig:
    responsibilities_threshold: int = 20
    cohesion_threshold: int = 12
    coupling_threshold: int = 10
    loc_threshold: int = 400


@dataclass(frozen=True)
# ID: d2c55fd2-9508-4863-a1d1-ed5c171914e5
class ClarityConfig:
    structural_complexity: int = 20
    structural_lines: int = 300
    logic_simplification_threshold: int = 10


@dataclass(frozen=True)
# ID: ca897e8c-2d2a-4384-9c0e-e50a7a150e63
class ComplexityConfig:
    god_method_threshold: int = 30
    extraction_threshold: int = 15


@dataclass(frozen=True)
# ID: 9f5cb6d0-a2e8-4e7e-850f-5d52cacad63a
class ParsingConfig:
    min_block_len: int = 10
    score_test_fn: int = 1000
    score_test_class: int = 1000
    score_import: int = 100
    score_pytest: int = 500


@dataclass(frozen=True)
# ID: 531bbd4c-d181-44d7-a951-2d1ed6f3f092
class ExecutionConfig:
    task_timeout_sec: int = 300
    workflow_timeout_minutes: int = 30
    orchestrator_max_steps: int = 10
    orchestrator_adaptive_confidence: float = 0.3


@dataclass(frozen=True)
# ID: ee1df82a-359f-48ef-a220-971826be7ea0
class ValidationStrategyConfig:
    """Confidence thresholds per named validation strategy (ADR-040)."""

    minimal_threshold: float = 0.7
    standard_threshold: float = 0.8
    comprehensive_threshold: float = 0.9
    critical_path_threshold: float = 0.95
    default_threshold: float = 0.8


@dataclass(frozen=True)
# ID: 4f332080-09c6-4ee6-b93b-41ab22095174
class ActionConfig:
    max_data_size_bytes: int = 5_242_880


@dataclass(frozen=True)
# ID: 4ed8b90f-159e-4147-af1d-d5a01cbc4ef7
class PromptPipelineConfig:
    max_file_size_bytes: int = 1_048_576


@dataclass(frozen=True)
# ID: d586577a-437e-4c26-8dd1-ba5283b8a6f0
class ValidatorConfig:
    lru_cache_size: int = 1024
    lru_cache_size_small: int = 512


@dataclass(frozen=True)
# ID: 15bf16dc-c670-4742-a338-39a134a8d744
class MemoryConfig:
    recency_days: int = 30
    episode_retention_days: int = 30
    reflection_retention_days: int = 90


@dataclass(frozen=True)
# ID: 972301d5-6370-47c1-a9b2-1668aa89b332
class RepositoriesConfig:
    decision_trace_default_limit: int = 10
    decision_trace_max_limit: int = 100
    decision_trace_retention_days: int = 30
    refusal_default_limit: int = 20
    refusal_by_type_limit: int = 50
    symbol_definition_default_limit: int = 500
    project_def_max_limit: int = 500
    project_def_default_limit: int = 100


@dataclass(frozen=True)
# ID: c21addc5-f8d0-41b5-a716-8984e28da0d8
class GitConfig:
    recent_commits_n: int = 10
    changed_files_log_n: int = 20


@dataclass(frozen=True)
# ID: 51388277-8f97-4655-b5a2-a704716ef4fe
class VectorsConfig:
    index_batch_size: int = 10
    scan_limit: int = 10000
    report_preview_count: int = 10
    policy_vectorizer_batch_size: int = 10


@dataclass(frozen=True)
# ID: 2d33c98b-1ed4-499b-a821-4764ed72a4ec
class SyncConfig:
    artifact_embed_batch_size: int = 10
    policy_index_batch_size: int = 10
    pattern_index_batch_size: int = 10
    specs_index_batch_size: int = 10


@dataclass(frozen=True)
# ID: 87095648-7a0f-4b32-b430-eb54cba9aa39
class AuthorityPackageConfig:
    search_limit: int = 10


@dataclass(frozen=True)
# ID: eb02fecc-3b0e-4b78-8aef-48eac9572b85
class StrategicAuditorConfig:
    sample_limit: int = 100
    commit_lookback: int = 15
    compact_max_chars: int = 1500


@dataclass(frozen=True)
# ID: 1db478c8-329c-401f-864c-c7a3982f22f4
class MiscConfig:
    linelength_max_line_chars: int = 100
    enrichment_description_max_chars: int = 500
    enrichment_symbols_batch_limit: int = 200
    conversation_max_content_chars: int = 2000
    code_snippet_context_lines: int = 20
    embedding_search_default_limit: int = 10
    retriever_search_limit: int = 10
    retriever_context_lines: int = 20
    file_navigator_read_max_lines: int = 200
    file_navigator_max_read_bytes: int = 1_048_576
    knowledge_consolidation_max_lines: int = 10
    context_export_http_timeout_sec: int = 10
    metadata_max_comment_length: int = 120
    census_hotspot_limit: int = 10
    clustering_default_n_clusters: int = 15
    legacy_scan_display_limit: int = 10
    limb_status_recent_limit: int = 15
    refusal_inspect_default_limit: int = 20
    refusal_inspect_by_type_limit: int = 20
    capability_tagging_default_llm_confidence: float = 0.70
    knowledge_min_occurrences: int = 3
    knowledge_max_lines: int = 10
    context_aware_test_context_lines: int = 40
    perf_overhead_warning_pct: int = 50
    perf_overhead_error_pct: int = 100
    context_search_display_limit: int = 20
    proposals_display_limit: int = 20


# ---------------------------------------------------------------------------
# Workers section — one dataclass per worker sub-key
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
# ID: 2b9a3a7b-f6c2-404b-8b3d-05ecf70b618d
class WorkerCallSiteRewriterConfig:
    claim_limit: int = 50


@dataclass(frozen=True)
# ID: cd230702-b80c-41a2-8d52-a0297aa989c0
class WorkerDocWriterConfig:
    batch_size: int = 25


@dataclass(frozen=True)
# ID: d627b73c-8a7c-4260-adff-c7a2d274d12e
class WorkerDocWorkerConfig:
    batch_size: int = 50


@dataclass(frozen=True)
# ID: 7cd69bc3-41f2-48b7-b330-5d170cf86860
class WorkerPromptArtifactWriterConfig:
    claim_limit: int = 25


@dataclass(frozen=True)
# ID: 123297dc-8907-4baf-9602-f33f79002b48
class WorkerPromptExtractorConfig:
    claim_limit: int = 25
    context_lines: int = 40


@dataclass(frozen=True)
# ID: 593b96fb-329b-46e4-b490-3029df029e47
class WorkerCapabilityTaggerConfig:
    batch_size: int = 20


@dataclass(frozen=True)
# ID: 76350f2c-892a-41ef-8562-1bee90a5e69b
class WorkerProposalConsumerConfig:
    claim_limit: int = 5


@dataclass(frozen=True)
# ID: 47236015-9d93-4f93-af91-1334353de07f
class WorkerViolationExecutorConfig:
    claim_limit: int = 50


@dataclass(frozen=True)
# ID: accbcdf4-23be-44bd-b0c0-4212dfe9fd4e
class WorkerViolationRemediatorConfig:
    claim_limit: int = 50
    scan_limit: int = 200
    ceremony_timeout_sec: int = 30
    semantic_examples_limit: int = 3
    min_role_confidence: float = 0.55


@dataclass(frozen=True)
# ID: 4f4f42b4-c4eb-4d05-b97a-5dcd97dbca5c
class WorkerShopConfig:
    glide_off_multiplier: float = 0.10
    fallback_threshold_sec: int = 600
    findings_scan_limit: int = 200


@dataclass(frozen=True)
# ID: db4c3515-9de4-44ee-9bb5-283ef53b87b6
class WorkerProposalPipelineShopConfig:
    """
    finalizing_redrive_cap_n — ADR-150 D1 (#802): the abandon-at-cap rail
    (ADR-104 D3/D9 family, third instance) applied to the stuck-finalizing
    roll-forward loop. After this many failed redrives, counted in place on
    the proposal's single persistent open stuck_finalizing finding, the
    finding escalates to the governor inbox (indeterminate/human, ADR-150
    D2) and the proposal is excluded from further redrive until a human
    resolves the finding (ADR-150 D3 re-arm). Own knob per D9's precedent:
    an unrecordable consequence chain is a distinct phenomenon from a
    crashing worker or a perpetually-failing generation.
    """

    stuck_approved_sla_sec: int = 1800
    stuck_executing_sla_sec: int = 900
    stuck_finalizing_sla_sec: int = 300
    stuck_undeferred_sla_sec: int = 120
    repeated_failure_threshold: int = 3
    repeated_failure_lookback_sec: int = 86400
    findings_scan_limit: int = 200
    finalizing_redrive_cap_n: int = 3


@dataclass(frozen=True)
# ID: 9447633e-e6c3-49e5-8a2b-34570dfb0d74
class WorkerTestRemediatorConfig:
    scan_limit: int = 200


@dataclass(frozen=True)
# ID: 87dc2e43-4fa4-4f06-9729-5863e4e970bf
class WorkerTestRunnerSensorConfig:
    scan_limit: int = 50


@dataclass(frozen=True)
# ID: 382dfb51-5dde-4934-8ede-f89042f2c3df
class WorkerIntentInspectorConfig:
    alignment_batch: int = 20


@dataclass(frozen=True)
# ID: b4073ed0-e290-4ce0-95d3-14f11647e428
class WorkerObserverConfig:
    stale_threshold_seconds: int = 3600


@dataclass(frozen=True)
# ID: 0e3397a8-6a9a-49c6-a253-0829101e8a4e
class WorkerCoherenceSensorConfig:
    lookback_seconds: int = 7200


@dataclass(frozen=True)
# ID: 5b0e2c1a-9d47-4f8e-b3a6-7c1e0f4d2a98
class WorkerVarTmpJanitorConfig:
    # ADR-117 D2/D3 retention rails, governor-tunable.
    retention_days: int = 7
    max_reap_per_run: int = 200


@dataclass(frozen=True)
# ID: 7f3a9d05-1e62-4b8c-8f04-2d5b6a1c9e73
class WorkerCanaryJanitorConfig:
    # ADR-147 sandbox retention rails, governor-tunable.
    retention_seconds: int = 3600
    max_reap_per_run: int = 50


@dataclass(frozen=True)
# ID: e1b5e532-edb4-405f-b09f-57339041baf9
class WorkersConfig:
    call_site_rewriter: WorkerCallSiteRewriterConfig = field(
        default_factory=WorkerCallSiteRewriterConfig
    )
    doc_writer: WorkerDocWriterConfig = field(default_factory=WorkerDocWriterConfig)
    doc_worker: WorkerDocWorkerConfig = field(default_factory=WorkerDocWorkerConfig)
    prompt_artifact_writer: WorkerPromptArtifactWriterConfig = field(
        default_factory=WorkerPromptArtifactWriterConfig
    )
    prompt_extractor: WorkerPromptExtractorConfig = field(
        default_factory=WorkerPromptExtractorConfig
    )
    capability_tagger: WorkerCapabilityTaggerConfig = field(
        default_factory=WorkerCapabilityTaggerConfig
    )
    proposal_consumer: WorkerProposalConsumerConfig = field(
        default_factory=WorkerProposalConsumerConfig
    )
    violation_executor: WorkerViolationExecutorConfig = field(
        default_factory=WorkerViolationExecutorConfig
    )
    violation_remediator: WorkerViolationRemediatorConfig = field(
        default_factory=WorkerViolationRemediatorConfig
    )
    worker_shop: WorkerShopConfig = field(default_factory=WorkerShopConfig)
    proposal_pipeline_shop: WorkerProposalPipelineShopConfig = field(
        default_factory=WorkerProposalPipelineShopConfig
    )
    test_remediator: WorkerTestRemediatorConfig = field(
        default_factory=WorkerTestRemediatorConfig
    )
    test_runner_sensor: WorkerTestRunnerSensorConfig = field(
        default_factory=WorkerTestRunnerSensorConfig
    )
    intent_inspector: WorkerIntentInspectorConfig = field(
        default_factory=WorkerIntentInspectorConfig
    )
    observer: WorkerObserverConfig = field(default_factory=WorkerObserverConfig)
    coherence_sensor: WorkerCoherenceSensorConfig = field(
        default_factory=WorkerCoherenceSensorConfig
    )
    var_tmp_janitor: WorkerVarTmpJanitorConfig = field(
        default_factory=WorkerVarTmpJanitorConfig
    )
    canary_janitor: WorkerCanaryJanitorConfig = field(
        default_factory=WorkerCanaryJanitorConfig
    )


# ---------------------------------------------------------------------------
# Top-level config
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
# ID: 973dd73d-45af-4909-a275-c4fd44af56fb
class OperationalConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)
    workers: WorkersConfig = field(default_factory=WorkersConfig)
    blackboard: BlackboardConfig = field(default_factory=BlackboardConfig)
    health_log: HealthLogConfig = field(default_factory=HealthLogConfig)
    daemon: DaemonConfig = field(default_factory=DaemonConfig)
    worker_classification: WorkerClassificationConfig = field(
        default_factory=WorkerClassificationConfig
    )
    proposals: ProposalsConfig = field(default_factory=ProposalsConfig)
    consequence_log: ConsequenceLogConfig = field(default_factory=ConsequenceLogConfig)
    log_maintenance: LogMaintenanceConfig = field(default_factory=LogMaintenanceConfig)
    audit: AuditConfig = field(default_factory=AuditConfig)
    coverage: CoverageConfig = field(default_factory=CoverageConfig)
    workflow_gate: WorkflowGateConfig = field(default_factory=WorkflowGateConfig)
    context: ContextConfig = field(default_factory=ContextConfig)
    health: HealthConfig = field(default_factory=HealthConfig)
    testing: TestingConfig = field(default_factory=TestingConfig)
    strategy_selector: StrategySelectorConfig = field(
        default_factory=StrategySelectorConfig
    )
    analyzers: AnalyzersConfig = field(default_factory=AnalyzersConfig)
    modularity: ModularityConfig = field(default_factory=ModularityConfig)
    refactor: RefactorConfig = field(default_factory=RefactorConfig)
    clarity: ClarityConfig = field(default_factory=ClarityConfig)
    complexity: ComplexityConfig = field(default_factory=ComplexityConfig)
    parsing: ParsingConfig = field(default_factory=ParsingConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    action: ActionConfig = field(default_factory=ActionConfig)
    prompt_pipeline: PromptPipelineConfig = field(default_factory=PromptPipelineConfig)
    validator: ValidatorConfig = field(default_factory=ValidatorConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    repositories: RepositoriesConfig = field(default_factory=RepositoriesConfig)
    git: GitConfig = field(default_factory=GitConfig)
    vectors: VectorsConfig = field(default_factory=VectorsConfig)
    sync: SyncConfig = field(default_factory=SyncConfig)
    authority_package: AuthorityPackageConfig = field(
        default_factory=AuthorityPackageConfig
    )
    strategic_auditor: StrategicAuditorConfig = field(
        default_factory=StrategicAuditorConfig
    )
    validation_strategy: ValidationStrategyConfig = field(
        default_factory=ValidationStrategyConfig
    )
    misc: MiscConfig = field(default_factory=MiscConfig)


# ---------------------------------------------------------------------------
# Generic loader — replaces 34 per-section _load_* functions
# ---------------------------------------------------------------------------


# ID: e8265df6-2116-4504-af8e-036aa6d1e806
def _load_from_sec[T](sec: dict[str, Any], cls: type[T]) -> T:
    """Construct a frozen dataclass from a YAML section dict.

    Dispatches each field by resolved type (bool before int to avoid
    subclass collision; tuple[str, ...] via get_origin; nested dataclasses
    recursed one level via _section). Falls back to the field's declared
    default on any type mismatch or missing key — error logged, never raised.
    """
    hints = get_type_hints(cls)
    kwargs: dict[str, Any] = {}
    for f in dataclasses.fields(cls):  # type: ignore[arg-type]
        if not f.init:
            continue
        typ = hints[f.name]
        if dataclasses.is_dataclass(typ):
            kwargs[f.name] = _load_from_sec(_section(sec, f.name), typ)  # type: ignore[arg-type]
        elif typ is bool:
            kwargs[f.name] = _get_bool(sec, f.name, f.default)  # type: ignore[arg-type]
        elif typ is int:
            kwargs[f.name] = _get_int(sec, f.name, f.default)  # type: ignore[arg-type]
        elif typ is float:
            kwargs[f.name] = _get_float(sec, f.name, f.default)  # type: ignore[arg-type]
        elif get_origin(typ) is tuple:
            kwargs[f.name] = _get_str_tuple(sec, f.name, f.default)  # type: ignore[arg-type]
    return cls(**kwargs)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Public loader
# ---------------------------------------------------------------------------


# ID: f5b20a98-a3b5-4e8d-a19e-f310639cd2a9
def load_operational_config() -> OperationalConfig:
    """
    Load .intent/enforcement/config/operational_config.yaml via IntentRepository.

    Returns an OperationalConfig with every section populated from the
    YAML file. On any failure — missing file, parse error, non-mapping
    section, type-coercion error on a single field — the loader logs a
    warning at WARNING level and substitutes the matching fallback
    default. It never raises, so callers can use the result unconditionally.

    The drift window is bounded by IntentRepository.reload() on the next
    audit-sensor cycle (ADR-039).
    """
    raw: dict[str, Any] = {}
    try:
        repo = get_intent_repository()
        config_path = repo.resolve_rel("enforcement/config/operational_config.yaml")
        loaded = repo.load_document(config_path)
        if isinstance(loaded, dict):
            raw = loaded
        else:
            logger.warning(
                "operational_config: operational_config.yaml did not parse as a "
                "dict — using fallback defaults."
            )
    except Exception as exc:
        logger.warning(
            "operational_config: could not load .intent/enforcement/config/"
            "operational_config.yaml (%s) — using fallback defaults.",
            exc,
        )

    return _load_from_sec(raw, OperationalConfig)
