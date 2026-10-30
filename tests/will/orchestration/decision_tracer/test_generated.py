from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from will.orchestration.decision_tracer import DecisionTracer


# ID: 6d8dd7cc-30f2-477f-8852-d78c61c81603
async def test_DecisionTracer_save_trace():
    from pathlib import Path

    with (
        patch(
            "will.orchestration.decision_tracer.configured_repo_root",
            return_value=Path("/tmp/repo"),
        ),
        patch("will.orchestration.decision_tracer.PathResolver") as mock_path_resolver,
        patch("will.orchestration.decision_tracer.FileService") as mock_file_service,
    ):
        mock_resolver_instance = MagicMock()
        mock_resolver_instance.reports_dir = Path("/tmp/repo/reports")
        mock_path_resolver.return_value = mock_resolver_instance

        mock_fs_instance = MagicMock()
        mock_fs_instance.ensure_dir = MagicMock()
        mock_file_service.return_value = mock_fs_instance

        tracer = DecisionTracer(
            file_service=mock_fs_instance,
            agent_name="TestAgent",
            goal="TestGoal",
        )

        expected_path = Path("/tmp/trace.json")
        tracer._save_to_file = MagicMock(return_value=expected_path)
        tracer._save_to_database = AsyncMock()

        result = await tracer.save_trace()

        assert result == expected_path
        tracer._save_to_file.assert_called_once()
        tracer._save_to_database.assert_awaited_once_with(expected_path)


# ID: 6deecf46-3f9c-4e7a-9928-c052c496edba
def test_DecisionTracer_explain_chain():
    with (
        patch(
            "will.orchestration.decision_tracer.configured_repo_root",
            return_value="/tmp/repo",
        ),
        patch(
            "will.orchestration.decision_tracer.PathResolver"
        ) as mock_path_resolver_cls,
        patch(
            "will.orchestration.decision_tracer.FileService"
        ) as mock_file_service_cls,
    ):
        mock_path_resolver = MagicMock()
        mock_path_resolver.reports_dir = MagicMock()
        mock_path_resolver.reports_dir.__truediv__ = MagicMock(return_value=MagicMock())
        mock_path_resolver_cls.return_value = mock_path_resolver

        mock_file_service = MagicMock()
        mock_file_service_cls.return_value = mock_file_service

        tracer = DecisionTracer(
            session_id="sess-1",
            agent_name="AgentX",
            goal="Ship feature",
        )

        # Empty decisions -> placeholder message
        assert tracer.explain_chain() == "No decisions recorded yet."

        decision = MagicMock()
        decision.agent = "AgentX"
        decision.decision_type = "Architecture"
        decision.timestamp = "2024-01-01T00:00:00"
        decision.rationale = "Because reasons"
        decision.chosen_action = "Do the thing"
        decision.alternatives_considered = ["Alt A", "Alt B"]
        decision.confidence = 0.85
        decision.context = {"key": "value"}

        tracer.decisions.append(decision)

        result = tracer.explain_chain()

        assert "=== CORE Decision Chain ===" in result
        assert "Session: sess-1" in result
        assert "Agent: AgentX" in result
        assert "Total decisions: 1" in result
        assert "[1] AgentX - Architecture" in result
        assert "Rationale: Because reasons" in result
        assert "Chosen: Do the thing" in result
        assert "Alternatives: Alt A, Alt B" in result
        assert "Confidence: 85%" in result
        assert '"key": "value"' in result




# ID: 95844d24-07d0-4b91-900d-0917ddf0a814
def test_DecisionTracer_record():
    from will.orchestration.decision_tracer import DecisionTracer

    fake_root = MagicMock()
    fake_root.resolve.return_value = fake_root
    fake_root.__truediv__ = lambda self, other: fake_root
    fake_root.relative_to.return_value = fake_root

    path_resolver = MagicMock()
    path_resolver.repo_root = fake_root
    reports_dir = MagicMock()
    reports_dir.__truediv__ = lambda self, other: fake_root
    path_resolver.reports_dir = reports_dir

    file_service = MagicMock()

    with (
        patch(
            "will.orchestration.decision_tracer.PathResolver"
        ) as mock_path_resolver_cls,
        patch(
            "will.orchestration.decision_tracer.FileService"
        ) as mock_file_service_cls,
        patch(
            "will.orchestration.decision_tracer.configured_repo_root",
            return_value=fake_root,
        ),
        patch("will.orchestration.decision_tracer.Path") as mock_path,
    ):
        resolved_path = MagicMock()
        mock_path.return_value.resolve.return_value = resolved_path
        mock_path_resolver_cls.return_value.reports_dir = reports_dir

        tracer = DecisionTracer(
            path_resolver=path_resolver,
            session_id="sess-1",
            file_service=file_service,
            agent_name="agent-x",
            goal="do the thing",
        )
        tracer.ensure_dir_mock = file_service.ensure_dir

        tracer.record(
            agent="agent-x",
            decision_type="select_action",
            rationale="it is the best option",
            chosen_action="do_it",
            alternatives=["do_other"],
            context={"k": "v"},
            confidence=0.9,
        )

    assert len(tracer.decisions) == 1
    decision = tracer.decisions[0]
    assert decision.agent == "agent-x"
    assert decision.decision_type == "select_action"
    assert decision.rationale == "it is the best option"
    assert decision.chosen_action == "do_it"
    assert decision.alternatives_considered == ["do_other"]
    assert decision.context == {"k": "v"}
    assert decision.confidence == 0.9
