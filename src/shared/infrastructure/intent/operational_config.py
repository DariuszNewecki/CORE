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

from dataclasses import dataclass, field
from typing import Any

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
    # last N samples per subject instead. The default of 100 sits well
    # above WorkerClassificationConfig.cycle_window (5) and the consumer
    # sample_cap (cycle_window * 4 = 20), with investigation headroom.
    telemetry_keep_last_per_worker: int = 100


@dataclass(frozen=True)
# ID: eeee047a-d8a0-46d7-858a-1c6bb47079b5
class HealthLogConfig:
    stale_threshold_seconds: int = 3600


@dataclass(frozen=True)
# ID: d6b4d3bb-cb67-4a62-90a7-1a6ca68e50e0
class DaemonConfig:
    one_shot_interval_sec: int = 300
    # ADR-081 Step 0 — loop-hold instrumentation. Defaults are the OFF state
    # so a YAML revert returns to clean baseline. Step 3a-telemetry subscribes
    # a structured handler to the slow-callback warnings these settings emit.
    slow_callback_duration_sec: float = 0.1
    set_debug: bool = False


@dataclass(frozen=True)
# ID: 7e8f9a0b-1c2d-3e4f-5a6b-7c8d9e0f1a2b
class WorkerClassificationConfig:
    """ADR-081 D7 — gates for the runtime.worker_process_classification rule.

    The rule consumes loop_hold.sample blackboard entries (Step 3a-telemetry)
    and fires advisory findings when observed loop-hold contradicts the
    declared requires_dedicated_process state on a worker. The three gates
    here are the thresholds D7 specifies; values are tunable via
    .intent/enforcement/config/operational_config.yaml without code change.
    """

    loop_hold_escalation_sec: float = 5.0
    loop_hold_deescalation_sec: float = 1.0
    cycle_window: int = 5


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
    stuck_approved_sla_sec: int = 1800
    stuck_executing_sla_sec: int = 900
    repeated_failure_threshold: int = 3
    repeated_failure_lookback_sec: int = 86400
    findings_scan_limit: int = 200


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
    misc: MiscConfig = field(default_factory=MiscConfig)


# ---------------------------------------------------------------------------
# Per-section factories
# ---------------------------------------------------------------------------


def _load_llm(raw: dict[str, Any]) -> LLMConfig:
    sec = _section(raw, "llm")
    return LLMConfig(
        default_max_tokens=_get_int(sec, "default_max_tokens", 4096),
        default_max_length=_get_int(sec, "default_max_length", 4096),
        http_timeout_sec=_get_int(sec, "http_timeout_sec", 60),
        request_timeout_sec=_get_int(sec, "request_timeout_sec", 300),
        provider_timeout_sec=_get_int(sec, "provider_timeout_sec", 180),
    )


def _load_embedding(raw: dict[str, Any]) -> EmbeddingConfig:
    sec = _section(raw, "embedding")
    return EmbeddingConfig(
        chunk_size=_get_int(sec, "chunk_size", 512),
        chunk_overlap=_get_int(sec, "chunk_overlap", 50),
        max_chars=_get_int(sec, "max_chars", 20000),
        provider_request_timeout_sec=_get_float(
            sec, "provider_request_timeout_sec", 120.0
        ),
        provider_connect_timeout_sec=_get_float(
            sec, "provider_connect_timeout_sec", 10.0
        ),
        utils_request_timeout_sec=_get_float(sec, "utils_request_timeout_sec", 30.0),
    )


def _load_chunking(raw: dict[str, Any]) -> ChunkingConfig:
    sec = _section(raw, "chunking")
    return ChunkingConfig(max_chunk_chars=_get_int(sec, "max_chunk_chars", 1500))


