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
