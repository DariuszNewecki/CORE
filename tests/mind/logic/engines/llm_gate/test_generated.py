import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from pathlib import Path
from typing import Any

from mind.logic.engines.llm_gate import LLMGateEngine, _resolve_file_content_hash, _read_cached_verdict, _write_cached_verdict
from shared.domain.engine import BaseEngine, EngineResult
from shared.domain.path_resolver import PathResolver
from shared.domain.llm_client_protocol import LLMClientProtocol
from shared.domain.prompt_model import PromptModel


@pytest.fixture
def mock_path_resolver(tmp_path) -> PathResolver:
    patcher = MagicMock(spec=PathResolver)
    patcher.repo_root = tmp_path
    return patcher


@pytest.fixture
def mock_llm_client() -> LLMClientProtocol:
    return MagicMock(spec=LLMClientProtocol)


@pytest.fixture
def engine(mock_path_resolver, mock_llm_client) -> LLMGateEngine:
    with patch.object(PromptModel, 'load', return_value=MagicMock()) as mock_load:
        mock_prompt = MagicMock()
        mock_prompt.invoke = AsyncMock(return_value='{"violation": false}')
        mock_load.return_value = mock_prompt
        engine = LLMGateEngine(path_resolver=mock_path_resolver, llm_client=mock_llm_client)
        engine._audit_prompt_model = mock_prompt
        engine._prompt_model = mock_prompt
        return engine


@pytest.fixture
def sample_file(tmp_path) -> Path:
    file_path = tmp_path / "test_file.py"
    file_path.write_text("print('hello')", encoding="utf-8")
    return file_path


@pytest.fixture
def valid_params() -> dict[str, Any]:
    return {
        "instruction": "Ensure file is valid Python",
        "rationale": "Testing rationale",
        "_rule_id": "rule-123",
        "_rule_content_hash": "hash123",
    }


class TestLLMGateEngineInit:
    def test_init_stores_dependencies(self, mock_path_resolver, mock_llm_client):
        with patch.object(PromptModel, 'load') as mock_load:
            mock_prompt = MagicMock()
            mock_load.return_value = mock_prompt
            engine = LLMGateEngine(path_resolver=mock_path_resolver, llm_client=mock_llm_client)
            assert engine._paths is mock_path_resolver
            assert engine.llm is mock_llm_client
            assert engine._prompt_model is mock_prompt
            assert engine._audit_prompt_model is mock_prompt

    def test_engine_id_is_correct(self):
        assert LLMGateEngine.engine_id == "llm_gate"


