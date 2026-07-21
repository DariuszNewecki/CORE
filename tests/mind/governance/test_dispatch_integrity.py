# tests/mind/governance/test_dispatch_integrity.py

"""#820 — dispatch integrity and result truthfulness in the universal sink.

Two ways a rule could enforce nothing while reporting success, both closed
in ``rule_executor`` rather than per-engine, because the executor is the
single path every rule dispatches through.

**Contract 1 — unsupported check_type.** A rule naming a ``check_type`` its
engine cannot dispatch falls through to an empty result. Four
``capability.taxonomy.*`` rules sat blocking-but-inert this way since
``4849af15`` (March 2026), naming a ``capability_taxonomy_whitelist``
handler that never landed. The rules executed, returned nothing, and
reported clean on every audit. #820 Group A implemented the handler
(``KnowledgeGateEngine._check_capability_taxonomy_whitelist``), so these four
now dispatch for real, and Group A's own retire-vs-repair follow-up
demoted ``canonical_only``/``no_ad_hoc_capabilities`` to advisory (removing
their mappings) as near-duplicates of the two precise rules. #820 Group B
reconciled the six ``component_responsibility`` rules the same way: three
retired as advisory historical markers naming their concrete mechanical
successors, three preserved as advisory doctrine with no mechanical
replacement invented — all six mappings removed, so none of them appear in
``KNOWN_UNSUPPORTED`` below either. See
``tests/mind/governance/test_capability_taxonomy_disposition.py`` and
``tests/mind/governance/test_component_responsibility_disposition.py``.

**Contract 2 — failure without evidence.** ``execute_rule`` materialises
findings by iterating ``result.violations``. An engine returning
``ok=False`` with an empty list therefore renders as a clean pass.
ast_gate's own #588 unknown-check_type guard returns exactly that shape,
so that fix has been invisible since it landed.

The mapping sweep at the end is a standing gate: it pins the currently
known drift so a *new* unsupported pair fails the suite. ``KNOWN_UNSUPPORTED``
is now empty — every rule found by the original sweep has been repaired
(action_pattern, capability_taxonomy_whitelist) or reconciled to advisory
with its mapping removed (the two duplicate umbrella rules, the six
component_responsibility rules). A future regression re-populates this set
and the two disposition test files above catch the specific rule.
"""

from __future__ import annotations

import glob
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
import yaml

from mind.governance.executable_rule import ExecutableRule
from mind.governance.rule_executor import declared_check_types, execute_rule
from mind.logic.engines.base import EngineResult
from mind.logic.engines.registry import EngineRegistry
from shared.models import AuditSeverity
from shared.path_resolver import PathResolver


# Repo root derived from this file's location, never hardcoded: the checkout
# path differs between the server and a container mount.
REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module", autouse=True)
def _primed_registry() -> None:
    """The sweep resolves engines through the registry, which needs priming."""
    EngineRegistry.initialize(PathResolver(REPO_ROOT))


# Every rule currently naming a check_type no engine implements. Each entry
# is a live defect awaiting repair, NOT an accepted exception — the pin
# exists so *new* drift fails the suite, not to bless what is here.
#
# Groups, found by the sweep rather than assumed:
#
#   capability_taxonomy_whitelist (4, blocking) — REPAIRED, no longer listed
#     (#820 Group A). Handler never landed after being mapped in 4849af15
#     (March 2026); KnowledgeGateEngine._check_capability_taxonomy_whitelist
#     now implements it. Two of the four (canonical_only, no_ad_hoc_capabilities)
#     were then retired to advisory as near-duplicates of the remaining two
#     precise rules; their mappings are removed, not repaired.
#   component_responsibility (6, reporting) — RECONCILED, no longer listed
#     (#820 Group B). Doubly dark while inert: knowledge_gate is partitioned
#     out of stateless mode, so these never ran in CI either. Three retired
#     as advisory historical markers naming their concrete mechanical
#     successors (architecture.layers.no_mind_execution,
#     architecture.will.must_delegate_to_body,
#     architecture.api.must_route_through_will); three preserved as advisory
#     doctrine with no mechanical replacement invented
#     (architecture.shared.no_strategic_decisions,
#     infrastructure.no_business_logic, infrastructure.no_strategic_decisions).
#     All six mappings removed rather than repaired — "strategic decision"
#     and "business logic" are semantic judgments, not patterns a check_type
#     could mechanically verify.
#   action_pattern (1, BLOCKING, ast_gate) — REPAIRED, no longer listed. It
#     was the serious one: ast_gate runs in stateless mode, so unlike the
#     others this rule was reached on every CI audit and silently returned
#     nothing, via ast_gate's own #588 guard being swallowed by the executor.
#     The remap onto `required_decorator` + `write_defaults_false` was
#     investigated and rejected — `write_defaults_false` dispatches but has no
#     validator branch (it would enforce nothing, silently), and
#     `required_decorator` is a mutating-args heuristic with different
#     semantics. Repaired instead by implementing the check_type in ast_gate;
#     see tests/mind/logic/engines/ast_gate/test_action_pattern_check.py.
KNOWN_UNSUPPORTED: frozenset[tuple[str, str, str]] = frozenset()


