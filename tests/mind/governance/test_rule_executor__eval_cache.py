# tests/mind/governance/test_rule_executor__eval_cache.py
"""ADR-039 Option F — evaluation-level cache in rule_executor.

Proves the content-identity cache skips engine.verify() for unchanged
(rule, file) pairs and re-evaluates correctly on any change:

- cache hit skips verify() on second cycle
- file-content change (mtime_ns/size) invalidates the entry
- rule_content_hash change invalidates the entry
- llm_gate engine is excluded from caching
- empty rule_content_hash is excluded from caching
- transient LLM failures are never cached
- ENFORCEMENT_FAILURE (engine crash) is never cached
- a clean file is cached as an empty findings list
- clear_eval_cache() resets all entries
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from mind.governance.executable_rule import ExecutableRule
from mind.governance.rule_executor import (
    _TRANSIENT_LLM_FAILURE_MARKER,
    clear_eval_cache,
    execute_rule,
)
from mind.logic.engines.base import BaseEngine, EngineResult
from shared.models import EvidenceClass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_eval_cache() -> None:
    """Ensure every test starts with a cold cache."""
    clear_eval_cache()
    yield
    clear_eval_cache()


# ID: c0e67f3e-af87-4957-a377-708a33a83ff2
class _CountingEngine(BaseEngine):
    """Engine that counts verify() calls and returns a configurable result."""

    engine_id = "fake_counting"
    evidence_class = EvidenceClass.PROVEN

    def __init__(
        self, violations: list[str] | None = None, *, crash: bool = False
    ) -> None:
        self.call_count = 0
        self._violations = violations or []
        self._crash = crash

    async def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        self.call_count += 1
        if self._crash:
            raise RuntimeError("boom")
        ok = not self._violations
        return EngineResult(ok, "x", list(self._violations), self.engine_id)


def _make_context(repo_path: Path, files: list[Path]) -> Any:
    ctx = MagicMock()
    ctx.repo_path = repo_path
    ctx.force_llm = False
    ctx.get_files.return_value = files
    return ctx


def _make_rule(
    *,
    rule_id: str = "test.rule",
    engine: str = "fake_counting",
    rule_content_hash: str = "abc123",
) -> ExecutableRule:
    return ExecutableRule(
        rule_id=rule_id,
        engine=engine,
        params={},
        enforcement="blocking",
        scope=["**/*.py"],
        rule_content_hash=rule_content_hash,
    )


def _patch_engine(monkeypatch: pytest.MonkeyPatch, engine: BaseEngine) -> None:
    monkeypatch.setattr(
        "mind.logic.engines.registry.EngineRegistry.get",
        lambda engine_id: engine,
    )


# ---------------------------------------------------------------------------
# Cache hit / miss behaviour
# ---------------------------------------------------------------------------


async def test_cache_hit_skips_verify_on_second_call(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Second call with identical (rule, file, content) must not invoke verify()."""
    target = tmp_path / "module.py"
    target.write_text("x = 1")

    engine = _CountingEngine()
    _patch_engine(monkeypatch, engine)

    rule = _make_rule()
    ctx = _make_context(tmp_path, [target])

    await execute_rule(rule, ctx)
    await execute_rule(rule, ctx)

    assert engine.call_count == 1, "verify() must be skipped on cache hit"


