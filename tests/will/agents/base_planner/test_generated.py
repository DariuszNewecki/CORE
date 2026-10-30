from __future__ import annotations

from unittest.mock import patch

from will.agents.base_planner import parse_and_validate_plan


# ID: f8b39dc7-900a-4426-ac77-8a8bede35247
def test_parse_and_validate_plan():
    response_text = '{"plan": [{"action": "file.write", "step": "write file", "params": {"file_path": "src/a.py"}}]}'

    mock_task = object()
    with (
        patch(
            "will.agents.base_planner.extract_json_from_response",
            return_value={
                "plan": [
                    {
                        "action": "file.write",
                        "step": "write file",
                        "params": {"file_path": "src/a.py"},
                    }
                ]
            },
        ),
        patch(
            "will.agents.base_planner.plan_steps",
            return_value=[
                {
                    "action": "file.write",
                    "step": "write file",
                    "params": {"file_path": "src/a.py"},
                }
            ],
        ),
        patch(
            "will.agents.base_planner.ExecutionTask",
            return_value=mock_task,
        ) as mock_exec_task,
    ):
        result = parse_and_validate_plan(response_text)

    assert result == [mock_task]
    mock_exec_task.assert_called_once_with(
        action="file.write", step="write file", params={"file_path": "src/a.py"}
    )


from will.agents.base_planner import plan_steps


# ID: da7b2194-dc0d-445a-990a-ae02c11c1494
def test_plan_steps():
    steps = ["step one", "step two", "step three"]

    # Bare list is accepted as-is
    assert plan_steps(steps) is steps

    # Object form with "plan" key returns the inner step list
    assert plan_steps({"plan": steps}) is steps

    # Non-plan shapes yield None
    assert plan_steps({"not_plan": steps}) is None
    assert plan_steps({"plan": "not-a-list"}) is None
    assert plan_steps("unexpected") is None
    assert plan_steps(None) is None


from unittest.mock import MagicMock

from will.agents.base_planner import build_planning_prompt


# ID: 2fe96d42-537a-48d6-b7a6-483c746f78ef
def test_build_planning_prompt():
    path_resolver = MagicMock()
    path_resolver.repo_root = "/tmp/repo"

    with (
        patch("will.agents.base_planner.PathResolver", MagicMock) as mock_resolver_cls,
        patch("will.agents.base_planner.PromptPipeline") as mock_pipeline_cls,
    ):
        # Make isinstance check pass
        mock_resolver_cls.__instancecheck__ = lambda self, obj: True
        # object.__instancecheck__ can't be patched on class; instead skip
        pass

    # Since isinstance relies on the real PathResolver class, build a real-ish object.
    # Use MagicMock with spec so isinstance passes.
    from will.agents.base_planner import PathResolver as RealPathResolver

    resolver = MagicMock(spec=RealPathResolver)
    resolver.repo_root = "/tmp/repo"

    with patch("will.agents.base_planner.PromptPipeline") as mock_pipeline_cls:
        mock_pipeline = MagicMock()
        mock_pipeline.process.return_value = "FINAL PROCESSED PROMPT"
        mock_pipeline_cls.return_value = mock_pipeline

        template = "GOAL: {goal}\nACTIONS: {action_descriptions}\nRECON: {reconnaissance_report}"

        result = build_planning_prompt(
            path_resolver=resolver,
            goal="Fix the bug",
            action_descriptions_str="Edit file",
            reconnaissance_report="Repo looks fine",
            prompt_template=template,
        )

    assert result == "FINAL PROCESSED PROMPT"
    mock_pipeline_cls.assert_called_once_with("/tmp/repo")
    mock_pipeline.process.assert_called_once()
    processed_arg = mock_pipeline.process.call_args[0][0]
    assert "GOAL: Fix the bug" in processed_arg
    assert "ACTIONS: Edit file" in processed_arg
    assert "RECON: Repo looks fine" in processed_arg
    assert "MUTATION-ONLY PLANNING" in processed_arg
