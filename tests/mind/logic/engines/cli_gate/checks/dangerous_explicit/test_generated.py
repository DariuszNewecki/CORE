from __future__ import annotations

import pytest

from mind.logic.engines.cli_gate.checks.dangerous_explicit import DangerousExplicitCheck
from shared.models import AuditSeverity


# ID: 5a00e66b-71f0-4735-97f3-4bc100ac5c8e
class TestDangerousExplicitCheck:
    @pytest.fixture
    # ID: 9f76c0a5-b96b-4684-8a30-7b188ccee517
    def check(self) -> DangerousExplicitCheck:
        return DangerousExplicitCheck()

    # ID: 0b68771a-040f-40c3-ae7f-85240c1e586e
    def test_has_correct_check_type(self, check: DangerousExplicitCheck) -> None:
        """Verify the check_type class attribute is 'dangerous_explicit'."""
        assert check.check_type == "dangerous_explicit"

    # ID: 844c72ab-6ab9-47da-98cf-b8faab4c9b76
    def test_empty_commands_returns_empty_findings(
        self, check: DangerousExplicitCheck
    ) -> None:
        """When no commands are provided, verify returns no findings."""
        result = check.verify([], {})
        assert result == []

    # ID: 52535342-1f12-4348-ab6f-113c7bea4838
    def test_non_mutate_commands_are_skipped(
        self, check: DangerousExplicitCheck
    ) -> None:
        """Commands with behavior other than 'mutate' are ignored."""
        commands = [
            {
                "behavior": "read",
                "name": "read_cmd",
                "dangerous": True,
                "params_list": ["write"],
            },
            {
                "behavior": "query",
                "name": "query_cmd",
                "dangerous": True,
                "params_list": ["write"],
            },
        ]
        result = check.verify(commands, {})
        assert result == []

    # ID: b898bc86-0e2b-4d01-86f8-21574b58216e
    def test_dangerous_mutate_command_with_write_param_no_findings(
        self, check: DangerousExplicitCheck
    ) -> None:
        """A mutate command with dangerous=True and write param generates no findings."""
        commands = [
            {
                "behavior": "mutate",
                "name": "safe_mutate",
                "dangerous": True,
                "params_list": ["write", "other"],
                "file_path": "/tmp/test.sh",
            }
        ]
        result = check.verify(commands, {})
        assert result == []

    # ID: a1847e0e-1aec-4c70-b6cc-5bfc0e0cf562
    def test_mutate_command_missing_dangerous_flag_generates_finding(
        self, check: DangerousExplicitCheck
    ) -> None:
        """A mutate command without dangerous=True should produce a BLOCK finding."""
        commands = [
            {
                "behavior": "mutate",
                "name": "risky_mutate",
                "dangerous": False,
                "params_list": ["write"],
                "file_path": "/tmp/script.sh",
            }
        ]
        result = check.verify(commands, {})
        assert len(result) == 1
        finding = result[0]
        assert finding.check_id == "cli_gate.dangerous_explicit"
        assert finding.severity == AuditSeverity.BLOCK
        assert "risky_mutate" in finding.message
        assert "not marked dangerous=True" in finding.message
        assert finding.file_path == "/tmp/script.sh"
        assert finding.context == {
            "command_name": "risky_mutate",
            "missing": "dangerous",
        }

    # ID: 37cb907b-ee75-4c80-a9eb-dd96bc4ed55e
    def test_mutate_command_missing_write_param_generates_finding(
        self, check: DangerousExplicitCheck
    ) -> None:
        """A mutate command without 'write' in params_list should produce a BLOCK finding."""
        commands = [
            {
                "behavior": "mutate",
                "name": "no_write",
                "dangerous": True,
                "params_list": ["other_param"],
                "file_path": "/tmp/update.sh",
            }
        ]
        result = check.verify(commands, {})
        assert len(result) == 1
        finding = result[0]
        assert finding.check_id == "cli_gate.dangerous_explicit"
        assert finding.severity == AuditSeverity.BLOCK
        assert "no_write" in finding.message
        assert "missing the mandatory 'write' parameter" in finding.message
        assert finding.file_path == "/tmp/update.sh"
        assert finding.context == {"command_name": "no_write", "missing": "write_param"}

    # ID: 95f0fd71-553a-4e0e-9ad4-cdfc10e724d8
    def test_mutate_command_missing_both_conditions_produces_two_findings(
        self, check: DangerousExplicitCheck
    ) -> None:
        """A mutate command without dangerous=True and without write param generates two findings."""
        commands = [
            {
                "behavior": "mutate",
                "name": "double_offender",
                "dangerous": False,
                "params_list": ["other"],
                "file_path": "/tmp/bad.sh",
            }
        ]
        result = check.verify(commands, {})
        assert len(result) == 2
        missing_dangerous = any(f.context.get("missing") == "dangerous" for f in result)
        missing_write = any(f.context.get("missing") == "write_param" for f in result)
        assert missing_dangerous, "Expected a finding for missing dangerous flag"
        assert missing_write, "Expected a finding for missing write parameter"
        for finding in result:
            assert finding.check_id == "cli_gate.dangerous_explicit"
            assert finding.severity == AuditSeverity.BLOCK
            assert finding.file_path == "/tmp/bad.sh"

    # ID: e92dd375-7cdc-4d21-ac0a-601e8c138d1d
    def test_mutate_command_with_none_params_list_missing_write(
        self, check: DangerousExplicitCheck
    ) -> None:
        """A mutate command with params_list=None should trigger missing write finding."""
        commands = [
            {
                "behavior": "mutate",
                "name": "null_params",
                "dangerous": True,
                "params_list": None,
                "file_path": "/tmp/null.sh",
            }
        ]
        result = check.verify(commands, {})
        assert len(result) == 1
        assert result[0].context["missing"] == "write_param"

    # ID: 639fdfbf-09a9-4a7d-865e-fb78645996d5
    def test_mutate_command_with_empty_params_list_missing_write(
        self, check: DangerousExplicitCheck
    ) -> None:
        """A mutate command with params_list=[] should trigger missing write finding."""
        commands = [
            {
                "behavior": "mutate",
                "name": "empty_params",
                "dangerous": True,
                "params_list": [],
                "file_path": "/tmp/empty.sh",
            }
        ]
        result = check.verify(commands, {})
        assert len(result) == 1
        assert result[0].context["missing"] == "write_param"

    # ID: 09a31548-e762-4c83-8445-3dfd8e7447a4
    def test_multiple_mutate_commands_all_with_errors(
        self, check: DangerousExplicitCheck
    ) -> None:
        """Multiple problematic mutate commands each produce their own findings."""
        commands = [
            {
                "behavior": "mutate",
                "name": "cmd1",
                "dangerous": False,
                "params_list": ["write"],
                "file_path": "/tmp/1.sh",
            },
            {
                "behavior": "mutate",
                "name": "cmd2",
                "dangerous": True,
                "params_list": [],
                "file_path": "/tmp/2.sh",
            },
            {
                "behavior": "mutate",
                "name": "cmd3",
                "dangerous": False,
                "params_list": None,
                "file_path": "/tmp/3.sh",
            },
        ]
        result = check.verify(commands, {})
        # cmd1: 1 finding (missing dangerous)
        # cmd2: 1 finding (missing write)
        # cmd3: 2 findings (missing dangerous, missing write)
        assert len(result) == 4
        cmd1_findings = [f for f in result if f.context["command_name"] == "cmd1"]
        assert len(cmd1_findings) == 1
        assert cmd1_findings[0].context["missing"] == "dangerous"

        cmd2_findings = [f for f in result if f.context["command_name"] == "cmd2"]
        assert len(cmd2_findings) == 1
        assert cmd2_findings[0].context["missing"] == "write_param"

        cmd3_findings = [f for f in result if f.context["command_name"] == "cmd3"]
        assert len(cmd3_findings) == 2

    # ID: 500b0385-a2e5-405f-bebc-219875b6e40d
    def test_confirmation_shaped_field_does_not_substitute_for_write(
        self, check: DangerousExplicitCheck
    ) -> None:
        """#824: interactive confirmation MAY be an additional safeguard but
        MUST NOT replace --write. A command carrying a confirmation-shaped
        field but lacking dangerous=True and the write param is still a
        violation on both counts -- the check has no alternate acceptance
        path for confirmation, by design."""
        commands = [
            {
                "behavior": "mutate",
                "name": "confirm_only",
                "dangerous": False,
                "params_list": ["yes", "interactive"],
                "requires_confirmation": True,
                "file_path": "/tmp/confirm_only.sh",
            }
        ]
        result = check.verify(commands, {})
        assert len(result) == 2
        missing = {f.context["missing"] for f in result}
        assert missing == {"dangerous", "write_param"}

    # ID: bef37abd-8513-4c80-a96a-06d101caeba1
    def test_dangerous_and_write_satisfy_the_contract_even_with_confirmation(
        self, check: DangerousExplicitCheck
    ) -> None:
        """#824: confirmation as an ADDITIONAL safeguard alongside a correctly
        declared dangerous=True + write command produces no findings -- the
        corrected rule permits confirmation as a supplement, never as a
        substitute."""
        commands = [
            {
                "behavior": "mutate",
                "name": "belt_and_suspenders",
                "dangerous": True,
                "params_list": ["write", "yes"],
                "requires_confirmation": True,
                "file_path": "/tmp/belt_and_suspenders.sh",
            }
        ]
        result = check.verify(commands, {})
        assert result == []

    # ID: d4801c15-cf0f-4cc7-9bda-68442ce9d661
    def test_command_with_no_name_and_no_file_path(
        self, check: DangerousExplicitCheck
    ) -> None:
        """When command name and file_path are missing, the verify method uses defaults."""
        commands = [
            {
                "behavior": "mutate",
                "dangerous": False,
                "params_list": ["write"],
            }
        ]
        result = check.verify(commands, {})
        assert len(result) == 1
        finding = result[0]
        assert finding.context["command_name"] == ""
        assert finding.file_path == "none"





# ID: 6f94e13b-21af-41f5-9ddb-a584157fd254
def test_DangerousExplicitCheck_verify():
    check = DangerousExplicitCheck()
    commands = [
        {
            "behavior": "mutate",
            "name": "write_file",
            "file_path": "/tmp/x",
            "dangerous": True,
            "params_list": ["write", "path"],
        },
        {
            "behavior": "read",
            "name": "read_file",
            "file_path": "/tmp/y",
            "dangerous": False,
            "params_list": [],
        },
    ]
    params: dict = {}

    findings = check.verify(commands, params)

    assert findings == []
