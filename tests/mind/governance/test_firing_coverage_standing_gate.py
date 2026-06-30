# tests/mind/governance/test_firing_coverage_standing_gate.py

"""Standing firing-coverage gate (ADR-076 D6 promotion).

The D6 fixture-level firing-coverage test in
``test_adr_076_firing_coverage.py`` asserts every artifact_gate
check_type can be made to fire. This test exercises the standing
counterpart: the assertion that lives in the audit driver itself,
emits a ``SCOPE_INERT`` finding for every enforcing per-file rule
whose declared scope matches zero files in the walked set, and so
makes a future #480-class drift visible in the next audit verdict
instead of discoverable months later.

The unit under test is
``mind.governance.constitutional_auditor_dynamic._check_per_file_scope_coverage``.
It is exercised directly because surfacing through ``run_dynamic_rules``
would require the full audit context fixture and crowd out the
narrow assertion these tests exist to make.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock


from mind.governance.auditor import AuditVerdict, ConstitutionalAuditor
from mind.governance.constitutional_auditor_dynamic import (
    _check_per_file_scope_coverage,
)
from mind.governance.executable_rule import ExecutableRule
from shared.models import AuditSeverity


def _ctx(
    files_for: dict[tuple[tuple[str, ...], tuple[str, ...]], list[Path]],
) -> MagicMock:
    """Stub AuditorContext whose ``get_files`` returns canned results.

    Keyed by (include_tuple, exclude_tuple) so each rule can be wired
    to its own walked-set match independently. Default empty list
    triggers the gate.
    """
    ctx = MagicMock()

    def _get_files(include, exclude=None):
        key = (tuple(include), tuple(exclude or []))
        return files_for.get(key, [])

    ctx.get_files.side_effect = _get_files
    return ctx


def _rule(
    rule_id: str,
    *,
    engine: str = "ast_gate",
    scope: list[str] | None = None,
    exclusions: list[str] | None = None,
    enforcement: str = "blocking",
    is_context_level: bool = False,
) -> ExecutableRule:
    return ExecutableRule(
        rule_id=rule_id,
        engine=engine,
        params={},
        enforcement=enforcement,
        scope=scope if scope is not None else ["src/**/*.py"],
        exclusions=exclusions or [],
        is_context_level=is_context_level,
    )


# ---------------------------------------------------------------------------
# Positive case: a forced zero-match enforcing per-file rule fires the gate
# ---------------------------------------------------------------------------


def test_forced_zero_scope_emits_scope_inert_finding():
    """A blocking per-file rule whose scope matches no walked-set file
    MUST surface a SCOPE_INERT BLOCK finding."""
    rule = _rule(
        "test.scope_drift",
        scope=["src/nonexistent_dir/**/*.py"],
        exclusions=[],
    )
    ctx = _ctx({})  # any include → empty list

    findings = _check_per_file_scope_coverage(ctx, [rule])

    assert len(findings) == 1
    f = findings[0]
    assert f.check_id == "test.scope_drift.scope_inert"
    assert f.severity == AuditSeverity.BLOCK
    assert "SCOPE_INERT" in f.message
    assert "test.scope_drift" in f.message
    assert f.context["finding_type"] == "SCOPE_INERT"
    assert f.context["scope"] == ["src/nonexistent_dir/**/*.py"]


# ---------------------------------------------------------------------------
# Negative cases: every exclusion path
# ---------------------------------------------------------------------------


def test_matched_scope_emits_nothing():
    """A blocking per-file rule whose scope matches >=1 file in the
    walked set is healthy — no finding."""
    rule = _rule("test.healthy", scope=["src/**/*.py"], exclusions=[])
    ctx = _ctx({(("src/**/*.py",), ()): [Path("src/foo.py")]})

    findings = _check_per_file_scope_coverage(ctx, [rule])

    assert findings == []


def test_context_level_rule_skipped():
    """Context-level rules dispatch via verify_context, not the file
    walker, so they are out of scope for this gate even with empty
    rule scope."""
    rule = _rule(
        "test.context_only",
        is_context_level=True,
        scope=[],
    )
    ctx = _ctx({})

    findings = _check_per_file_scope_coverage(ctx, [rule])

    assert findings == []


def test_empty_scope_by_design_skipped():
    """ADR-043 D7: scope=[] is a deliberate inertness marker (the
    rule runs at proposal-execution time, not audit time). The gate
    must not flag it."""
    rule = _rule("purity.logic_conservation", engine="llm_gate", scope=[])
    ctx = _ctx({})

    findings = _check_per_file_scope_coverage(ctx, [rule])

    assert findings == []


def test_passive_engine_skipped():
    """passive_gate + its aliases return OK by construction; their
    rules' enforcement lives outside the audit pipeline (decoration
    time, registry registration time, runtime). Excluded from the
    gate."""
    for engine in (
        "passive_gate",
        "python_runtime",
        "type_system",
        "runtime_metric",
        "advisory",
        "runtime_check",
        "dataclass_validation",
    ):
        rule = _rule(f"test.passive.{engine}", engine=engine)
        ctx = _ctx({})  # zero matches

        findings = _check_per_file_scope_coverage(ctx, [rule])

        assert findings == [], f"passive engine {engine} must not trigger the gate"


def test_advisory_rule_skipped():
    """Advisory/reporting rules can have zero matches by intent —
    they're not constraints."""
    for level in ("reporting", "advisory"):
        rule = _rule(
            f"test.advisory.{level}",
            enforcement=level,
            scope=["src/nonexistent/**/*.py"],
        )
        ctx = _ctx({})

        findings = _check_per_file_scope_coverage(ctx, [rule])

        assert findings == [], f"enforcement={level} must not trigger the gate"


