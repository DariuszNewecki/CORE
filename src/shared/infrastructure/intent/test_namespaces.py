# src/shared/infrastructure/intent/test_namespaces.py
"""Consumer-side discriminator for test-remediation findings (ADR-091 D5 Phase 5).

After Phase 5's canonical subject migration, `TestCoverageSensor` posts under
`python::test.coverage::<source_file>` and `TestRunnerSensor` posts under
`python::test.runner.missing::<source_file>` and
`python::test.runner.failure::<test_file>::<test_name>` (per ADR-091 D2).
These subjects share the `python::*` artifact prefix with `AuditViolationSensor`,
`CoherenceSensorWorker`, and `repo_crawler` — the legacy single-prefix
discriminators (`test.run_required::*`, `test.missing::*`, `test.failure::*`)
are gone.

Consumer pipelines that need to filter "is this finding a test-remediation
target?" call `is_test_remediation_subject(subject)` (Python path) or fold
`test_remediation_like_patterns()` into a SQL `LIKE ANY(:patterns)` binding.

Both derive from the set of `mandate.scope.rule_namespace` values declared by
worker declarations whose `implementation.class == "TestRunnerSensor"`.
The producer-side declaration IS the authoritative consumer-side filter:
TestRunnerSensor's output (the `python::test.runner.missing|failure::*`
sub_namespaces) is the set TestRemediator claims.

**TestCoverageSensor is intentionally excluded** from this predicate. Its
output (`python::test.coverage::*`) is consumed by TestRunnerSensor as
work-to-do (run pytest on the corresponding test file), not by
TestRemediator — those findings name uncovered source files that
TestRunnerSensor still needs to process. Including them in this predicate
would race-claim against TestRunnerSensor and route gap signals to
build.tests proposals before the pytest verification has run. The
producer/consumer pairing is: TestCoverageSensor → TestRunnerSensor →
(emits runner.missing/runner.failure) → TestRemediator. Pre-Phase-5 code
honored this split (`_MISSING_SUBJECT_PREFIX`/`_FAILURE_SUBJECT_PREFIX`
only); the canonical-format migration preserves it.

The ADR-091 D5 Phase 5 prose framed this predicate as "derived from both
test sensors' rule_namespaces"; pre-implementation smoke confirmed that
phrasing over-claims for the same reason Phase 3's `rule_namespaces()`
phrasing did. The correct semantic is "namespaces TestRemediator claims"
— i.e. TestRunnerSensor's output only. A Note appendix on ADR-091 records
the correction.

`CoherenceSensorWorker` is intentionally excluded from this predicate: per
ADR-027 D1 it is detection-only, and no production code consumes its
`python::coherence.incoherence::*` findings for remediation (verified during
Phase 5 implementation — its `_FINDING_SUBJECT` self-dedup in `coherence_sensor`
is the worker's own dedup of its own posts, not a third-party consumer).

The audit-violation predicate (`shared.infrastructure.intent.audit_namespaces`)
and this one are constitutional twins — same shape, different declared-class
filter. The third use of the pattern would earn a `consumer_domains` factor-up
per ADR-091's protocols-reflex discipline note; the second use stays as a
near-mechanical mirror.

LAYER: shared/infrastructure — pure derivation from IntentRepository; no DB
access, no LLM, no file writes. Constitutional consumer of the ADR-091 D2
canonical subject format.
"""

from __future__ import annotations

from shared.infrastructure.intent.intent_repository import get_intent_repository


_CANONICAL_ARTIFACT_TYPE = "python"
_CANONICAL_PREFIX = f"{_CANONICAL_ARTIFACT_TYPE}::"
_REMEDIATION_SENSOR_CLASS_NAMES = frozenset({"TestRunnerSensor"})