class TestLLMGateEngineVerify:
    @pytest.mark.asyncio
    async def test_verify_happy_path_no_rule_id(self, engine, sample_file):
        params = {
            "instruction": "Check code quality",
            "rationale": "Test rationale",
        }
        result = await engine.verify(sample_file, params)
        assert result.ok is True
        assert result.message == "Semantic adherence verified."
        assert result.violations == []
        assert result.engine_id == "llm_gate"

    @pytest.mark.asyncio
    async def test_verify_with_violation(self, engine, sample_file, valid_params):
        engine._audit_prompt_model.invoke = AsyncMock(return_value='{"violation": true, "reasoning": "Bad style", "finding": "Found issue"}')
        result = await engine.verify(sample_file, valid_params)
        assert result.ok is False
        assert "Semantic Violation: Bad style" in result.message
        assert result.violations == ["Found issue"]

    @pytest.mark.asyncio
    async def test_verify_io_error(self, engine, tmp_path):
        non_existent = tmp_path / "does_not_exist.py"
        params = {"instruction": "test"}
        result = await engine.verify(non_existent, params)
        assert result.ok is False
        assert result.message.startswith("IO Error:")
        assert result.violations == []
        assert result.engine_id == "llm_gate"

    @pytest.mark.asyncio
    async def test_verify_llm_exception(self, engine, sample_file, valid_params):
        engine._audit_prompt_model.invoke = AsyncMock(side_effect=Exception("API failure"))
        result = await engine.verify(sample_file, valid_params)
        assert result.ok is False
        assert "ENFORCEMENT_UNAVAILABLE" in result.message
        assert result.violations == ["SYSTEM_ERROR_AI_OFFLINE"]

    @pytest.mark.asyncio
    async def test_verify_with_cache_hit_and_not_force(self, engine, sample_file, valid_params):
        mock_cached_result = EngineResult(ok=True, message="Cached pass", violations=[], engine_id="llm_gate")
        with patch('mind.logic.engines.llm_gate._resolve_file_content_hash', new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = "abc123"
            with patch('mind.logic.engines.llm_gate._read_cached_verdict', new_callable=AsyncMock) as mock_read:
                mock_read.return_value = mock_cached_result
                params_with_context = dict(valid_params)
                mock_context = MagicMock()
                mock_context.db_session = MagicMock()
                params_with_context["_context"] = mock_context
                result = await engine.verify(sample_file, params_with_context)
                assert result is mock_cached_result

    @pytest.mark.asyncio
    async def test_verify_cache_miss_invokes_llm(self, engine, sample_file, valid_params):
        with patch('mind.logic.engines.llm_gate._resolve_file_content_hash', new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = "abc123"
            with patch('mind.logic.engines.llm_gate._read_cached_verdict', new_callable=AsyncMock) as mock_read:
                mock_read.return_value = None
                with patch('mind.logic.engines.llm_gate._write_cached_verdict', new_callable=AsyncMock) as mock_write:
                    params_with_context = dict(valid_params)
                    mock_context = MagicMock()
                    mock_context.db_session = MagicMock()
                    params_with_context["_context"] = mock_context
                    result = await engine.verify(sample_file, params_with_context)
                    assert result.ok is True
                    assert result.message == "Semantic adherence verified."
                    mock_write.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_verify_cache_skipped_when_force_llm(self, engine, sample_file, valid_params):
        with patch('mind.logic.engines.llm_gate._resolve_file_content_hash', new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = "abc123"
            with patch('mind.logic.engines.llm_gate._read_cached_verdict', new_callable=AsyncMock) as mock_read:
                params_with_context = dict(valid_params)
                mock_context = MagicMock()
                mock_context.db_session = MagicMock()
                params_with_context["_context"] = mock_context
                params_with_context["_force_llm"] = True
                result = await engine.verify(sample_file, params_with_context)
                mock_read.assert_not_awaited()
                assert result.ok is True

    @pytest.mark.asyncio
    async def test_verify_no_session_no_cache(self, engine, sample_file, valid_params):
        with patch('mind.logic.engines.llm_gate._resolve_file_content_hash', new_callable=AsyncMock) as mock_resolve:
            with patch('mind.logic.engines.llm_gate._read_cached_verdict', new_callable=AsyncMock) as mock_read:
                params_no_session = dict(valid_params)
                result = await engine.verify(sample_file, params_no_session)
                mock_read.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_verify_cache_eligible_but_error_doesnt_write(self, engine, sample_file, valid_params):
        engine._audit_prompt_model.invoke = AsyncMock(side_effect=Exception("API failure"))
        with patch('mind.logic.engines.llm_gate._resolve_file_content_hash', new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = "abc123"
            with patch('mind.logic.engines.llm_gate._write_cached_verdict', new_callable=AsyncMock) as mock_write:
                params_with_context = dict(valid_params)
                mock_context = MagicMock()
                mock_context.db_session = MagicMock()
                params_with_context["_context"] = mock_context
                result = await engine.verify(sample_file, params_with_context)
                mock_write.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_verify_with_rel_path_fallback(self, engine, tmp_path):
        outside_file = tmp_path / ".." / "outside.txt"
        outside_file = outside_file.resolve()
        outside_file.write_text("content", encoding="utf-8")
        params = {"instruction": "test"}
        result = await engine.verify(outside_file, params)
        assert result.ok is True

    @pytest.mark.asyncio
    async def test_verify_file_read_exception(self, engine, sample_file, valid_params):
        with patch.object(Path, 'read_text', side_effect=PermissionError("No permission")):
            result = await engine.verify(sample_file, valid_params)
            assert result.ok is False
            assert "IO Error" in result.message
            assert result.violations == []

    @pytest.mark.asyncio
    async def test_verify_json_decode_fails_returns_error(self, engine, sample_file, valid_params):
        engine._audit_prompt_model.invoke = AsyncMock(return_value="invalid json{")
        result = await engine.verify(sample_file, valid_params)
        assert result.ok is False
        assert "ENFORCEMENT_UNAVAILABLE" in result.message

    @pytest.mark.asyncio
    async def test_verify_with_missing_instruction(self, engine, sample_file):
        params = {}
        result = await engine.verify(sample_file, params)
        assert result.ok is True
        assert result.message == "Semantic adherence verified."

    @pytest.mark.asyncio
    async def test_verify_with_empty_rationale_default(self, engine, sample_file):
        params = {"instruction": "check"}
        result = await engine.verify(sample_file, params)
        assert result.ok is True

    @pytest.mark.asyncio
    async def test_verify_with_empty_rule_content_hash(self, engine, sample_file):
        params = {"instruction": "check", "_rule_id": "x", "_rule_content_hash": ""}
        with patch('mind.logic.engines.llm_gate._resolve_file_content_hash', new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = "abc"
            with patch('mind.logic.engines.llm_gate._read_cached_verdict', new_callable=AsyncMock) as mock_read:
                params["_context"] = MagicMock(db_session=MagicMock())
                result = await engine.verify(sample_file, params)
                mock_read.assert_awaited_once()


class TestResolveFileContentHash:
    @pytest.mark.asyncio
    async def test_resolve_returns_hash(self):
        mock_session = MagicMock()
        result = await _resolve_file_content_hash(mock_session, "test.py", "content")
        assert isinstance(result, str)
        assert len(result) == 64

    @pytest.mark.asyncio
    async def test_resolve_with_empty_string_content(self):
        mock_session = MagicMock()
        result = await _resolve_file_content_hash(mock_session, "test.py", "")
        assert isinstance(result, str)
        assert len(result) == 64


class TestReadCachedVerdict:
    @pytest.mark.asyncio
    async def test_read_returns_none_on_failure(self):
        mock_session = MagicMock()
        result = await _read_cached_verdict(mock_session, rule_id="r1", file_path="f.py", file_content_hash="h1", rule_content_hash="h2")
        assert result is None

    @pytest.mark.asyncio
    async def test_read_returns_none_on_none_session(self):
        result = await _read_cached_verdict(None, rule_id="r1", file_path="f.py", file_content_hash="h1", rule_content_hash="h2")
        assert result is None


class TestWriteCachedVerdict:
    @pytest.mark.asyncio
    async def test_write_with_none_session_noops(self):
        result = await _write_cached_verdict(None, rule_id="r1", file_path="f.py", file_content_hash="h1", rule_content_hash="h2", verdict="PASS", findings=[])
        assert result is None

    @pytest.mark.asyncio
    async def test_write_with_valid_session(self):
        mock_session = MagicMock()
        result = await _write_cached_verdict(mock_session, rule_id="r1", file_path="f.py", file_content_hash="h1", rule_content_hash="h2", verdict="PASS", findings=[])
        assert result is None