def _load_blackboard(raw: dict[str, Any]) -> BlackboardConfig:
    sec = _section(raw, "blackboard")
    return BlackboardConfig(
        sla_default_seconds=_get_int(sec, "sla_default_seconds", 3600),
        telemetry_ttl_days=_get_int(sec, "telemetry_ttl_days", 7),
        telemetry_subject_prefixes=_get_str_tuple(
            sec, "telemetry_subject_prefixes", ("loop_hold.sample::",)
        ),
        delegate_finding_ttl_days=_get_int(sec, "delegate_finding_ttl_days", 7),
        delegate_finding_subjects=_get_str_tuple(
            sec,
            "delegate_finding_subjects",
            (
                "coherence.violation_executor.blast_bound",
                "coherence.repo_artifacts.drift",
            ),
        ),
        sweep_batch_max=_get_int(sec, "sweep_batch_max", 500),
        telemetry_keep_last_per_worker=_get_int(
            sec, "telemetry_keep_last_per_worker", 100
        ),
        reclaim_cap_n=_get_int(sec, "reclaim_cap_n", 3),
        remediation_cap_n=_get_int(sec, "remediation_cap_n", 3),
    )


def _load_health_log(raw: dict[str, Any]) -> HealthLogConfig:
    sec = _section(raw, "health_log")
    return HealthLogConfig(
        stale_threshold_seconds=_get_int(sec, "stale_threshold_seconds", 3600)
    )


def _load_daemon(raw: dict[str, Any]) -> DaemonConfig:
    sec = _section(raw, "daemon")
    return DaemonConfig(
        one_shot_interval_sec=_get_int(sec, "one_shot_interval_sec", 300),
        slow_callback_duration_sec=_get_float(sec, "slow_callback_duration_sec", 0.1),
        set_debug=_get_bool(sec, "set_debug", False),
    )


# ID: 6a7b8c9d-0e1f-2a3b-4c5d-6e7f8a9b0c1d
def _load_worker_classification(raw: dict[str, Any]) -> WorkerClassificationConfig:
    sec = _section(raw, "worker_classification")
    return WorkerClassificationConfig(
        loop_hold_escalation_sec=_get_float(sec, "loop_hold_escalation_sec", 5.0),
        loop_hold_deescalation_sec=_get_float(sec, "loop_hold_deescalation_sec", 1.0),
        cycle_window=_get_int(sec, "cycle_window", 5),
    )


def _load_proposals(raw: dict[str, Any]) -> ProposalsConfig:
    sec = _section(raw, "proposals")
    return ProposalsConfig(
        list_limit=_get_int(sec, "list_limit", 100),
        pending_limit=_get_int(sec, "pending_limit", 50),
    )


def _load_consequence_log(raw: dict[str, Any]) -> ConsequenceLogConfig:
    sec = _section(raw, "consequence_log")
    return ConsequenceLogConfig(
        default_lookback_seconds=_get_int(sec, "default_lookback_seconds", 3600)
    )


def _load_audit(raw: dict[str, Any]) -> AuditConfig:
    sec = _section(raw, "audit")
    return AuditConfig(
        llm_gate_verdict_cache_ttl_days=_get_int(
            sec, "llm_gate_verdict_cache_ttl_days", 30
        ),
        llm_gate_cache_staleness_threshold_seconds=_get_int(
            sec, "llm_gate_cache_staleness_threshold_seconds", 3600
        ),
    )


def _load_coverage(raw: dict[str, Any]) -> CoverageConfig:
    sec = _section(raw, "coverage")
    return CoverageConfig(
        gap_threshold_pct=_get_float(sec, "gap_threshold_pct", 75.0),
        warn_pct=_get_int(sec, "warn_pct", 75),
        low_bucket_pct=_get_int(sec, "low_bucket_pct", 50),
        gap_list_limit=_get_int(sec, "gap_list_limit", 10),
        collect_timeout_sec=_get_int(sec, "collect_timeout_sec", 120),
        full_run_timeout_sec=_get_int(sec, "full_run_timeout_sec", 300),
        quality_min_pct=_get_int(sec, "quality_min_pct", 75),
        watcher_required_pct=_get_float(sec, "watcher_required_pct", 75.0),
        watcher_rescan_hours=_get_int(sec, "watcher_rescan_hours", 24),
        batch_remediation_threshold_pct=_get_float(
            sec, "batch_remediation_threshold_pct", 75.0
        ),
        batch_remediation_partial_success_pct=_get_int(
            sec, "batch_remediation_partial_success_pct", 50
        ),
        single_file_target_pct=_get_float(sec, "single_file_target_pct", 75.0),
    )


