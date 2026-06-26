from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mind.logic.scout_inducer import ScoutInducer


@pytest.fixture
# ID: 75245429-e459-4897-af37-aad35e907f27
def mock_llm_client() -> MagicMock:
    """Return a mock LLM client implementing LLMClientProtocol."""
    return MagicMock()


@pytest.fixture
# ID: 77ac1a6d-2683-4a85-8a5f-9d6631e805f5
def inducer(mock_llm_client: MagicMock) -> ScoutInducer:
    """Return a ScoutInducer instance with a mocked LLM client."""
    return ScoutInducer(llm_client=mock_llm_client)


# ID: 65a4b64b-0936-406f-bc57-d4bef7e4010e
class TestScoutInducerInit:
    """Tests for ScoutInducer.__init__."""

    # ID: 9e92c776-014d-4f64-9ee4-a8689e1eaa97
    def test_init_sets_llm(self, mock_llm_client: MagicMock) -> None:
        """__init__ stores the llm_client as self.llm."""
        inst = ScoutInducer(llm_client=mock_llm_client)
        assert inst.llm is mock_llm_client

    # ID: b5ddeb25-a317-4b6d-871c-f0580c399606
    def test_init_loads_prompt_model(self, mock_llm_client: MagicMock) -> None:
        """__init__ loads the prompt model using PromptModel.load."""
        with patch("mind.logic.scout_inducer.PromptModel.load") as mock_load:
            inst = ScoutInducer(llm_client=mock_llm_client)
            mock_load.assert_called_once_with("scout_rule_inducer")
            assert inst._prompt_model is mock_load.return_value