def _mapped_check_type_pairs() -> list[tuple[str, str, str]]:
    """Yield every (rule_id, engine, check_type) declared in the enforcement mappings."""
    pairs: list[tuple[str, str, str]] = []
    root = REPO_ROOT / ".intent" / "enforcement" / "mappings"
    for path in glob.glob(str(root / "**" / "*.yaml"), recursive=True):
        doc = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        mappings = doc.get("mappings") or doc
        if not isinstance(mappings, dict):
            continue
        for rule_id, cfg in mappings.items():
            if not isinstance(cfg, dict):
                continue
            engine = cfg.get("engine")
            check_type = (cfg.get("params") or {}).get("check_type")
            if isinstance(engine, str) and isinstance(check_type, str):
                pairs.append((rule_id, engine, check_type))
    return pairs


def _unsupported_pairs() -> set[tuple[str, str, str]]:
    """Return mapped pairs whose engine publishes a vocabulary excluding the check_type."""
    unsupported: set[tuple[str, str, str]] = set()
    for rule_id, engine_id, check_type in _mapped_check_type_pairs():
        # Never `continue` past an unresolvable engine: swallowing it is how
        # this sweep would quietly check nothing at all — the precise failure
        # mode this module exists to prevent.
        engine = EngineRegistry.get(engine_id)
        declared = declared_check_types(engine)
        if declared is not None and check_type not in declared:
            unsupported.add((rule_id, engine_id, check_type))
    return unsupported


def test_mappings_declare_no_new_unsupported_check_type() -> None:
    """Standing gate: no mapping may name a check_type its engine cannot dispatch.

    Failure here means either a new rule was mapped to a nonexistent handler,
    or an engine dropped a check_type its rules still reference.
    """
    pairs = _mapped_check_type_pairs()
    assert pairs, "no (engine, check_type) pairs found — the sweep is vacuous"
    unsupported = _unsupported_pairs()
    new_drift = unsupported - KNOWN_UNSUPPORTED
    assert not new_drift, (
        "Rules map to check_types their engine does not implement, so they "
        f"enforce nothing: {sorted(new_drift)}"
    )


def test_known_unsupported_set_is_not_stale() -> None:
    """The pinned defects must still be real — a repaired rule has to leave the pin.

    Guards the opposite drift from the test above: if #820 step 2 repairs a
    rule but leaves it listed here, this fails and forces the bookkeeping.
    """
    unsupported = _unsupported_pairs()
    repaired = KNOWN_UNSUPPORTED - unsupported
    assert not repaired, (
        "These rules no longer name an unsupported check_type — remove them "
        f"from KNOWN_UNSUPPORTED: {sorted(repaired)}"
    )


def test_inert_rule_inventory_is_exactly_as_recorded() -> None:
    """Pin the inventory: zero rules with an unsupported check_type.

    The sweep originally found eleven. `architecture.patterns.action_pattern`
    was repaired first (ast_gate). #820 Group A implemented
    `capability_taxonomy_whitelist` for the two precise rules and retired
    the two duplicate umbrella rules (`canonical_only`,
    `no_ad_hoc_capabilities`) to advisory, removing their mappings. #820
    Group B reconciled the six `component_responsibility` rules the same
    way — three retired as advisory historical markers, three preserved as
    advisory doctrine — all six mappings removed rather than repaired.
    Zero unsupported (rule, engine, check_type) pairs remain anywhere.
    """
    unsupported = _unsupported_pairs()
    assert unsupported == set(KNOWN_UNSUPPORTED)
    assert len(unsupported) == 0


def _context(tmp_path: Path) -> Any:
    ctx = MagicMock()
    ctx.repo_path = tmp_path
    ctx.force_llm = False
    return ctx


