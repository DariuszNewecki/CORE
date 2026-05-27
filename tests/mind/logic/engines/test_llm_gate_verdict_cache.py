"""ADR-044 — incremental llm_gate verdict cache tests.

Covers the six acceptance conditions from ADR-044 §Implementation guidance #6:

  1. Cache hit on second audit run with no file change.
  2. Cache miss when file content changes between runs.
  3. Cache miss for all files under a rule when the rule's YAML changes.
  4. ``--force-llm`` bypasses the cache READ but still updates verdicts.
  5. Daemon sensor + concurrent ``core-admin code audit`` share verdict rows.
  6. INFO line ``llm_gate cache hit: <rule_id> <file_path>`` is emitted on hit.

Tests exercise the real SQL against core.llm_gate_verdicts. Each test
scopes its rows under a unique rule_id prefix and deletes matching rows
on teardown — no global state survives across tests.

The cache helpers take an injected AsyncSession (ADR-044 + Mind/Body
boundary): Mind layer never opens sessions itself, so tests open one
via ``get_session()`` and pass it in.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import text

from mind.logic.engines.llm_gate import (
    LLMGateEngine,
    _read_cached_verdict,
    _write_cached_verdict,
)
from shared.infrastructure.database.session_manager import get_session


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------


@pytest_asyncio.fixture
# ID: 6e2a9c4b-7f1d-43e5-a092-8c5b3d6f1e9a
async def test_prefix():
    """Unique rule_id prefix per test. Rows under it are wiped on teardown."""
    prefix = f"test_adr044_{uuid.uuid4().hex[:8]}"
    yield prefix
    async with get_session() as session:
        await session.execute(
            text("DELETE FROM core.llm_gate_verdicts WHERE rule_id LIKE :pref"),
            {"pref": f"{prefix}%"},
        )
        await session.commit()


@pytest.fixture
# ID: 7a3d8f5c-2e4b-41a9-b806-9f2c7e1d5a4b
def stub_engine(tmp_path):
    """LLMGateEngine with PromptModel.load patched out so we never touch
    var/prompts. The audit_prompt_model is replaced with an AsyncMock so
    tests can drive its return value or call count.
    """
    fake_prompt = MagicMock()
    fake_prompt.invoke = AsyncMock(
        return_value=json.dumps(
            {"violation": False, "reasoning": "stub", "finding": None}
        )
    )
    with patch(
        "mind.logic.engines.llm_gate.PromptModel.load", return_value=fake_prompt
    ):
        path_resolver = MagicMock()
        path_resolver.repo_root = tmp_path
        engine = LLMGateEngine(path_resolver=path_resolver, llm_client=AsyncMock())
        # Re-stub on the instance so the test always controls the invoke
        # call (the engine reads self._audit_prompt_model directly).
        engine._audit_prompt_model = fake_prompt
        engine._prompt_model = fake_prompt
    return engine


# ID: 8c1d4f9a-2b6e-43c7-9a5d-7e1f4b3c8d2a
async def _seed_verdict(
    *,
    rule_id: str,
    file_path: str,
    file_content_hash: str,
    rule_content_hash: str,
    verdict: str,
    findings: list,
) -> None:
    """Convenience helper: open a session and write a verdict row."""
    async with get_session() as session:
        await _write_cached_verdict(
            session,
            rule_id=rule_id,
            file_path=file_path,
            file_content_hash=file_content_hash,
            rule_content_hash=rule_content_hash,
            verdict=verdict,
            findings=findings,
        )


# ID: 9d2e5f0b-3c7f-44d8-ab6e-8f2a5c4d9e3b
async def _read_verdict(
    *,
    rule_id: str,
    file_path: str,
    file_content_hash: str,
    rule_content_hash: str,
):
    """Convenience helper: open a session and read a verdict row."""
    async with get_session() as session:
        return await _read_cached_verdict(
            session,
            rule_id=rule_id,
            file_path=file_path,
            file_content_hash=file_content_hash,
            rule_content_hash=rule_content_hash,
        )


# ----------------------------------------------------------------------
# Acceptance 1 — Hit on unchanged file
# ----------------------------------------------------------------------


@pytest.mark.asyncio
# ID: 8b4e9a1d-3c2f-4a87-b095-1e6c7f3d8b2a
async def test_acceptance_1_hit_on_unchanged_file(test_prefix: str) -> None:
    """First run writes; second run with identical hashes reads the row back."""
    rule_id = f"{test_prefix}.r1"
    file_path = "tests/_adr044_unchanged.py"
    fch = "file_hash_v1"
    rch = "rule_hash_v1"

    await _seed_verdict(
        rule_id=rule_id,
        file_path=file_path,
        file_content_hash=fch,
        rule_content_hash=rch,
        verdict="PASS",
        findings=[],
    )

    cached = await _read_verdict(
        rule_id=rule_id,
        file_path=file_path,
        file_content_hash=fch,
        rule_content_hash=rch,
    )

    assert cached is not None, "expected cache hit"
    assert cached.ok is True
    assert cached.violations == []
    assert cached.engine_id == "llm_gate"


# ----------------------------------------------------------------------
# Acceptance 2 — Miss when file content changes
# ----------------------------------------------------------------------


@pytest.mark.asyncio
# ID: 9c5f1b2e-4d3a-49b8-a106-2f7d8e4c9b3a
async def test_acceptance_2_miss_when_file_changes(test_prefix: str) -> None:
    """A different file_content_hash for the same (rule_id, file_path) misses."""
    rule_id = f"{test_prefix}.r2"
    file_path = "tests/_adr044_changing.py"
    rch = "rule_hash_v1"

    await _seed_verdict(
        rule_id=rule_id,
        file_path=file_path,
        file_content_hash="fch_before_edit",
        rule_content_hash=rch,
        verdict="PASS",
        findings=[],
    )

    cached = await _read_verdict(
        rule_id=rule_id,
        file_path=file_path,
        file_content_hash="fch_after_edit",  # file changed
        rule_content_hash=rch,
    )

    assert cached is None, "expected cache miss on changed file hash"


# ----------------------------------------------------------------------
# Acceptance 3 — Miss for all files under a rule when YAML changes
# ----------------------------------------------------------------------


@pytest.mark.asyncio
# ID: 1d6a2c3f-5e4b-4ac9-b207-3a8e9f5d1c4b
async def test_acceptance_3_miss_when_rule_changes(test_prefix: str) -> None:
    """Editing a rule's YAML (new rule_content_hash) invalidates every cached
    verdict under that rule, leaving file_content_hash untouched."""
    rule_id = f"{test_prefix}.r3"
    files = [
        ("tests/_adr044_a.py", "fch_a"),
        ("tests/_adr044_b.py", "fch_b"),
        ("tests/_adr044_c.py", "fch_c"),
    ]

    for path, fch in files:
        await _seed_verdict(
            rule_id=rule_id,
            file_path=path,
            file_content_hash=fch,
            rule_content_hash="rule_hash_old",
            verdict="PASS",
            findings=[],
        )

    # Governor edits the rule's YAML — rule_content_hash flips.
    for path, fch in files:
        cached = await _read_verdict(
            rule_id=rule_id,
            file_path=path,
            file_content_hash=fch,
            rule_content_hash="rule_hash_new",
        )
        assert cached is None, f"{path} should miss under rule_hash_new"


# ----------------------------------------------------------------------
# Acceptance 4 — --force-llm bypasses cache READ but still WRITES
# ----------------------------------------------------------------------


@pytest.mark.asyncio
# ID: 2e7b3d4a-6f5c-4abd-c308-4b9a1c6e2d5f
async def test_acceptance_4_force_llm_bypasses_cache(
    test_prefix: str, stub_engine: LLMGateEngine, tmp_path
) -> None:
    """force_llm=True must skip the cache read, dispatch to Ollama, and
    upsert the fresh verdict."""
    rule_id = f"{test_prefix}.r4"

    file_path = tmp_path / "force_subject.py"
    content = "# original\n"
    file_path.write_text(content, encoding="utf-8")
    rel_path = "force_subject.py"

    fch = hashlib.sha256(content.encode("utf-8")).hexdigest()
    rch = "rch_for_test_4"

    # Pre-seed cache with a STALE verdict — force_llm must ignore this.
    await _seed_verdict(
        rule_id=rule_id,
        file_path=rel_path,
        file_content_hash=fch,
        rule_content_hash=rch,
        verdict="FAIL",
        findings=["stale-cached-finding"],
    )

    # Stub LLM returns PASS — distinct from the cached FAIL so we can
    # tell whether the engine consulted the cache or the LLM.
    stub_engine._audit_prompt_model.invoke = AsyncMock(
        return_value=json.dumps(
            {"violation": False, "reasoning": "fresh PASS", "finding": None}
        )
    )

    # The engine reads context.db_session from params['_context'].
    async with get_session() as session:
        mock_context = MagicMock()
        mock_context.db_session = session

        params = {
            "instruction": "irrelevant",
            "_rule_id": rule_id,
            "_rule_content_hash": rch,
            "_force_llm": True,  # the bypass
            "_context": mock_context,
        }

        result = await stub_engine.verify(file_path, params)

    # 4a: LLM was actually called — bypass worked.
    assert stub_engine._audit_prompt_model.invoke.call_count == 1, (
        "force_llm should have driven a fresh LLM call"
    )

    # 4b: Returned verdict is the LIVE one, not the cached FAIL.
    assert result.ok is True, "expected live PASS, not cached FAIL"

    # 4c: Cache row was UPDATED to the new verdict.
    cached_now = await _read_verdict(
        rule_id=rule_id,
        file_path=rel_path,
        file_content_hash=fch,
        rule_content_hash=rch,
    )
    assert cached_now is not None, "cache row missing after force_llm write"
    assert cached_now.ok is True, "cache row should be updated to PASS"


# ----------------------------------------------------------------------
# Acceptance 5 — Daemon + manual audit share verdict rows
# ----------------------------------------------------------------------


@pytest.mark.asyncio
# ID: 3f8c4e5b-7a6d-4abe-d409-5c2b8d7f3e6a
async def test_acceptance_5_shared_between_callers(test_prefix: str) -> None:
    """Caller A writes a verdict; caller B (different process semantically)
    reads it back. The unique constraint prevents duplicate rows under
    concurrent writers."""
    rule_id = f"{test_prefix}.r5"
    file_path = "tests/_adr044_shared.py"
    fch = "fch_shared"
    rch = "rch_shared"

    await _seed_verdict(
        rule_id=rule_id,
        file_path=file_path,
        file_content_hash=fch,
        rule_content_hash=rch,
        verdict="FAIL",
        findings=["docstring missing"],
    )

    cached = await _read_verdict(
        rule_id=rule_id,
        file_path=file_path,
        file_content_hash=fch,
        rule_content_hash=rch,
    )
    assert cached is not None, "second caller should hit the row caller A wrote"
    assert cached.ok is False  # FAIL maps to ok=False
    assert "docstring missing" in cached.violations

    # Second write at the same key — unique constraint + ON CONFLICT
    # collapse races into a single row.
    await _seed_verdict(
        rule_id=rule_id,
        file_path=file_path,
        file_content_hash=fch,
        rule_content_hash=rch,
        verdict="FAIL",
        findings=["docstring missing"],
    )

    async with get_session() as session:
        result = await session.execute(
            text(
                """
                SELECT count(*) FROM core.llm_gate_verdicts
                WHERE rule_id = :rid AND file_path = :fp
                  AND file_content_hash = :fch AND rule_content_hash = :rch
                """
            ),
            {"rid": rule_id, "fp": file_path, "fch": fch, "rch": rch},
        )
        assert result.scalar() == 1, "expected exactly one row at the cache key"


# ----------------------------------------------------------------------
# Acceptance 6 — INFO line emitted on cache hit
# ----------------------------------------------------------------------


@pytest.mark.asyncio
# ID: 4a9d5f6c-8b7e-4abf-e50a-6d3c9e8a4f7b
async def test_acceptance_6_info_log_on_hit(
    test_prefix: str,
    stub_engine: LLMGateEngine,
    tmp_path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Driving verify() through a cache hit emits exactly one
    ``llm_gate cache hit: <rule_id> <rel_path>`` INFO line, and the LLM is
    not called.
    """
    rule_id = f"{test_prefix}.r6"

    file_path = tmp_path / "subject.py"
    content = "def f(): pass\n"
    file_path.write_text(content, encoding="utf-8")
    rel_path = "subject.py"

    fch = hashlib.sha256(content.encode("utf-8")).hexdigest()
    rch = "rch_for_test_6"

    await _seed_verdict(
        rule_id=rule_id,
        file_path=rel_path,
        file_content_hash=fch,
        rule_content_hash=rch,
        verdict="PASS",
        findings=[],
    )

    async with get_session() as session:
        mock_context = MagicMock()
        mock_context.db_session = session

        params = {
            "instruction": "must-not-reach-LLM",
            "_rule_id": rule_id,
            "_rule_content_hash": rch,
            "_force_llm": False,
            "_context": mock_context,
        }

        with caplog.at_level(logging.INFO, logger="mind.logic.engines.llm_gate"):
            result = await stub_engine.verify(file_path, params)

    # The cached PASS verdict was reconstructed.
    assert result.ok is True
    assert result.engine_id == "llm_gate"

    # The LLM was not invoked — the cache short-circuited.
    assert stub_engine._audit_prompt_model.invoke.call_count == 0

    # Exactly one matching INFO line was emitted.
    matches = [
        r
        for r in caplog.records
        if "cache hit" in r.getMessage()
        and rule_id in r.getMessage()
        and rel_path in r.getMessage()
    ]
    assert len(matches) == 1, (
        f"expected one cache-hit INFO line, got {len(matches)}: {[r.getMessage() for r in caplog.records]}"
    )
