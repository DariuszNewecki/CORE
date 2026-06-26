"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/mind/logic/engines/llm_gate.py
- Symbol: LLMGateEngine
- Status: verified_in_sandbox
- Generated: 2026-01-11 02:22:45
- 2026-06-07 (#572 Cat B batch 5):
    * signatures realigned for path_resolver DI
    * tmp paths moved under var/tmp/ per CLAUDE.md (no /tmp/ writes)
    * boundary shift: source's verify() invokes self._audit_prompt_model.invoke()
      (which internally consults self.llm). The autogen vintage mocked
      self.llm.make_request — a call site that no longer exists on the
      Mind-layer engine. Each test now replaces ._audit_prompt_model with a
      MagicMock exposing AsyncMock invoke()
    * cache-hit test reframed: ADR-044 routes the cache through a DB
      session injected via params['_context'].db_session — without that
      plumbing cache_eligible is False and every verify() call re-invokes
      the prompt model. The test now pins that bare-params calls are NOT
      cached (rather than asserting the obsolete in-memory cache behavior)
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from mind.logic.engines.llm_gate import LLMGateEngine
from shared.path_resolver import PathResolver

pytestmark = [pytest.mark.integration]

_REPO_ROOT = Path("/opt/dev/CORE")


@pytest.fixture
def path_resolver():
    """Real PathResolver at the repo root. The engine reads ``.repo_root``
    during verify() to compute a display rel_path; no state is mutated."""
    return PathResolver(repo_root=_REPO_ROOT)


@pytest.fixture
def tmp_py_file():
    """Per-test source file under var/tmp/ (CLAUDE.md prohibits /tmp/)."""
    repo_tmp = _REPO_ROOT / "var" / "tmp"
    repo_tmp.mkdir(parents=True, exist_ok=True)
    p = repo_tmp / f"llm_gate_test_{uuid.uuid4().hex}.py"
    yield p
    p.unlink(missing_ok=True)


def _engine_with_mocked_prompt(
    path_resolver, invoke_return_value=None, invoke_side_effect=None
):
    """Construct an LLMGateEngine and replace its ``_audit_prompt_model``
    with a mock exposing AsyncMock invoke(). Returns (engine, invoke_mock).

    The engine's prompt-model is initialised in __init__ via PromptModel.load(),
    which loads the real prompt YAML from disk; tests don't exercise the
    template path so we substitute the mock immediately after construction.
    self.llm is left as a bare Mock — verify() forwards it to invoke() but
    the mock invoke ignores the argument."""
    invoke_kwargs = {}
    if invoke_return_value is not None:
        invoke_kwargs["return_value"] = invoke_return_value
    if invoke_side_effect is not None:
        invoke_kwargs["side_effect"] = invoke_side_effect
    invoke_mock = AsyncMock(**invoke_kwargs)
    engine = LLMGateEngine(path_resolver=path_resolver, llm_client=Mock())
    engine._audit_prompt_model = MagicMock(invoke=invoke_mock)
    return engine, invoke_mock


async def test_verify_successful_no_violation(path_resolver, tmp_py_file):
    """Verification with a non-violation LLM response → ok=True, no violations."""
    engine, invoke_mock = _engine_with_mocked_prompt(
        path_resolver,
        invoke_return_value=json.dumps(
            {"violation": False, "reasoning": "Code follows the rule", "finding": None}
        ),
    )
    tmp_py_file.write_text("def foo(): pass", encoding="utf-8")
    params = {
        "instruction": "Functions must have docstrings",
        "rationale": "Documentation is important",
    }

    result = await engine.verify(tmp_py_file, params)

    assert result.ok
    assert result.message == "Semantic adherence verified."
    assert result.violations == []
    assert result.engine_id == "llm_gate"
    invoke_mock.assert_awaited_once()


async def test_verify_successful_with_violation(path_resolver, tmp_py_file):
    """Verification with a violation LLM response → ok=False, finding propagated."""
    engine, _ = _engine_with_mocked_prompt(
        path_resolver,
        invoke_return_value=json.dumps(
            {
                "violation": True,
                "reasoning": "Function lacks docstring",
                "finding": "Missing documentation",
            }
        ),
    )
    tmp_py_file.write_text("def foo(): pass", encoding="utf-8")
    params = {
        "instruction": "Functions must have docstrings",
        "rationale": "Documentation is important",
    }

    result = await engine.verify(tmp_py_file, params)

    assert not result.ok
    assert result.message == "Semantic Violation: Function lacks docstring"
    assert result.violations == ["Missing documentation"]
    assert result.engine_id == "llm_gate"


async def test_verify_with_violation_no_finding(path_resolver, tmp_py_file):
    """Violation True but finding None → ok=False, empty violations list."""
    engine, _ = _engine_with_mocked_prompt(
        path_resolver,
        invoke_return_value=json.dumps(
            {
                "violation": True,
                "reasoning": "Function lacks docstring",
                "finding": None,
            }
        ),
    )
    tmp_py_file.write_text("def foo(): pass", encoding="utf-8")
    params = {
        "instruction": "Functions must have docstrings",
        "rationale": "Documentation is important",
    }

    result = await engine.verify(tmp_py_file, params)

    assert not result.ok
    assert result.message == "Semantic Violation: Function lacks docstring"
    assert result.violations == []
    assert result.engine_id == "llm_gate"


async def test_verify_file_read_error(path_resolver):
    """File read fails before prompt invocation → IO Error result, invoke not awaited."""
    engine, invoke_mock = _engine_with_mocked_prompt(path_resolver)
    file_path = Path("/non/existent/file.py")
    params = {"instruction": "Test rule", "rationale": "Test rationale"}

    result = await engine.verify(file_path, params)

    assert not result.ok
    assert "IO Error" in result.message
    assert result.violations == []
    assert result.engine_id == "llm_gate"
    invoke_mock.assert_not_awaited()


async def test_verify_llm_request_error(path_resolver, tmp_py_file):
    """Prompt invocation raises → ENFORCEMENT_UNAVAILABLE result (P1.3 hardening)."""
    engine, _ = _engine_with_mocked_prompt(
        path_resolver, invoke_side_effect=Exception("API timeout")
    )
    tmp_py_file.write_text("def foo(): pass", encoding="utf-8")
    params = {"instruction": "Test rule", "rationale": "Test rationale"}

    result = await engine.verify(tmp_py_file, params)

    assert not result.ok
    assert "LLM Reasoning Failed" in result.message
    # Source emits SYSTEM_ERROR_AI_OFFLINE as the canonical infra-failure
    # marker, not an empty violations list.
    assert result.violations == ["SYSTEM_ERROR_AI_OFFLINE"]
    assert result.engine_id == "llm_gate"


async def test_verify_invalid_json_response(path_resolver, tmp_py_file):
    """Prompt returns non-JSON → json.loads raises → same ENFORCEMENT_UNAVAILABLE path."""
    engine, _ = _engine_with_mocked_prompt(
        path_resolver, invoke_return_value="Not valid JSON"
    )
    tmp_py_file.write_text("def foo(): pass", encoding="utf-8")
    params = {"instruction": "Test rule", "rationale": "Test rationale"}

    result = await engine.verify(tmp_py_file, params)

    assert not result.ok
    assert "LLM Reasoning Failed" in result.message
    assert result.violations == ["SYSTEM_ERROR_AI_OFFLINE"]
    assert result.engine_id == "llm_gate"


async def test_verify_no_cache_without_db_session(path_resolver, tmp_py_file):
    """ADR-044: the verify() cache is DB-mediated and only engages when
    params plumb rule_id, rule_content_hash, and a session through
    params['_context'].db_session. Without that plumbing every call re-
    invokes the prompt model. (Pre-#572 vintage of this test asserted an
    in-memory single-call cache that never existed on the current source —
    see the file's header note.)"""
    engine, invoke_mock = _engine_with_mocked_prompt(
        path_resolver,
        invoke_return_value=json.dumps(
            {"violation": False, "reasoning": "OK", "finding": None}
        ),
    )
    content = "def foo(): pass"
    tmp_py_file.write_text(content, encoding="utf-8")
    params = {"instruction": "Cache test rule", "rationale": "Cache test rationale"}

    result1 = await engine.verify(tmp_py_file, params)
    result2 = await engine.verify(tmp_py_file, params)

    assert invoke_mock.await_count == 2
    # Each call constructs a fresh EngineResult — no in-memory dedup.
    assert result1 is not result2
    assert result1.ok and result2.ok


async def test_verify_cache_miss_different_content(path_resolver, tmp_py_file):
    """Same parameters but different file content → 2 invocations (cache miss
    on the content-hash axis). Test passes today because no cache engages
    in the bare-params path — it's a regression guard for the eventual
    case when DB-cache plumbing is present."""
    engine, invoke_mock = _engine_with_mocked_prompt(
        path_resolver,
        invoke_return_value=json.dumps(
            {"violation": False, "reasoning": "Test result", "finding": None}
        ),
    )

    tmp_py_file.write_text("content1", encoding="utf-8")
    params = {"instruction": "rule", "rationale": "rationale"}
    await engine.verify(tmp_py_file, params)

    tmp_py_file.write_text("content2", encoding="utf-8")
    await engine.verify(tmp_py_file, params)

    assert invoke_mock.await_count == 2


async def test_verify_cache_miss_different_instruction(path_resolver, tmp_py_file):
    """Same file content but different instruction → 2 invocations (cache
    miss on the rule-content-hash axis)."""
    engine, invoke_mock = _engine_with_mocked_prompt(
        path_resolver,
        invoke_return_value=json.dumps(
            {"violation": False, "reasoning": "Test result", "finding": None}
        ),
    )
    tmp_py_file.write_text("def foo(): pass", encoding="utf-8")

    params1 = {"instruction": "rule1", "rationale": "rationale"}
    await engine.verify(tmp_py_file, params1)

    params2 = {"instruction": "rule2", "rationale": "rationale"}
    await engine.verify(tmp_py_file, params2)

    assert invoke_mock.await_count == 2


async def test_verify_default_rationale(path_resolver, tmp_py_file):
    """No rationale in params → default rationale is used by verify()."""
    engine, _ = _engine_with_mocked_prompt(
        path_resolver,
        invoke_return_value=json.dumps(
            {"violation": False, "reasoning": "Test", "finding": None}
        ),
    )
    tmp_py_file.write_text("def foo(): pass", encoding="utf-8")

    params = {"instruction": "Test rule"}
    result = await engine.verify(tmp_py_file, params)

    assert result.ok


async def test_verify_missing_instruction(path_resolver, tmp_py_file):
    """Empty params dict → instruction is None, prompt is still invoked."""
    engine, invoke_mock = _engine_with_mocked_prompt(
        path_resolver,
        invoke_return_value=json.dumps(
            {"violation": False, "reasoning": "Test", "finding": None}
        ),
    )
    tmp_py_file.write_text("def foo(): pass", encoding="utf-8")

    await engine.verify(tmp_py_file, {})

    invoke_mock.assert_awaited()


def test_engine_id(path_resolver):
    """engine_id is the class-level identity ``"llm_gate"``."""
    engine = LLMGateEngine(path_resolver=path_resolver, llm_client=Mock())
    assert engine.engine_id == "llm_gate"


def test_init_with_custom_llm_client(path_resolver):
    """Constructor stores the llm_client on self.llm verbatim."""
    mock_llm = Mock()
    engine = LLMGateEngine(path_resolver=path_resolver, llm_client=mock_llm)
    assert engine.llm is mock_llm


def test_init_without_llm_client(path_resolver):
    """None is accepted as the llm_client sentinel; self.llm becomes None,
    construction still succeeds."""
    engine = LLMGateEngine(path_resolver=path_resolver, llm_client=None)
    assert hasattr(engine, "llm")