def _load_workflow_gate(raw: dict[str, Any]) -> WorkflowGateConfig:
    sec = _section(raw, "workflow_gate")
    return WorkflowGateConfig(
        linter_timeout_sec=_get_float(sec, "linter_timeout_sec", 30.0),
        quality_timeout_sec=_get_float(sec, "quality_timeout_sec", 60.0),
        ruff_format_timeout_sec=_get_float(sec, "ruff_format_timeout_sec", 60.0),
        import_timeout_sec=_get_float(sec, "import_timeout_sec", 60.0),
    )


def _load_context(raw: dict[str, Any]) -> ContextConfig:
    sec = _section(raw, "context")
    return ContextConfig(
        score_target_file=_get_int(sec, "score_target_file", 100),
        score_target_path=_get_int(sec, "score_target_path", 80),
        score_target_symbol=_get_int(sec, "score_target_symbol", 120),
        score_has_content=_get_int(sec, "score_has_content", 30),
        vector_top_k=_get_int(sec, "vector_top_k", 10),
        db_provider_max_items=_get_int(sec, "db_provider_max_items", 100),
        token_estimate_overhead=_get_int(sec, "token_estimate_overhead", 300),
        cache_ttl_hours=_get_int(sec, "cache_ttl_hours", 24),
        db_recent_packets_limit=_get_int(sec, "db_recent_packets_limit", 10),
    )


def _load_health(raw: dict[str, Any]) -> HealthConfig:
    sec = _section(raw, "health")
    return HealthConfig(
        worker_alive_threshold_sec=_get_int(sec, "worker_alive_threshold_sec", 600),
        worker_warn_threshold_sec=_get_int(sec, "worker_warn_threshold_sec", 3600),
        long_lookback_hours=_get_int(sec, "long_lookback_hours", 24),
        medium_lookback_minutes=_get_int(sec, "medium_lookback_minutes", 60),
        short_lookback_minutes=_get_int(sec, "short_lookback_minutes", 30),
        recent_lookback_minutes=_get_int(sec, "recent_lookback_minutes", 10),
        worker_lease_renew_interval_sec=_get_int(
            sec, "worker_lease_renew_interval_sec", 240
        ),
    )


def _load_testing(raw: dict[str, Any]) -> TestingConfig:
    sec = _section(raw, "testing")
    return TestingConfig(
        pytest_collection_timeout_sec=_get_int(
            sec, "pytest_collection_timeout_sec", 30
        ),
        pytest_execution_timeout_sec=_get_int(sec, "pytest_execution_timeout_sec", 300),
        sandbox_timeout_sec=_get_int(sec, "sandbox_timeout_sec", 30),
        executor_timeout_sec=_get_int(sec, "executor_timeout_sec", 60),
        metrics_timeout_sec=_get_int(sec, "metrics_timeout_sec", 30),
        simple_gen_timeout_sec=_get_float(sec, "simple_gen_timeout_sec", 20.0),
        context_aware_gen_timeout_sec=_get_float(
            sec, "context_aware_gen_timeout_sec", 15.0
        ),
        runtime_validator_timeout_sec=_get_int(
            sec, "runtime_validator_timeout_sec", 60
        ),
        max_failures=_get_int(sec, "max_failures", 10),
        snippet_max_lines=_get_int(sec, "snippet_max_lines", 20),
    )