async def test_cache_miss_on_file_content_change(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Changing file content (mtime_ns changes) must invalidate the cache entry."""
    target = tmp_path / "module.py"
    target.write_text("x = 1")

    engine = _CountingEngine()
    _patch_engine(monkeypatch, engine)

    rule = _make_rule()
    ctx = _make_context(tmp_path, [target])

    await execute_rule(rule, ctx)

    # Write content of a DIFFERENT LENGTH so st_size changes — this guarantees
    # cache invalidation regardless of mtime resolution or event-loop timing.
    # "x = 1" is 5 bytes; "x = 2  # changed" is longer, making size the
    # reliable distinguisher under load when mtime may not advance.
    await asyncio.sleep(0)
    target.write_text("x = 2  # changed")

    await execute_rule(rule, ctx)

    assert engine.call_count == 2, "verify() must re-run after file content changes"


async def test_cache_miss_on_rule_hash_change(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A changed rule_content_hash must invalidate the cache entry."""
    target = tmp_path / "module.py"
    target.write_text("x = 1")

    engine = _CountingEngine()
    _patch_engine(monkeypatch, engine)

    ctx = _make_context(tmp_path, [target])

    await execute_rule(_make_rule(rule_content_hash="hash-v1"), ctx)
    await execute_rule(_make_rule(rule_content_hash="hash-v2"), ctx)

    assert engine.call_count == 2, "verify() must re-run when rule definition changes"


async def test_clean_file_cached_as_empty_findings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A file with no violations must be cached (second call returns [] without verify())."""
    target = tmp_path / "clean.py"
    target.write_text("x = 1")

    engine = _CountingEngine(violations=[])
    _patch_engine(monkeypatch, engine)

    rule = _make_rule()
    ctx = _make_context(tmp_path, [target])

    first = await execute_rule(rule, ctx)
    second = await execute_rule(rule, ctx)

    assert first == []
    assert second == []
    assert engine.call_count == 1, "clean file must be cached and not re-verified"


# ---------------------------------------------------------------------------
# Cache exclusions
# ---------------------------------------------------------------------------


async def test_llm_gate_engine_bypasses_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """llm_gate engine must never hit the evaluation cache."""
    target = tmp_path / "doc.py"
    target.write_text("x = 1")

    engine = _CountingEngine()
    _patch_engine(monkeypatch, engine)

    # engine name "llm_gate" triggers the exclusion regardless of the engine object.
    rule = _make_rule(engine="llm_gate")
    ctx = _make_context(tmp_path, [target])

    await execute_rule(rule, ctx)
    await execute_rule(rule, ctx)

    assert engine.call_count == 2, "llm_gate must not be served from eval cache"


async def test_empty_rule_hash_bypasses_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An empty rule_content_hash disables caching (hash is not trustworthy)."""
    target = tmp_path / "module.py"
    target.write_text("x = 1")

    engine = _CountingEngine()
    _patch_engine(monkeypatch, engine)

    rule = _make_rule(rule_content_hash="")
    ctx = _make_context(tmp_path, [target])

    await execute_rule(rule, ctx)
    await execute_rule(rule, ctx)

    assert engine.call_count == 2, "empty rule_content_hash must bypass the cache"


# ---------------------------------------------------------------------------
# Results that must never be cached
# ---------------------------------------------------------------------------


async def test_transient_llm_failure_not_cached(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Transient LLM failure results must not be stored; next cycle must re-verify."""
    target = tmp_path / "module.py"
    target.write_text("x = 1")

    transient_engine = _CountingEngine(violations=[_TRANSIENT_LLM_FAILURE_MARKER])
    _patch_engine(monkeypatch, transient_engine)

    rule = _make_rule()
    ctx = _make_context(tmp_path, [target])

    await execute_rule(rule, ctx)
    await execute_rule(rule, ctx)

    assert transient_engine.call_count == 2, (
        "transient failure must force re-evaluation"
    )


async def test_enforcement_failure_not_cached(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An engine crash (ENFORCEMENT_FAILURE) must not be cached."""
    target = tmp_path / "module.py"
    target.write_text("x = 1")

    crash_engine = _CountingEngine(crash=True)
    _patch_engine(monkeypatch, crash_engine)

    rule = _make_rule()
    ctx = _make_context(tmp_path, [target])

    await execute_rule(rule, ctx)
    await execute_rule(rule, ctx)

    assert crash_engine.call_count == 2, (
        "ENFORCEMENT_FAILURE must not be served from cache"
    )


# ---------------------------------------------------------------------------
# clear_eval_cache()
# ---------------------------------------------------------------------------


async def test_clear_eval_cache_forces_full_reeval(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """clear_eval_cache() must cause the next call to re-verify all files."""
    target = tmp_path / "module.py"
    target.write_text("x = 1")

    engine = _CountingEngine()
    _patch_engine(monkeypatch, engine)

    rule = _make_rule()
    ctx = _make_context(tmp_path, [target])

    await execute_rule(rule, ctx)
    clear_eval_cache()
    await execute_rule(rule, ctx)

    assert engine.call_count == 2, "verify() must re-run after clear_eval_cache()"
