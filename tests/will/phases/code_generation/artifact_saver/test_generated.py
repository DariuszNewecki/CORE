from __future__ import annotations

from unittest.mock import MagicMock

from will.phases.code_generation.artifact_saver import ArtifactSaver


# ID: 030e9fd2-eab3-4a15-b51d-0966783eb8d8
def test_artifact_saver_save_generation_artifacts():
    file_service = MagicMock()
    saver = ArtifactSaver(file_service)

    step = MagicMock()
    step.params = {"code": "print('hello')"}

    report_data = {"goal": "test goal", "steps": [{"step": 1}]}

    saver._build_report_data = MagicMock(return_value=report_data)
    saver._get_params_dict = MagicMock(return_value={"code": "print('hello')"})
    saver._save_code_artifact = MagicMock()
    saver._save_report = MagicMock()
    saver._log_summary = MagicMock()

    saver.save_generation_artifacts([step], "work/dir", "test goal")

    saver._build_report_data.assert_called_once_with([step], "test goal")
    saver._get_params_dict.assert_called_once_with(step.params)
    saver._save_code_artifact.assert_called_once_with(
        step, 1, "work/dir", report_data["steps"][0]
    )
    saver._save_report.assert_called_once_with(report_data, "work/dir")
    saver._log_summary.assert_called_once_with(report_data, "work/dir")
    assert saver._save_report.call_count == 1





# ID: f08bc020-b72a-4761-8b84-4179f6cf5682
def test_ArtifactSaver():
    file_service = MagicMock()

    step = MagicMock()
    step.action = "refactor.module"
    step.description = "Refactor the module"
    step.params = {"code": "print('hello')", "file_path": "src/target.py"}
    step.metadata = {}

    saver = ArtifactSaver(file_service)
    saver.save_generation_artifacts([step], "work_dir", "refactor goal")

    written_paths = [c.args[0] for c in file_service.write.call_args_list]
    assert "work_dir/generation_report.json" in written_paths
    assert any(p.startswith("work_dir/step_01_") for p in written_paths)

    report_call = next(
        c
        for c in file_service.write.call_args_list
        if c.args[0] == "work_dir/generation_report.json"
    )
    report_json = report_call.args[1]
    assert '"goal": "refactor goal"' in report_json
    assert '"total_steps": 1' in report_json
    assert '"successful": 1' in report_json