# ID: cf7745b2-50e4-4fd5-9af3-ec70dc8f209b
class TestScoutInducerPropose:
    """Tests for ScoutInducer.propose."""

    # ID: c9ce42ac-ca45-4ae7-8f37-3eeaed7be501
    async def test_propose_happy_path(self, inducer: ScoutInducer) -> None:
        """propose returns candidates when LLM responds with valid data."""
        candidate = {
            "rule_id": "test-001",
            "statement": "test rule",
            "enforcement": {"engine": "regex", "params": {"pattern": "foo"}},
            "rationale": "testing",
            "evidence_sample": "bar",
            "ramp_note": "low",
        }
        valid_response = {"candidates": [candidate]}

        mock_prompt_model = MagicMock()
        mock_prompt_model.invoke = AsyncMock(
            return_value='{"candidates": [{"rule_id": "test-001"}]}'
        )
        inducer._prompt_model = mock_prompt_model

        with patch(
            "mind.logic.scout_inducer.extract_json", return_value=valid_response
        ):
            result = await inducer.propose("signal text")

        assert result == [candidate]

    # ID: 38f95cab-1bac-4a2a-9731-44eee2640d86
    async def test_propose_calls_prompt_model_with_context(
        self, inducer: ScoutInducer
    ) -> None:
        """propose passes code_signals in context and uses the LLM client."""
        mock_prompt_model = MagicMock()
        mock_prompt_model.invoke = AsyncMock(return_value='{"candidates": []}')
        inducer._prompt_model = mock_prompt_model

        with patch(
            "mind.logic.scout_inducer.extract_json", return_value={"candidates": []}
        ):
            await inducer.propose("my_signals")

        mock_prompt_model.invoke.assert_awaited_once_with(
            context={"code_signals": "my_signals"},
            client=inducer.llm,
            user_id="scout_rule_inducer",
        )

    # ID: 034f653e-ab22-4660-ae0f-0bb4dc683ec0
    async def test_propose_returns_empty_on_prompt_model_error(
        self, inducer: ScoutInducer
    ) -> None:
        """propose returns [] when _prompt_model.invoke raises an exception."""
        mock_prompt_model = MagicMock()
        mock_prompt_model.invoke = AsyncMock(side_effect=RuntimeError("LLM failure"))
        inducer._prompt_model = mock_prompt_model

        result = await inducer.propose("signal text")
        assert result == []

    # ID: f67a859f-5faa-4e55-bf39-a375b151dcbb
    async def test_propose_returns_empty_on_extract_json_error(
        self, inducer: ScoutInducer
    ) -> None:
        """propose returns [] when extract_json raises an exception."""
        mock_prompt_model = MagicMock()
        mock_prompt_model.invoke = AsyncMock(return_value="invalid json")
        inducer._prompt_model = mock_prompt_model

        with patch(
            "mind.logic.scout_inducer.extract_json", side_effect=ValueError("bad json")
        ):
            result = await inducer.propose("signal text")
        assert result == []

    # ID: 3413a1c0-b591-4f5a-b24f-667b441d158e
    async def test_propose_returns_empty_when_response_not_dict(
        self, inducer: ScoutInducer
    ) -> None:
        """propose returns [] when extract_json returns a non-dict value."""
        mock_prompt_model = MagicMock()
        mock_prompt_model.invoke = AsyncMock(return_value="null")
        inducer._prompt_model = mock_prompt_model

        with patch("mind.logic.scout_inducer.extract_json", return_value=None):
            result = await inducer.propose("signal text")
        assert result == []

    # ID: 55cd1025-07be-48b8-ba27-52030a1459fa
    async def test_propose_returns_empty_when_candidates_missing(
        self, inducer: ScoutInducer
    ) -> None:
        """propose returns [] when the response dict has no 'candidates' key."""
        mock_prompt_model = MagicMock()
        mock_prompt_model.invoke = AsyncMock(return_value='{"other": "data"}')
        inducer._prompt_model = mock_prompt_model

        with patch(
            "mind.logic.scout_inducer.extract_json", return_value={"other": "data"}
        ):
            result = await inducer.propose("signal text")
        assert result == []

    # ID: cbec0534-ab6d-4515-804b-14d2855141e6
    async def test_propose_returns_empty_when_candidates_not_list(
        self, inducer: ScoutInducer
    ) -> None:
        """propose returns [] when the 'candidates' value is not a list."""
        mock_prompt_model = MagicMock()
        mock_prompt_model.invoke = AsyncMock(
            return_value='{"candidates": "not_a_list"}'
        )
        inducer._prompt_model = mock_prompt_model

        with patch(
            "mind.logic.scout_inducer.extract_json",
            return_value={"candidates": "not_a_list"},
        ):
            result = await inducer.propose("signal text")
        assert result == []

    # ID: 75492896-50ad-4959-a4b8-90033a0d350a
    async def test_propose_filters_invalid_candidates(
        self, inducer: ScoutInducer
    ) -> None:
        """propose drops candidates without rule_id and logs a warning."""
        valid_candidate = {"rule_id": "valid-id", "statement": "ok"}
        invalid_candidate = {"statement": "missing rule_id"}
        candidates_input = [valid_candidate, invalid_candidate]
        response = {"candidates": candidates_input}

        mock_prompt_model = MagicMock()
        mock_prompt_model.invoke = AsyncMock(return_value="{}")
        inducer._prompt_model = mock_prompt_model

        with patch("mind.logic.scout_inducer.extract_json", return_value=response):
            with patch("mind.logic.scout_inducer.logger") as mock_logger:
                result = await inducer.propose("signal text")

        assert result == [valid_candidate]
        mock_logger.warning.assert_called_once()

    # ID: 611a4343-a553-4344-9ae0-2bd2e7a9326d
    async def test_propose_filters_non_dict_candidates(
        self, inducer: ScoutInducer
    ) -> None:
        """propose drops candidates that are not dicts."""
        response = {"candidates": [{"rule_id": "ok"}, "string", 42]}

        mock_prompt_model = MagicMock()
        mock_prompt_model.invoke = AsyncMock(return_value="{}")
        inducer._prompt_model = mock_prompt_model

        with patch("mind.logic.scout_inducer.extract_json", return_value=response):
            with patch("mind.logic.scout_inducer.logger"):
                result = await inducer.propose("signal text")

        assert result == [{"rule_id": "ok"}]

    # ID: f4636019-8754-48e6-ad3f-d6342f307b90
    async def test_propose_returns_empty_list_on_empty_signals(
        self, inducer: ScoutInducer
    ) -> None:
        """propose handles empty signal string gracefully."""
        mock_prompt_model = MagicMock()
        mock_prompt_model.invoke = AsyncMock(return_value='{"candidates": []}')
        inducer._prompt_model = mock_prompt_model

        with patch(
            "mind.logic.scout_inducer.extract_json", return_value={"candidates": []}
        ):
            result = await inducer.propose("")
        assert result == []

    # ID: 33cbed4a-dd9d-4f33-8603-7a8a729a5035
    async def test_propose_returns_correct_type(self, inducer: ScoutInducer) -> None:
        """propose always returns a list."""
        mock_prompt_model = MagicMock()
        mock_prompt_model.invoke = AsyncMock(
            return_value='{"candidates": [{"rule_id": "a"}]}'
        )
        inducer._prompt_model = mock_prompt_model

        with patch(
            "mind.logic.scout_inducer.extract_json",
            return_value={"candidates": [{"rule_id": "a"}]},
        ):
            result = await inducer.propose("signal text")
        assert isinstance(result, list)