def _load_strategy_selector(raw: dict[str, Any]) -> StrategySelectorConfig:
    sec = _section(raw, "strategy_selector")
    return StrategySelectorConfig(
        min_recommended_score=_get_int(sec, "min_recommended_score", 15),
        score_role_preferred=_get_int(sec, "score_role_preferred", 25),
        score_role_discouraged=_get_int(sec, "score_role_discouraged", 25),
        score_generalized_match=_get_int(sec, "score_generalized_match", 16),
        score_rule_preferred=_get_int(sec, "score_rule_preferred", 12),
        score_rule_discouraged=_get_int(sec, "score_rule_discouraged", 12),
        score_size_bonus=_get_int(sec, "score_size_bonus", 10),
        score_size_penalty=_get_int(sec, "score_size_penalty", 10),
        score_strong_split=_get_int(sec, "score_strong_split", 14),
        score_cluster_count_bonus=_get_int(sec, "score_cluster_count_bonus", 8),
        score_cluster_count_penalty=_get_int(sec, "score_cluster_count_penalty", 8),
        score_constraint_role_bonus=_get_int(sec, "score_constraint_role_bonus", 9),
        score_constraint_role_penalty=_get_int(sec, "score_constraint_role_penalty", 8),
        score_conservatism_bias_bonus=_get_int(sec, "score_conservatism_bias_bonus", 8),
        score_conservatism_structural_bonus=_get_int(
            sec, "score_conservatism_structural_bonus", 5
        ),
        large_file_lines=_get_int(sec, "large_file_lines", 400),
        small_file_lines=_get_int(sec, "small_file_lines", 200),
        strong_split_lines=_get_int(sec, "strong_split_lines", 450),
    )


def _load_analyzers(raw: dict[str, Any]) -> AnalyzersConfig:
    sec = _section(raw, "analyzers")
    return AnalyzersConfig(
        file_complexity_high_threshold=_get_int(
            sec, "file_complexity_high_threshold", 15
        ),
        class_methods_high_threshold=_get_int(sec, "class_methods_high_threshold", 10),
        function_body_high_threshold=_get_int(sec, "function_body_high_threshold", 25),
        function_body_low_threshold=_get_int(sec, "function_body_low_threshold", 10),
        max_file_lines=_get_int(sec, "max_file_lines", 400),
        max_function_lines=_get_int(sec, "max_function_lines", 50),
        max_module_lines=_get_int(sec, "max_module_lines", 400),
    )


def _load_refactor(raw: dict[str, Any]) -> RefactorConfig:
    sec = _section(raw, "refactor")
    return RefactorConfig(
        responsibilities_threshold=_get_int(sec, "responsibilities_threshold", 20),
        cohesion_threshold=_get_int(sec, "cohesion_threshold", 12),
        coupling_threshold=_get_int(sec, "coupling_threshold", 10),
        loc_threshold=_get_int(sec, "loc_threshold", 400),
    )


def _load_clarity(raw: dict[str, Any]) -> ClarityConfig:
    sec = _section(raw, "clarity")
    return ClarityConfig(
        structural_complexity=_get_int(sec, "structural_complexity", 20),
        structural_lines=_get_int(sec, "structural_lines", 300),
        logic_simplification_threshold=_get_int(
            sec, "logic_simplification_threshold", 10
        ),
    )


def _load_complexity(raw: dict[str, Any]) -> ComplexityConfig:
    sec = _section(raw, "complexity")
    return ComplexityConfig(
        god_method_threshold=_get_int(sec, "god_method_threshold", 30),
        extraction_threshold=_get_int(sec, "extraction_threshold", 15),
    )


def _load_parsing(raw: dict[str, Any]) -> ParsingConfig:
    sec = _section(raw, "parsing")
    return ParsingConfig(
        min_block_len=_get_int(sec, "min_block_len", 10),
        score_test_fn=_get_int(sec, "score_test_fn", 1000),
        score_test_class=_get_int(sec, "score_test_class", 1000),
        score_import=_get_int(sec, "score_import", 100),
        score_pytest=_get_int(sec, "score_pytest", 500),
    )


def _load_execution(raw: dict[str, Any]) -> ExecutionConfig:
    sec = _section(raw, "execution")
    return ExecutionConfig(
        task_timeout_sec=_get_int(sec, "task_timeout_sec", 300),
        workflow_timeout_minutes=_get_int(sec, "workflow_timeout_minutes", 30),
        orchestrator_max_steps=_get_int(sec, "orchestrator_max_steps", 10),
    )


def _load_action(raw: dict[str, Any]) -> ActionConfig:
    sec = _section(raw, "action")
    return ActionConfig(
        max_data_size_bytes=_get_int(sec, "max_data_size_bytes", 5_242_880)
    )


def _load_prompt_pipeline(raw: dict[str, Any]) -> PromptPipelineConfig:
    sec = _section(raw, "prompt_pipeline")
    return PromptPipelineConfig(
        max_file_size_bytes=_get_int(sec, "max_file_size_bytes", 1_048_576)
    )


