import pytest

from mind.logic.engines.cli_gate.checks.dangerous_explicit import DangerousExplicitCheck
from shared.models import AuditSeverity


class TestDangerousExplicitCheck:
    @pytest.fixture
    def check(self) -> DangerousExplicitCheck:
        return DangerousExplicitCheck()

    def test_has_correct_check_type(self, check: DangerousExplicitCheck) -> None:
        """Verify the check_type class attribute is 'dangerous_explicit'."""
        assert check.check_type == "dangerous_explicit"

    def test_empty_commands_returns_empty_findings(
        self, check: DangerousExplicitCheck
    ) -> None:
        """When no commands are provided, verify returns no findings."""
        result = check.verify([], {})
        assert result == []

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
