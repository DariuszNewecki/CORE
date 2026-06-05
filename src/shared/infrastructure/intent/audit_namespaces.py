# src/shared/infrastructure/intent/audit_namespaces.py
"""Consumer-side discriminator for audit-violation findings (ADR-091 D5 Phase 3).

After Phase 3's canonical subject migration, `AuditViolationSensor` posts under
`python::<rule_namespace>::<file_path>` (per ADR-091 D2). This subject prefix
is shared with test sensors, the coherence sensor, and repo_crawler — the
legacy single-prefix discriminator (the historical `audit dot violation`
namespace) is gone.

Consumer pipelines that need to filter "is this finding an audit-violation?"
call `is_audit_violation_subject(subject)` (Python path) or fold
`audit_violation_like_patterns()` into a SQL `LIKE ANY(:patterns)` binding.

Both derive from the set of `mandate.scope.rule_namespace` values declared by
worker declarations whose `implementation.class == "AuditViolationSensor"`.
The producer-side declarations ARE the authoritative consumer-side filter:
if no audit sensor is declared to emit under `<ns>`, the violation_remediator
pipeline has no business claiming `python::<ns>::*` findings (they belong to
a different pipeline — CCC inline, coherence_sensor, test sensors, etc.).

This deliberately differs from `IntentRepository.rule_namespaces()`. The set
of top-level rule directories under `.intent/rules/` is a SUPERSET of the
audit-sensor namespace set — rule directories like `coherence/` exist for
CCC inline use, with no audit_sensor backing. Predicate-derivation drift
note in ADR-091 §Risks: a sensor declaring a `rule_namespace` whose
`.intent/rules/<ns>/` tree is empty would still register here (matched by
declaration) but `_resolve_rule_ids` returns empty, so the producer never
emits and the predicate stays correct by vacuous truth.

BYOR contract: a third-party audit sensor shipped as
`.intent/workers/audit_sensor_<x>.yaml` with `rule_namespace: <ns>` and
rules at `.intent/rules/<ns>/` is automatically claimed by this predicate.
No enumeration drift across consumer call sites; no constitutional
vocabulary change.

LAYER: shared/infrastructure — pure derivation from IntentRepository; no DB
access, no LLM, no file writes. Constitutional consumer of the ADR-091 D2
canonical subject format.
"""

from __future__ import annotations

from shared.infrastructure.intent.intent_repository import get_intent_repository


_CANONICAL_ARTIFACT_TYPE = "python"
_CANONICAL_PREFIX = f"{_CANONICAL_ARTIFACT_TYPE}::"
_AUDIT_SENSOR_CLASS_NAME = "AuditViolationSensor"


def _audit_violation_namespaces() -> set[str]:
    """Return the set of `rule_namespace` values declared by audit-sensor workers.

    Walks every worker declaration loaded by IntentRepository, keeps those
    whose `implementation.class` equals `AuditViolationSensor`, and collects
    their `mandate.scope.rule_namespace` field values. The result is the
    audit-violation namespace set authoritative for consumer-side filtering.
    """
    repo = get_intent_repository()
    namespaces: set[str] = set()
    for worker_id in repo.list_workers():
        try:
            declaration = repo.load_worker(worker_id)
        except Exception:
            continue
        impl = declaration.get("implementation") or {}
        if impl.get("class") != _AUDIT_SENSOR_CLASS_NAME:
            continue
        scope = (declaration.get("mandate") or {}).get("scope") or {}
        rule_namespace = scope.get("rule_namespace")
        if isinstance(rule_namespace, str) and rule_namespace:
            namespaces.add(rule_namespace)
    return namespaces


# ID: b7cac333-0e93-4c1e-a24e-7c94d1aaae51
def is_audit_violation_subject(subject: str) -> bool:
    """Return True if `subject` is an audit-violation finding under ADR-091 D2.

    A subject qualifies when it begins with the canonical `python::` artifact
    prefix AND its sub_namespace (segment between the first two `::`
    separators) has a top-level dot segment that matches the `rule_namespace`
    of a declared `AuditViolationSensor` worker.

    Example matches (after Phase 3 row rewrite):
        python::purity.docstrings.required::src/foo.py            → True
        python::architecture.channels.logger_not_presentation::… → True

    Example non-matches (other python::* producers per D3):
        python::test.coverage::src/foo.py                  → False
        python::test.runner.failure::src/foo.py            → False
        python::coherence.incoherence::abc123              → False (CoherenceSensorWorker)
        python::coherence.repo_artifacts.drift::…          → False (repo_crawler)
        python::ai.fragile_string_check::…                 → False (no audit_sensor_ai.yaml)
    """
    if not subject.startswith(_CANONICAL_PREFIX):
        return False

    rest = subject[len(_CANONICAL_PREFIX) :]
    sub_namespace = rest.split("::", 1)[0]
    top_segment = sub_namespace.split(".", 1)[0]

    return top_segment in _audit_violation_namespaces()


# ID: 003af3a3-65eb-47c7-9de5-c8b3d09d8917
def audit_violation_like_patterns() -> list[str]:
    """Return SQL LIKE patterns matching every audit-violation subject form.

    Each pattern targets one declared audit-sensor namespace: e.g.
    `python::purity.%`, `python::architecture.%`. Callers fold the list into
    a parameterised `subject LIKE ANY(:patterns)` binding — see
    `BlackboardQueryService.fetch_open_finding_subjects_by_patterns`.

    The list is derived fresh each call so a daemon-mid-cycle governance
    refresh (per ADR-039) immediately widens consumer queries to newly-loaded
    audit-sensor declarations — symmetric with the producer-side dynamic
    rule resolution in `AuditViolationSensor._resolve_rule_ids`.

    Two pattern variants per namespace cover both dotted-subrule subjects
    (`python::purity.docstrings.required::…`) and exact-namespace subjects
    (`python::purity::…`) — the latter form appears only when a namespace
    has a single rule ID equal to the namespace name, but the predicate
    accepts both shapes so the pattern set must too.
    """
    namespaces = sorted(_audit_violation_namespaces())
    return [f"{_CANONICAL_PREFIX}{ns}.%" for ns in namespaces] + [
        f"{_CANONICAL_PREFIX}{ns}::%" for ns in namespaces
    ]


# ID: 9fc2d5b7-47a0-4100-8161-ce7f52e5bc2d
def audit_violation_subject_for(rule_id: str, file_path: str) -> str:
    """Construct the canonical Phase-3 subject string for a single violation.

    Convenience helper for sites that need to compute the exact subject a
    sensor would post (e.g. dedup-fetch keys). Equivalent to the framework's
    `post_artifact_finding` subject construction for `artifact_type=python`.
    """
    return f"{_CANONICAL_PREFIX}{rule_id}::{file_path}"