def _load_validator(raw: dict[str, Any]) -> ValidatorConfig:
    sec = _section(raw, "validator")
    return ValidatorConfig(
        lru_cache_size=_get_int(sec, "lru_cache_size", 1024),
        lru_cache_size_small=_get_int(sec, "lru_cache_size_small", 512),
    )


def _load_memory(raw: dict[str, Any]) -> MemoryConfig:
    sec = _section(raw, "memory")
    return MemoryConfig(
        recency_days=_get_int(sec, "recency_days", 30),
        episode_retention_days=_get_int(sec, "episode_retention_days", 30),
        reflection_retention_days=_get_int(sec, "reflection_retention_days", 90),
    )


def _load_repositories(raw: dict[str, Any]) -> RepositoriesConfig:
    sec = _section(raw, "repositories")
    return RepositoriesConfig(
        decision_trace_default_limit=_get_int(sec, "decision_trace_default_limit", 10),
        decision_trace_max_limit=_get_int(sec, "decision_trace_max_limit", 100),
        decision_trace_retention_days=_get_int(
            sec, "decision_trace_retention_days", 30
        ),
        refusal_default_limit=_get_int(sec, "refusal_default_limit", 20),
        refusal_by_type_limit=_get_int(sec, "refusal_by_type_limit", 50),
        symbol_definition_default_limit=_get_int(
            sec, "symbol_definition_default_limit", 500
        ),
        project_def_max_limit=_get_int(sec, "project_def_max_limit", 500),
        project_def_default_limit=_get_int(sec, "project_def_default_limit", 100),
    )


def _load_git(raw: dict[str, Any]) -> GitConfig:
    sec = _section(raw, "git")
    return GitConfig(
        recent_commits_n=_get_int(sec, "recent_commits_n", 10),
        changed_files_log_n=_get_int(sec, "changed_files_log_n", 20),
    )


def _load_vectors(raw: dict[str, Any]) -> VectorsConfig:
    sec = _section(raw, "vectors")
    return VectorsConfig(
        index_batch_size=_get_int(sec, "index_batch_size", 10),
        scan_limit=_get_int(sec, "scan_limit", 10000),
        report_preview_count=_get_int(sec, "report_preview_count", 10),
        policy_vectorizer_batch_size=_get_int(sec, "policy_vectorizer_batch_size", 10),
    )


def _load_sync(raw: dict[str, Any]) -> SyncConfig:
    sec = _section(raw, "sync")
    return SyncConfig(
        artifact_embed_batch_size=_get_int(sec, "artifact_embed_batch_size", 10),
        policy_index_batch_size=_get_int(sec, "policy_index_batch_size", 10),
        pattern_index_batch_size=_get_int(sec, "pattern_index_batch_size", 10),
        specs_index_batch_size=_get_int(sec, "specs_index_batch_size", 10),
    )


def _load_authority_package(raw: dict[str, Any]) -> AuthorityPackageConfig:
    sec = _section(raw, "authority_package")
    return AuthorityPackageConfig(search_limit=_get_int(sec, "search_limit", 10))


def _load_strategic_auditor(raw: dict[str, Any]) -> StrategicAuditorConfig:
    sec = _section(raw, "strategic_auditor")
    return StrategicAuditorConfig(
        sample_limit=_get_int(sec, "sample_limit", 100),
        commit_lookback=_get_int(sec, "commit_lookback", 15),
        compact_max_chars=_get_int(sec, "compact_max_chars", 1500),
    )