def _test_remediation_namespaces() -> set[str]:
    """Return the `rule_namespace` set declared by test-remediation sensors.

    Walks every worker declaration loaded by IntentRepository, keeps those
    whose `implementation.class == "TestRunnerSensor"`, and collects their
    `mandate.scope.rule_namespace` field values. The result
    (today: `{"test.runner"}`) is the authoritative test-remediation
    namespace set; the predicate accepts that exact value AND its
    D2-permitted dotted extensions (`test.runner.missing`,
    `test.runner.failure`).

    TestCoverageSensor is excluded — see module docstring for the
    producer/consumer split that motivates the exclusion.
    """
    repo = get_intent_repository()
    namespaces: set[str] = set()
    for worker_id in repo.list_workers():
        try:
            declaration = repo.load_worker(worker_id)
        except Exception:
            continue
        impl = declaration.get("implementation") or {}
        if impl.get("class") not in _REMEDIATION_SENSOR_CLASS_NAMES:
            continue
        scope = (declaration.get("mandate") or {}).get("scope") or {}
        rule_namespace = scope.get("rule_namespace")
        if isinstance(rule_namespace, str) and rule_namespace:
            namespaces.add(rule_namespace)
    return namespaces


# ID: ed90b8ee-f472-4dbd-be3f-1b7385e62f20
def is_test_remediation_subject(subject: str) -> bool:
    """Return True if `subject` is a test-remediation finding under ADR-091 D2.

    A subject qualifies when it begins with the canonical `python::` artifact
    prefix AND its sub_namespace (segment between the first two `::`
    separators) equals or extends a `rule_namespace` declared by a test sensor.

    Example matches (after Phase 5 row rewrite):
        python::test.runner.missing::src/foo.py     → True  (TestRunnerSensor)
        python::test.runner.failure::tests/x.py::t  → True  (TestRunnerSensor)

    Example non-matches (other python::* producers):
        python::test.coverage::src/foo.py              → False (TestCoverageSensor — consumed by TestRunnerSensor, not by TestRemediator)
        python::purity.docstrings.required::src/foo.py → False (AuditViolationSensor)
        python::coherence.incoherence::abc123          → False (CoherenceSensorWorker — detection only)
        python::coherence.repo_artifacts.drift::x      → False (repo_crawler)
    """
    if not subject.startswith(_CANONICAL_PREFIX):
        return False

    rest = subject[len(_CANONICAL_PREFIX) :]
    sub_namespace = rest.split("::", 1)[0]
    namespaces = _test_remediation_namespaces()
    if sub_namespace in namespaces:
        return True
    return any(sub_namespace.startswith(f"{ns}.") for ns in namespaces)


# ID: 11824c00-fc7c-4a76-961a-67dac7e132fb
def test_remediation_like_patterns() -> list[str]:
    """Return SQL LIKE patterns matching every test-remediation subject form.

    Each pattern targets one declared test-sensor namespace under both
    exact-match (`python::test.coverage::%`) and dotted-extension
    (`python::test.runner.%`) shapes — covering the D2-permitted sub_namespace
    extensions like `test.runner.missing` and `test.runner.failure`.

    Callers fold the list into a parameterised `subject LIKE ANY(:patterns)`
    binding — see `BlackboardQueryService.fetch_open_findings_by_patterns`
    and `BlackboardClaimService.claim_findings_by_patterns`.

    The list is derived fresh each call so a daemon-mid-cycle governance
    refresh (per ADR-039) immediately widens consumer queries to newly-loaded
    test-sensor declarations.
    """
    namespaces = sorted(_test_remediation_namespaces())
    return [f"{_CANONICAL_PREFIX}{ns}.%" for ns in namespaces] + [
        f"{_CANONICAL_PREFIX}{ns}::%" for ns in namespaces
    ]


# ID: f1ad3524-fcd0-48f8-963c-8ce4b0ac48cc
def test_remediation_subject_for(sub_namespace: str, identity_key_value: str) -> str:
    """Construct the canonical Phase-5 subject string for a single test finding.

    Convenience helper for sites that need to compute the exact subject a
    sensor would post (e.g. dedup-fetch keys). Equivalent to the framework's
    `post_artifact_finding` subject construction for `artifact_type=python`.
    """
    return f"{_CANONICAL_PREFIX}{sub_namespace}::{identity_key_value}"
