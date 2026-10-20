from __future__ import annotations

from typing import Any

import pytest

from mind.logic.engines.cli_gate.checks.no_layer_exposure import NoLayerExposureCheck
from shared.models import AuditSeverity


@pytest.fixture
# ID: c602a41e-f78e-4c1d-9d9a-d97c2f4ef359
def check_instance() -> NoLayerExposureCheck:
    return NoLayerExposureCheck()


# ID: dbcfe643-df04-4e20-9ca0-a8e548f8174d
class TestNoLayerExposureCheck:
    """Tests for the NoLayerExposureCheck CLI gate check."""

    # ID: e106fb03-fc75-4397-97fd-4432da9f10b5
    def test_check_type(self, check_instance: NoLayerExposureCheck) -> None:
        """Verify check_type attribute is set correctly."""
        assert check_instance.check_type == "no_layer_exposure"

    # ID: 9e3e30b9-cd0f-4d61-b90d-881a3c137299
    def test_verify_empty_commands(self, check_instance: NoLayerExposureCheck) -> None:
        """Edge case: empty commands list should return no findings."""
        result = check_instance.verify([], {"some": "params"})
        assert result == []

    # ID: 68a7c5d2-b8ef-4467-89ea-f4a444349115
    def test_verify_no_forbidden_in_params(
        self, check_instance: NoLayerExposureCheck
    ) -> None:
        """Edge case: params with no forbidden_resources key."""
        commands: list[dict[str, Any]] = [{"name": "layer.resource.command"}]
        result = check_instance.verify(commands, {})
        assert result == []

    # ID: 25480ba6-a448-4a6d-a292-156675e13ef6
    def test_verify_forbidden_resources_none(
        self, check_instance: NoLayerExposureCheck
    ) -> None:
        """Edge case: forbidden_resources is None should be treated as empty."""
        commands: list[dict[str, Any]] = [{"name": "layer.resource.command"}]
        result = check_instance.verify(commands, {"forbidden_resources": None})
        assert result == []

    # ID: 1e0b35df-9acd-421a-adff-d199591cccbc
    def test_verify_forbidden_resources_empty_list(
        self, check_instance: NoLayerExposureCheck
    ) -> None:
        """Edge case: forbidden_resources empty list."""
        commands: list[dict[str, Any]] = [{"name": "layer.resource.command"}]
        result = check_instance.verify(commands, {"forbidden_resources": []})
        assert result == []

    # ID: 0024cbd8-7790-4ce4-833a-737e40d5a0b4
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

    # ID: aab75b6f-d4f7-42eb-9900-aad402b49e42
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

    # ID: 32529800-5eb9-4cc4-8c1a-91fb7d369be0
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

    # ID: 280dfa86-3f85-40cd-be0b-93f08fb963e1
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

    # ID: 095b4ad8-00c0-46b7-a999-473dd5f2b37d
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

    # ID: f00f95f9-57eb-4ae2-94fe-0ad390cae9c1
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

    # ID: c9862e0d-d0f8-4338-87ac-b981ca499b4c
    def test_verify_case_sensitivity(
        self, check_instance: NoLayerExposureCheck
    ) -> None:
        """Verify resource matching is case-sensitive."""
        commands: list[dict[str, Any]] = [
            {"name": "FORBIDDEN.layer.cmd"},
        ]
        result = check_instance.verify(commands, {"forbidden_resources": ["forbidden"]})
        assert result == []

    # ID: f353b860-4936-49b2-b94f-ee724593b419
    def test_verify_file_path_none(self, check_instance: NoLayerExposureCheck) -> None:
        """Verify file_path defaults to 'none' when missing."""
        commands: list[dict[str, Any]] = [
            {"name": "forbidden.cmd"},
        ]
        result = check_instance.verify(commands, {"forbidden_resources": ["forbidden"]})
        assert len(result) == 1
        assert result[0].file_path == "none"

    # ID: c6a58706-b7e1-46f8-b264-985f78e0a5b3
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


# ID: 686e9762-6168-491f-858f-5e7227ab66c7
def test_NoLayerExposureCheck_verify():
    check = NoLayerExposureCheck()

    commands = [
        {"name": "db.query", "file_path": "/tmp/cmd.py"},
        {"name": "safe.run", "file_path": "/tmp/safe.py"},
    ]
    params = {"forbidden_resources": ["db"]}

    findings = check.verify(commands, params)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.check_id == "cli_gate.no_layer_exposure"
    assert finding.file_path == "/tmp/cmd.py"
    assert finding.context["command_name"] == "db.query"
    assert finding.context["resource"] == "db"
    assert finding.context["forbidden_resources"] == ["db"]





# ID: 02588e3e-8e8d-460c-aa3d-5898ca342414
def test_NoLayerExposureCheck() -> None:
    check = NoLayerExposureCheck()
    check.verify = NoLayerExposureCheck.verify.__get__(check, NoLayerExposureCheck)

    commands = [
        {"name": "db.query", "file_path": "cmd1.py"},
        {"name": "api.call", "file_path": "cmd2.py"},
        {"name": "db.write", "file_path": "cmd3.py"},
        {"name": "", "file_path": "cmd4.py"},
    ]
    params = {"forbidden_resources": ["db"]}

    findings = check.verify(commands, params)

    assert len(findings) == 2
    assert findings[0].check_id == "cli_gate.no_layer_exposure"
    assert findings[0].context["command_name"] == "db.query"
    assert findings[0].context["resource"] == "db"
    assert findings[0].file_path == "cmd1.py"
    assert findings[1].context["command_name"] == "db.write"