def _load_misc(raw: dict[str, Any]) -> MiscConfig:
    sec = _section(raw, "misc")
    return MiscConfig(
        linelength_max_line_chars=_get_int(sec, "linelength_max_line_chars", 100),
        enrichment_description_max_chars=_get_int(
            sec, "enrichment_description_max_chars", 500
        ),
        conversation_max_content_chars=_get_int(
            sec, "conversation_max_content_chars", 2000
        ),
        code_snippet_context_lines=_get_int(sec, "code_snippet_context_lines", 20),
        embedding_search_default_limit=_get_int(
            sec, "embedding_search_default_limit", 10
        ),
        retriever_search_limit=_get_int(sec, "retriever_search_limit", 10),
        retriever_context_lines=_get_int(sec, "retriever_context_lines", 20),
        file_navigator_read_max_lines=_get_int(
            sec, "file_navigator_read_max_lines", 200
        ),
        file_navigator_max_read_bytes=_get_int(
            sec, "file_navigator_max_read_bytes", 1_048_576
        ),
        knowledge_consolidation_max_lines=_get_int(
            sec, "knowledge_consolidation_max_lines", 10
        ),
        context_export_http_timeout_sec=_get_int(
            sec, "context_export_http_timeout_sec", 10
        ),
        metadata_max_comment_length=_get_int(sec, "metadata_max_comment_length", 120),
        census_hotspot_limit=_get_int(sec, "census_hotspot_limit", 10),
        clustering_default_n_clusters=_get_int(
            sec, "clustering_default_n_clusters", 15
        ),
        legacy_scan_display_limit=_get_int(sec, "legacy_scan_display_limit", 10),
        limb_status_recent_limit=_get_int(sec, "limb_status_recent_limit", 15),
        refusal_inspect_default_limit=_get_int(
            sec, "refusal_inspect_default_limit", 20
        ),
        refusal_inspect_by_type_limit=_get_int(
            sec, "refusal_inspect_by_type_limit", 20
        ),
        capability_tagging_default_llm_confidence=_get_float(
            sec, "capability_tagging_default_llm_confidence", 0.70
        ),
        knowledge_min_occurrences=_get_int(sec, "knowledge_min_occurrences", 3),
        knowledge_max_lines=_get_int(sec, "knowledge_max_lines", 10),
        context_aware_test_context_lines=_get_int(
            sec, "context_aware_test_context_lines", 40
        ),
        perf_overhead_warning_pct=_get_int(sec, "perf_overhead_warning_pct", 50),
        perf_overhead_error_pct=_get_int(sec, "perf_overhead_error_pct", 100),
        context_search_display_limit=_get_int(sec, "context_search_display_limit", 20),
        proposals_display_limit=_get_int(sec, "proposals_display_limit", 20),
    )