# ---------------------------------------------------------------------------
# Mixed-set sanity: gate fires for the inert rule and is silent for healthy
# siblings in the same pass
# ---------------------------------------------------------------------------


def test_mixed_rule_set_isolates_inert_rule():
    """Given several rules, only the zero-match blocking per-file
    rule should produce a finding."""
    healthy = _rule("test.healthy", scope=["src/**/*.py"])
    inert = _rule("test.drifted", scope=["src/gone/**/*.py"])
    advisory = _rule(
        "test.advisory",
        enforcement="reporting",
        scope=["src/also_gone/**/*.py"],
    )
    ctx_level = _rule("test.ctx", is_context_level=True, scope=[])

    ctx = _ctx({(("src/**/*.py",), ()): [Path("src/foo.py")]})

    findings = _check_per_file_scope_coverage(
        ctx, [healthy, inert, advisory, ctx_level]
    )

    assert [f.check_id for f in findings] == ["test.drifted.scope_inert"]


# ---------------------------------------------------------------------------
# Integration: the wiring in run_dynamic_rules actually surfaces SCOPE_INERT
# to the verdict path
# ---------------------------------------------------------------------------


async def test_run_dynamic_rules_surfaces_scope_inert_to_verdict(monkeypatch):
    """End-to-end at the call-site level: plant one zero-scope blocking
    rule, drive ``run_dynamic_rules`` (the real entry — not the helper),
    and assert the resulting findings include a SCOPE_INERT BLOCK that
    ``_determine_verdict`` would resolve to FAIL.

    Stubs ``extract_executable_rules`` on the audit-driver module so the
    rule list is controlled without plumbing a full policies+mapping
    fixture. The context stub mirrors what the gate and the per-file
    dispatch path require: ``get_files`` returns [] for every include
    pattern, ``policies`` is an empty dict, and ``enforcement_loader``
    is a no-op MagicMock. The dispatch loop then iterates the planted
    rule, EngineRegistry returns the real ast_gate engine, and
    ``execute_rule`` walks the (empty) file list without finding work —
    leaving the SCOPE_INERT finding from the gate as the only output.
    """
    from mind.governance import constitutional_auditor_dynamic as cad

    planted = ExecutableRule(
        rule_id="test.integration.drifted",
        engine="ast_gate",
        params={},
        enforcement="blocking",
        scope=["src/nonexistent_dir/**/*.py"],
        exclusions=[],
        is_context_level=False,
    )

    monkeypatch.setattr(
        cad,
        "extract_executable_rules",
        lambda policies, loader: [planted],
    )

    # EngineRegistry must be primed before run_dynamic_rules dispatches
    # — otherwise the rule loop emits ENFORCEMENT_FAILURE for the
    # planted rule and noise crowds out the SCOPE_INERT assertion.
    from mind.logic.engines.registry import EngineRegistry
    from shared.path_resolver import PathResolver

    EngineRegistry.initialize(PathResolver(Path("/opt/dev/CORE")))

    ctx = MagicMock()
    ctx.policies = {}
    ctx.enforcement_loader = MagicMock()
    ctx.repo_path = Path("/opt/dev/CORE")
    ctx.get_files.return_value = []
    ctx.force_llm = False

    executed: set[str] = set()
    crashed: set[str] = set()

    findings = await cad.run_dynamic_rules(
        ctx, executed_rule_ids=executed, crashed_rule_ids=crashed
    )

    # The gate emitted exactly one SCOPE_INERT BLOCK finding.
    scope_inert = [
        f
        for f in findings
        if getattr(f, "context", {}).get("finding_type") == "SCOPE_INERT"
    ]
    assert len(scope_inert) == 1
    f = scope_inert[0]
    assert f.check_id == "test.integration.drifted.scope_inert"
    assert f.severity == AuditSeverity.BLOCK

    # The planted rule was still attempted by the dispatch loop — the
    # gate runs IN ADDITION to dispatch, not INSTEAD of it.
    assert "test.integration.drifted" in executed
    assert not crashed

    # Verdict integration: with no crashes, no ignored finding_type
    # carve-out (SCOPE_INERT is not in ENFORCEMENT_FAILURE's exemption),
    # and a BLOCK severity, the verdict resolves to FAIL.
    verdict = ConstitutionalAuditor._determine_verdict(
        findings,
        stats={},
        crashed_rule_ids=crashed,
    )
    assert verdict == AuditVerdict.FAIL
