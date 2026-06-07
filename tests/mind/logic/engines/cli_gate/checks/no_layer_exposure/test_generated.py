from typing import Any

import pytest

from mind.logic.engines.cli_gate.checks.no_layer_exposure import NoLayerExposureCheck
from shared.models import AuditSeverity


@pytest.fixture
def check_instance() -> NoLayerExposureCheck:
    return NoLayerExposureCheck()


class TestNoLayerExposureCheck:
    """Tests for the NoLayerExposureCheck CLI gate check."""

    def test_check_type(self, check_instance: NoLayerExposureCheck) -> None:
        """Verify check_type attribute is set correctly."""
        assert check_instance.check_type == "no_layer_exposure"

    def test_verify_empty_commands(self, check_instance: NoLayerExposureCheck) -> None:
        """Edge case: empty commands list should return no findings."""
        result = check_instance.verify([], {"some": "params"})
        assert result == []

    def test_verify_no_forbidden_in_params(
        self, check_instance: NoLayerExposureCheck
    ) -> None:
        """Edge case: params with no forbidden_resources key."""
        commands: list[dict[str, Any]] = [{"name": "layer.resource.command"}]
        result = check_instance.verify(commands, {})
        assert result == []

    def test_verify_forbidden_resources_none(
        self, check_instance: NoLayerExposureCheck
    ) -> None:
        """Edge case: forbidden_resources is None should be treated as empty."""
        commands: list[dict[str, Any]] = [{"name": "layer.resource.command"}]
        result = check_instance.verify(commands, {"forbidden_resources": None})
        assert result == []

    def test_verify_forbidden_resources_empty_list(
        self, check_instance: NoLayerExposureCheck
    ) -> None:
        """Edge case: forbidden_resources empty list."""
        commands: list[dict[str, Any]] = [{"name": "layer.resource.command"}]
        result = check_instance.verify(commands, {"forbidden_resources": []})
        assert result == []

    def test_verify_command_with_no_name(
        self, check_instance: NoLayerExposureCheck
    ) -> None:
        """Edge case: command dict with no 'name' key or empty name should be skipped."""
        commands: list[dict[str, Any]] = [
            {"name": ""},
            {},
            {"name": "allowed.resource.command"},
        ]
        result = check_instance.verify(
            commands, {"forbidden_resources": ["forbidden_layer"]}
        )
        assert result == []

    def test_verify_happy_path_no_exposure(
        self, check_instance: NoLayerExposureCheck
    ) -> None:
        """Happy path: no command exposes a forbidden resource."""
        commands: list[dict[str, Any]] = [
            {"name": "allowed.resource.do_thing"},
            {"name": "safe.layer.run"},
        ]
        result = check_instance.verify(
            commands, {"forbidden_resources": ["forbidden_layer", "restricted"]}
        )
        assert result == []

    def test_verify_single_exposure(self, check_instance: NoLayerExposureCheck) -> None:
        """Verify detection of a single forbidden resource exposure."""
        commands: list[dict[str, Any]] = [
            {"name": "forbidden_layer.some.command", "file_path": "/path/to/file.py"},
        ]
        result = check_instance.verify(
            commands, {"forbidden_resources": ["forbidden_layer"]}
        )
        assert len(result) == 1
        finding = result[0]
        assert finding.check_id == "cli_gate.no_layer_exposure"
        assert finding.severity == AuditSeverity.BLOCK
        assert "forbidden_layer" in finding.message
        assert finding.file_path == "/path/to/file.py"
        assert finding.context["command_name"] == "forbidden_layer.some.command"
        assert finding.context["resource"] == "forbidden_layer"
        assert finding.context["forbidden_resources"] == ["forbidden_layer"]

    def test_verify_multiple_exposures(
        self, check_instance: NoLayerExposureCheck
    ) -> None:
        """Verify detection of multiple forbidden resource exposures."""
        commands: list[dict[str, Any]] = [
            {"name": "forbidden_layer.cmd1", "file_path": "a.py"},
            {"name": "restricted.cmd2", "file_path": "b.py"},
            {"name": "allowed.cmd3", "file_path": "c.py"},
        ]
        result = check_instance.verify(
            commands, {"forbidden_resources": ["forbidden_layer", "restricted"]}
        )
        assert len(result) == 2
        assert all(f.severity == AuditSeverity.BLOCK for f in result)
        assert all(f.check_id == "cli_gate.no_layer_exposure" for f in result)
        resources_found = {f.context["resource"] for f in result}
        assert resources_found == {"forbidden_layer", "restricted"}

    def test_verify_multiple_commands_same_resource(
        self, check_instance: NoLayerExposureCheck
    ) -> None:
        """Verify exposure reported for each command even if resource repeats."""
        commands: list[dict[str, Any]] = [
            {"name": "bad.resource.cmd1"},
            {"name": "bad.resource.cmd2"},
        ]
        result = check_instance.verify(commands, {"forbidden_resources": ["bad"]})
        assert len(result) == 2

    def test_verify_resource_first_segment(
        self, check_instance: NoLayerExposureCheck
    ) -> None:
        """Verify only the first segment before '.' is checked as resource."""
        commands: list[dict[str, Any]] = [
            {"name": "good.restricted.cmd"},
        ]
        result = check_instance.verify(
            commands, {"forbidden_resources": ["restricted"]}
        )
        assert result == []

    def test_verify_case_sensitivity(
        self, check_instance: NoLayerExposureCheck
    ) -> None:
        """Verify resource matching is case-sensitive."""
        commands: list[dict[str, Any]] = [
            {"name": "FORBIDDEN.layer.cmd"},
        ]
        result = check_instance.verify(commands, {"forbidden_resources": ["forbidden"]})
        assert result == []

    def test_verify_file_path_none(self, check_instance: NoLayerExposureCheck) -> None:
        """Verify file_path defaults to 'none' when missing."""
        commands: list[dict[str, Any]] = [
            {"name": "forbidden.cmd"},
        ]
        result = check_instance.verify(commands, {"forbidden_resources": ["forbidden"]})
        assert len(result) == 1
        assert result[0].file_path == "none"

    def test_verify_context_contains_sorted_forbidden(
        self, check_instance: NoLayerExposureCheck
    ) -> None:
        """Verify the context has sorted forbidden_resources."""
        commands: list[dict[str, Any]] = [
            {"name": "c.cmd"},
            {"name": "a.cmd"},
        ]
        result = check_instance.verify(commands, {"forbidden_resources": ["c", "a"]})
        assert len(result) == 2
        for f in result:
            assert f.context["forbidden_resources"] == ["a", "c"]