def _load_workers(raw: dict[str, Any]) -> WorkersConfig:
    workers = _section(raw, "workers")
    return WorkersConfig(
        call_site_rewriter=WorkerCallSiteRewriterConfig(
            claim_limit=_get_int(
                _section(workers, "call_site_rewriter"), "claim_limit", 50
            )
        ),
        doc_writer=WorkerDocWriterConfig(
            batch_size=_get_int(_section(workers, "doc_writer"), "batch_size", 25)
        ),
        doc_worker=WorkerDocWorkerConfig(
            batch_size=_get_int(_section(workers, "doc_worker"), "batch_size", 50)
        ),
        prompt_artifact_writer=WorkerPromptArtifactWriterConfig(
            claim_limit=_get_int(
                _section(workers, "prompt_artifact_writer"), "claim_limit", 25
            )
        ),
        prompt_extractor=WorkerPromptExtractorConfig(
            claim_limit=_get_int(
                _section(workers, "prompt_extractor"), "claim_limit", 25
            ),
            context_lines=_get_int(
                _section(workers, "prompt_extractor"), "context_lines", 40
            ),
        ),
        capability_tagger=WorkerCapabilityTaggerConfig(
            batch_size=_get_int(
                _section(workers, "capability_tagger"), "batch_size", 20
            )
        ),
        proposal_consumer=WorkerProposalConsumerConfig(
            claim_limit=_get_int(
                _section(workers, "proposal_consumer"), "claim_limit", 5
            )
        ),
        violation_executor=WorkerViolationExecutorConfig(
            claim_limit=_get_int(
                _section(workers, "violation_executor"), "claim_limit", 50
            )
        ),
        violation_remediator=WorkerViolationRemediatorConfig(
            claim_limit=_get_int(
                _section(workers, "violation_remediator"), "claim_limit", 50
            ),
            scan_limit=_get_int(
                _section(workers, "violation_remediator"), "scan_limit", 200
            ),
            ceremony_timeout_sec=_get_int(
                _section(workers, "violation_remediator"), "ceremony_timeout_sec", 30
            ),
            semantic_examples_limit=_get_int(
                _section(workers, "violation_remediator"),
                "semantic_examples_limit",
                3,
            ),
            min_role_confidence=_get_float(
                _section(workers, "violation_remediator"),
                "min_role_confidence",
                0.55,
            ),
        ),
        worker_shop=WorkerShopConfig(
            glide_off_multiplier=_get_float(
                _section(workers, "worker_shop"), "glide_off_multiplier", 0.10
            ),
            fallback_threshold_sec=_get_int(
                _section(workers, "worker_shop"), "fallback_threshold_sec", 600
            ),
            findings_scan_limit=_get_int(
                _section(workers, "worker_shop"), "findings_scan_limit", 200
            ),
        ),
        proposal_pipeline_shop=WorkerProposalPipelineShopConfig(
            stuck_approved_sla_sec=_get_int(
                _section(workers, "proposal_pipeline_shop"),
                "stuck_approved_sla_sec",
                1800,
            ),
            stuck_executing_sla_sec=_get_int(
                _section(workers, "proposal_pipeline_shop"),
                "stuck_executing_sla_sec",
                900,
            ),
            repeated_failure_threshold=_get_int(
                _section(workers, "proposal_pipeline_shop"),
                "repeated_failure_threshold",
                3,
            ),
            repeated_failure_lookback_sec=_get_int(
                _section(workers, "proposal_pipeline_shop"),
                "repeated_failure_lookback_sec",
                86400,
            ),
            findings_scan_limit=_get_int(
                _section(workers, "proposal_pipeline_shop"),
                "findings_scan_limit",
                200,
            ),
        ),
        test_remediator=WorkerTestRemediatorConfig(
            scan_limit=_get_int(_section(workers, "test_remediator"), "scan_limit", 200)
        ),
        test_runner_sensor=WorkerTestRunnerSensorConfig(
            scan_limit=_get_int(
                _section(workers, "test_runner_sensor"), "scan_limit", 50
            )
        ),
        intent_inspector=WorkerIntentInspectorConfig(
            alignment_batch=_get_int(
                _section(workers, "intent_inspector"), "alignment_batch", 20
            )
        ),
        observer=WorkerObserverConfig(
            stale_threshold_seconds=_get_int(
                _section(workers, "observer"), "stale_threshold_seconds", 3600
            )
        ),
        coherence_sensor=WorkerCoherenceSensorConfig(
            lookback_seconds=_get_int(
                _section(workers, "coherence_sensor"), "lookback_seconds", 7200
            )
        ),
    )


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
        from shared.infrastructure.intent.intent_repository import (
            get_intent_repository,
        )

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

    return OperationalConfig(
        llm=_load_llm(raw),
        embedding=_load_embedding(raw),
        chunking=_load_chunking(raw),
        workers=_load_workers(raw),
        blackboard=_load_blackboard(raw),
        health_log=_load_health_log(raw),
        daemon=_load_daemon(raw),
        worker_classification=_load_worker_classification(raw),
        proposals=_load_proposals(raw),
        consequence_log=_load_consequence_log(raw),
        audit=_load_audit(raw),
        coverage=_load_coverage(raw),
        workflow_gate=_load_workflow_gate(raw),
        context=_load_context(raw),
        health=_load_health(raw),
        testing=_load_testing(raw),
        strategy_selector=_load_strategy_selector(raw),
        analyzers=_load_analyzers(raw),
        refactor=_load_refactor(raw),
        clarity=_load_clarity(raw),
        complexity=_load_complexity(raw),
        parsing=_load_parsing(raw),
        execution=_load_execution(raw),
        action=_load_action(raw),
        prompt_pipeline=_load_prompt_pipeline(raw),
        validator=_load_validator(raw),
        memory=_load_memory(raw),
        repositories=_load_repositories(raw),
        git=_load_git(raw),
        vectors=_load_vectors(raw),
        sync=_load_sync(raw),
        authority_package=_load_authority_package(raw),
        strategic_auditor=_load_strategic_auditor(raw),
        misc=_load_misc(raw),
    )