@pytest.mark.asyncio
async def test_unsupported_check_type_produces_block_finding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Contract 1: an unimplemented check_type is a BLOCK verdict, not silence."""

    class _DeclaringEngine:
        engine_id = "knowledge_gate"

        @classmethod
        def supported_check_types(cls) -> set[str]:
            return {"duplicate_ids"}

        async def verify_context(self, *_a: Any, **_k: Any) -> list[Any]:
            raise AssertionError("dispatch must be refused before the engine runs")

    monkeypatch.setattr(
        EngineRegistry, "get", classmethod(lambda cls, _id: _DeclaringEngine())
    )

    rule = ExecutableRule(
        rule_id="capability.taxonomy.canonical_only",
        engine="knowledge_gate",
        params={"check_type": "capability_taxonomy_whitelist"},
        enforcement="blocking",
        scope=[],
        exclusions=[],
        is_context_level=True,
    )
    findings = await execute_rule(rule, _context(tmp_path))

    assert len(findings) == 1
    finding = findings[0]
    assert finding.severity is AuditSeverity.BLOCK
    assert finding.context["finding_type"] == "ENFORCEMENT_FAILURE"
    assert finding.context["declared_check_type"] == "capability_taxonomy_whitelist"
    assert "does not implement" in finding.message


@pytest.mark.asyncio
async def test_supported_check_type_still_dispatches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The guard must not block engines whose check_type is declared."""
    dispatched: list[str] = []

    class _DeclaringEngine:
        engine_id = "knowledge_gate"

        @classmethod
        def supported_check_types(cls) -> set[str]:
            return {"duplicate_ids"}

        async def verify_context(self, *_a: Any, **_k: Any) -> list[Any]:
            dispatched.append("yes")
            return []

    monkeypatch.setattr(
        EngineRegistry, "get", classmethod(lambda cls, _id: _DeclaringEngine())
    )

    rule = ExecutableRule(
        rule_id="linkage.duplicate_ids",
        engine="knowledge_gate",
        params={"check_type": "duplicate_ids"},
        enforcement="blocking",
        scope=[],
        exclusions=[],
        is_context_level=True,
    )
    findings = await execute_rule(rule, _context(tmp_path))

    assert dispatched == ["yes"]
    assert findings == []


@pytest.mark.asyncio
async def test_missing_check_type_produces_block_finding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Contract 1, missing-name edge: no check_type at all must also BLOCK.

    The first cut guarded only `check_type not in declared`, so `None` walked
    straight past it. Against a context-level engine that reaches
    verify_context(), whose empty result is indistinguishable from a clean
    pass — the per-file ok=False/violations=[] contract cannot see it. This is
    the same fail-open shape #820 exists to close, one layer up.
    """

    class _DeclaringEngine:
        engine_id = "knowledge_gate"

        @classmethod
        def supported_check_types(cls) -> set[str]:
            return {"duplicate_ids"}

        async def verify_context(self, *_a: Any, **_k: Any) -> list[Any]:
            raise AssertionError("dispatch must be refused before the engine runs")

    monkeypatch.setattr(
        EngineRegistry, "get", classmethod(lambda cls, _id: _DeclaringEngine())
    )

    rule = ExecutableRule(
        rule_id="some.rule.without.a.check_type",
        engine="knowledge_gate",
        params={},
        enforcement="blocking",
        scope=[],
        exclusions=[],
        is_context_level=True,
    )
    findings = await execute_rule(rule, _context(tmp_path))

    assert len(findings) == 1
    finding = findings[0]
    assert finding.severity is AuditSeverity.BLOCK
    assert finding.context["finding_type"] == "ENFORCEMENT_FAILURE"
    assert finding.context["declared_check_type"] is None
    assert "declares no check_type" in finding.message


@pytest.mark.asyncio
async def test_vocabulary_accessor_failure_produces_block_finding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fail-closed discovery: a raising accessor must BLOCK, not opt out.

    Returning None on error read as "declares no vocabulary", which exempts
    the engine from validation entirely — the contract disabling itself at
    precisely the moment something is wrong with the engine.
    """

    class _BrokenVocabularyEngine:
        engine_id = "knowledge_gate"

        @classmethod
        def supported_check_types(cls) -> set[str]:
            raise RuntimeError("registry unavailable")

        async def verify_context(self, *_a: Any, **_k: Any) -> list[Any]:
            raise AssertionError("dispatch must be refused before the engine runs")

    monkeypatch.setattr(
        EngineRegistry, "get", classmethod(lambda cls, _id: _BrokenVocabularyEngine())
    )

    rule = ExecutableRule(
        rule_id="some.rule",
        engine="knowledge_gate",
        params={"check_type": "duplicate_ids"},
        enforcement="blocking",
        scope=[],
        exclusions=[],
        is_context_level=True,
    )
    findings = await execute_rule(rule, _context(tmp_path))

    assert len(findings) == 1
    finding = findings[0]
    assert finding.severity is AuditSeverity.BLOCK
    assert finding.context["finding_type"] == "ENFORCEMENT_FAILURE"
    assert "registry unavailable" in finding.context["vocabulary_error"]
    assert "could not publish" in finding.message


