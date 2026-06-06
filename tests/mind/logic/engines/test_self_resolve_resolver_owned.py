"""Unit tests for ADR-091 D2 Revision B (d) resolver-ownership invariant check.

The rule statement: every distinct subject prefix appearing on a
``post_finding(..., resolution_mechanism='self_resolve')`` call site in
``src/`` MUST be backed by (1) a documented resolver path in the emitting
worker's module docstring (the canonical
``"ADR-091 D2 Revision B resolution classification:"`` block) AND (2) at
least one test under ``tests/`` that references the subject prefix as a
string.

The engine is the ``governance.taxonomy.self_resolve_resolver_owned``
check_type on ``TaxonomyGateEngine`` — context-level dispatch via
``verify_context``. Substrate is a synthetic ``src/`` + ``tests/`` skeleton
under tmp_path. Tests pin: clean tree (both conditions met) → zero
findings; missing docstring block → one finding; missing test reference →
one finding; subject derived from local-variable f-string with a
module-level prefix constant → prefix is correctly traced; untraceable
sites are skipped (no finding, per the design's conservative trace).
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest

from mind.logic.engines.taxonomy_gate import TaxonomyGateEngine
from shared.path_resolver import PathResolver


_CHECK_TYPE = "self_resolve_resolver_owned"

_CANONICAL_DOCSTRING = '''"""Worker module.