# ID: 97b8300c-7fe4-4c62-b3e3-959026bc173f
def test_empty_declared_vocabulary_is_a_declaration() -> None:
    """An engine declaring an empty vocabulary declares one — it is not absent.

    Truthiness-testing the ClassVar collapsed "dispatches no named check_type"
    into "publishes no contract", handing a fully-inert engine the exemption
    meant for engines that never opted in.
    """

    class _EmptyVocabularyEngine:
        _SUPPORTED_CHECK_TYPES: frozenset[str] = frozenset()

    assert declared_check_types(_EmptyVocabularyEngine()) == frozenset()


# ID: 3f7b2d90-6a15-48ce-b304-9e2d7c015b8a
def test_engine_publishing_no_vocabulary_returns_none() -> None:
    """The opt-in escape hatch survives: no accessor, no ClassVar, no contract."""

    class _NoVocabularyEngine:
        pass

    assert declared_check_types(_NoVocabularyEngine()) is None


@pytest.mark.asyncio
async def test_engine_declaring_nothing_is_not_validated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Opt-in contract: an engine publishing no vocabulary keeps its current behaviour."""
    dispatched: list[str] = []

    class _SilentEngine:
        engine_id = "taxonomy_gate"

        async def verify_context(self, *_a: Any, **_k: Any) -> list[Any]:
            dispatched.append("yes")
            return []

    monkeypatch.setattr(
        EngineRegistry, "get", classmethod(lambda cls, _id: _SilentEngine())
    )

    rule = ExecutableRule(
        rule_id="some.rule",
        engine="taxonomy_gate",
        params={"check_type": "anything_at_all"},
        enforcement="blocking",
        scope=[],
        exclusions=[],
        is_context_level=True,
    )
    findings = await execute_rule(rule, _context(tmp_path))

    assert dispatched == ["yes"]
    assert findings == []


@pytest.mark.asyncio
async def test_failure_without_violations_produces_block_finding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Contract 2: ok=False with no violations must surface, not vanish.

    This is the exact shape ast_gate's #588 unknown-check_type guard returns.
    """
    target = tmp_path / "sample.py"
    target.write_text("x = 1\n", encoding="utf-8")

    class _FailingEngine:
        engine_id = "ast_gate"
        evidence_class = None

        async def verify(self, *_a: Any, **_k: Any) -> EngineResult:
            return EngineResult(
                ok=False,
                message="Logic Error: Unknown check_type 'bogus'",
                violations=[],
                engine_id="ast_gate",
            )

    monkeypatch.setattr(
        EngineRegistry, "get", classmethod(lambda cls, _id: _FailingEngine())
    )

    ctx = _context(tmp_path)
    ctx.get_files = MagicMock(return_value=[target])

    rule = ExecutableRule(
        rule_id="some.per_file.rule",
        engine="ast_gate",
        params={"check_type": "bogus"},
        enforcement="reporting",
        scope=["**/*.py"],
        exclusions=[],
        is_context_level=False,
    )
    findings = await execute_rule(rule, ctx)

    assert len(findings) == 1
    finding = findings[0]
    # BLOCK regardless of the rule's own `reporting` tier: an engine that
    # cannot substantiate a failure is an enforcement failure, not a
    # low-severity observation. Mirrors the existing per-file crash handler.
    assert finding.severity is AuditSeverity.BLOCK
    assert finding.context["finding_type"] == "ENFORCEMENT_FAILURE"
    assert "Unknown check_type" in finding.message


@pytest.mark.asyncio
async def test_failure_with_violations_is_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A substantiated failure keeps the rule's own severity and message."""
    target = tmp_path / "sample.py"
    target.write_text("x = 1\n", encoding="utf-8")

    class _ViolatingEngine:
        engine_id = "ast_gate"
        evidence_class = None

        async def verify(self, *_a: Any, **_k: Any) -> EngineResult:
            return EngineResult(
                ok=False,
                message="found something",
                violations=["Line 1: real violation"],
                engine_id="ast_gate",
            )

    monkeypatch.setattr(
        EngineRegistry, "get", classmethod(lambda cls, _id: _ViolatingEngine())
    )

    ctx = _context(tmp_path)
    ctx.get_files = MagicMock(return_value=[target])

    rule = ExecutableRule(
        rule_id="some.per_file.rule",
        engine="ast_gate",
        params={"check_type": "real_check"},
        enforcement="reporting",
        scope=["**/*.py"],
        exclusions=[],
        is_context_level=False,
    )
    findings = await execute_rule(rule, ctx)

    assert len(findings) == 1
    assert findings[0].severity is AuditSeverity.INFO  # reporting tier preserved
    assert "real violation" in findings[0].message
    assert findings[0].context.get("finding_type") != "ENFORCEMENT_FAILURE"