ADR-091 D2 Revision B resolution classification:
- Subject prefix:        worker.silent::<worker_uuid>
- resolution_mechanism:  self_resolve
- Resolver path:         this worker's own run() method.
"""
'''


def _fake_context(repo_root: Path) -> SimpleNamespace:
    return SimpleNamespace(repo_path=repo_root)


def _engine(repo: Path) -> TaxonomyGateEngine:
    return TaxonomyGateEngine(path_resolver=PathResolver(repo_root=repo))


def _write_emitter(
    repo: Path,
    *,
    relative_path: str = "will/workers/worker_shop_manager.py",
    docstring: str = _CANONICAL_DOCSTRING,
    body: str | None = None,
) -> Path:
    """Lay down src/<relative_path> with the given docstring + body. Returns
    the full file path. Default body posts worker.silent::<uuid> with
    self_resolve, tracing through a module-level prefix constant — the
    surviving-tree shape the engine is most often going to see."""
    target = repo / "src" / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    if body is None:
        body = textwrap.dedent(
            """
            _FINDING_SUBJECT = "worker.silent"

            class WorkerShopManager:
                async def run(self):
                    worker_uuid = "abc"
                    subject = f"{_FINDING_SUBJECT}::{worker_uuid}"
                    await self.post_finding(
                        subject=subject,
                        payload={},
                        resolution_mechanism="self_resolve",
                    )
            """
        )
    target.write_text(docstring + body, encoding="utf-8")
    return target


def _write_test(
    repo: Path,
    *,
    relative_path: str = "will/workers/test_resolver_coverage.py",
    references_prefix: str = "worker.silent",
) -> Path:
    """Lay down tests/<relative_path> referencing the subject prefix."""
    target = repo / "tests" / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        textwrap.dedent(
            f"""
            def test_worker_silent_resolution():
                # References '{references_prefix}::' so the prefix appears in source.
                subject_prefix = "{references_prefix}"
                assert subject_prefix
            """
        ),
        encoding="utf-8",
    )
    return target


def test_is_context_level_for_self_resolve_check() -> None:
    assert TaxonomyGateEngine.is_context_level_for(_CHECK_TYPE) is True


@pytest.mark.asyncio
async def test_clean_tree_yields_no_findings(tmp_path: Path) -> None:
    """Emitter carries the canonical docstring block AND a test file
    references the subject prefix → zero findings."""
    _write_emitter(tmp_path)
    _write_test(tmp_path)
    findings = await _engine(tmp_path).verify_context(
        _fake_context(tmp_path), {"check_type": _CHECK_TYPE}
    )
    assert findings == []


@pytest.mark.asyncio
async def test_missing_docstring_block_flags_finding(tmp_path: Path) -> None:
    """Emitter has a docstring but lacks the canonical block → one finding
    citing the docstring gap. Test file is present so test coverage is OK."""
    _write_emitter(
        tmp_path,
        docstring='"""Just a normal module docstring with no resolver block."""\n',
    )
    _write_test(tmp_path)
    findings = await _engine(tmp_path).verify_context(
        _fake_context(tmp_path), {"check_type": _CHECK_TYPE}
    )
    assert len(findings) == 1
    f = findings[0]
    assert "worker.silent" in f.message
    assert "docstring" in f.message
    assert f.context["missing_docstring_block"] is True
    assert f.context["missing_test_coverage"] is False
    assert f.context["subject_prefix"] == "worker.silent"


@pytest.mark.asyncio
async def test_missing_test_coverage_flags_finding(tmp_path: Path) -> None:
    """Emitter docstring is fine but no tests/ file references the prefix
    → one finding citing the test gap."""
    _write_emitter(tmp_path)
    # No test file written.
    findings = await _engine(tmp_path).verify_context(
        _fake_context(tmp_path), {"check_type": _CHECK_TYPE}
    )
    assert len(findings) == 1
    f = findings[0]
    assert "worker.silent" in f.message
    assert "test" in f.message
    assert f.context["missing_docstring_block"] is False
    assert f.context["missing_test_coverage"] is True


@pytest.mark.asyncio
async def test_both_gaps_collapse_into_single_finding(tmp_path: Path) -> None:
    """A prefix missing BOTH docstring and test should still emit exactly
    one finding (per-prefix, not per-gap), with both context flags True."""
    _write_emitter(
        tmp_path,
        docstring='"""No resolver block."""\n',
    )
    # No test file.
    findings = await _engine(tmp_path).verify_context(
        _fake_context(tmp_path), {"check_type": _CHECK_TYPE}
    )
    assert len(findings) == 1
    f = findings[0]
    assert f.context["missing_docstring_block"] is True
    assert f.context["missing_test_coverage"] is True
    assert "and" in f.message  # both gaps listed


@pytest.mark.asyncio
async def test_inline_literal_subject_traces_prefix(tmp_path: Path) -> None:
    """When the subject is built inline as f"literal::{id}" (no module
    constant), the prefix is taken as the literal head before the first
    `::`. The current shop-manager pattern uses a module constant, but
    this branch covers a simpler shape someone might write."""
    _write_emitter(
        tmp_path,
        body=textwrap.dedent(
            """
            class Probe:
                async def run(self):
                    entry_id = "x"
                    await self.post_finding(
                        subject=f"literal.prefix::{entry_id}",
                        payload={},
                        resolution_mechanism="self_resolve",
                    )
            """
        ),
    )
    _write_test(tmp_path, references_prefix="literal.prefix")
    findings = await _engine(tmp_path).verify_context(
        _fake_context(tmp_path), {"check_type": _CHECK_TYPE}
    )
    assert findings == []


@pytest.mark.asyncio
async def test_untraceable_subject_is_skipped(tmp_path: Path) -> None:
    """A subject derived from a function parameter (no module constant, no
    f-string head we can trace) is not classified — by design the engine
    skips it rather than emitting a "untraceable" finding. The shape is
    rare in the surviving tree; future hardening can promote untraceable
    sites to their own finding class (issue #575 follow-up territory)."""
    _write_emitter(
        tmp_path,
        body=textwrap.dedent(
            """
            class Probe:
                async def run(self, subject_from_arg):
                    await self.post_finding(
                        subject=subject_from_arg,
                        payload={},
                        resolution_mechanism="self_resolve",
                    )
            """
        ),
    )
    findings = await _engine(tmp_path).verify_context(
        _fake_context(tmp_path), {"check_type": _CHECK_TYPE}
    )
    # No prefix → no entry in site_map → no finding.
    assert findings == []


@pytest.mark.asyncio
async def test_reaudit_post_finding_is_ignored(tmp_path: Path) -> None:
    """post_finding with resolution_mechanism='reaudit' (or anything other
    than 'self_resolve') is out of scope — those are governed by
    architecture.blackboard.reaudit_requires_reaudit_mechanism instead."""
    _write_emitter(
        tmp_path,
        body=textwrap.dedent(
            """
            _FINDING_SUBJECT = "python"

            class Probe:
                async def run(self):
                    sub = f"{_FINDING_SUBJECT}::audit.violation::x"
                    await self.post_finding(
                        subject=sub,
                        payload={},
                        resolution_mechanism="reaudit",
                    )
            """
        ),
    )
    findings = await _engine(tmp_path).verify_context(
        _fake_context(tmp_path), {"check_type": _CHECK_TYPE}
    )
    assert findings == []
