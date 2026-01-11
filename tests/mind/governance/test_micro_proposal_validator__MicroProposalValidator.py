"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/mind/governance/micro_proposal_validator.py
- Symbol: MicroProposalValidator
- Status: verified_in_sandbox
- Generated: 2026-01-11 02:06:50
"""

import pytest
from mind.governance.micro_proposal_validator import MicroProposalValidator

# Detected return type: validate() returns tuple[bool, str] (synchronous)


class TestMicroProposalValidator:
    """Unit tests for MicroProposalValidator.validate()"""

    def test_empty_plan(self):
        """Empty plan should fail validation"""
        validator = MicroProposalValidator()
        result = validator.validate([])
        assert result == (False, "Plan is empty")

    def test_non_list_input(self):
        """Non-list input should fail validation"""
        validator = MicroProposalValidator()
        result = validator.validate({})
        assert result == (False, "Plan is empty")

    def test_step_missing_action(self):
        """Step without action should fail validation"""
        validator = MicroProposalValidator()
        plan = [{"name": None, "parameters": {"file_path": "/tmp/test.txt"}}]
        result = validator.validate(plan)
        assert result == (False, "Step 1 missing action")

    def test_step_with_action_but_no_file_path(self):
        """Step with action but no file_path should pass validation"""
        validator = MicroProposalValidator()
        plan = [{"action": "read", "parameters": {"content": "test"}}]
        result = validator.validate(plan)
        assert result == (True, "")

    def test_step_with_model_dump_support(self):
        """Step with model_dump() method should be properly converted"""
        class MockPydanticModel:
            def model_dump(self):
                return {"action": "write", "parameters": {"file_path": "/allowed/path.txt"}}

        validator = MicroProposalValidator()
        # Mock the policy to allow the path
        validator._allowed = ["/allowed/*"]
        validator._forbidden = []

        plan = [MockPydanticModel()]
        result = validator.validate(plan)
        assert result == (True, "")

    def test_forbidden_path_detection(self):
        """Forbidden paths should be detected and rejected"""
        validator = MicroProposalValidator()
        validator._allowed = []
        validator._forbidden = ["/etc/*", "/root/*"]

        plan = [{"action": "read", "parameters": {"file_path": "/etc/passwd"}}]
        result = validator.validate(plan)
        assert result == (False, "Path '/etc/passwd' is explicitly forbidden by policy")

    def test_path_not_in_allowed_list(self):
        """Paths not in allowed list should be rejected when allowed list exists"""
        validator = MicroProposalValidator()
        validator._allowed = ["/home/user/*", "/tmp/*"]
        validator._forbidden = []

        plan = [{"action": "write", "parameters": {"file_path": "/var/log/test.log"}}]
        result = validator.validate(plan)
        assert result == (False, "Path '/var/log/test.log' not in allowed paths")

    def test_path_in_allowed_list(self):
        """Paths in allowed list should pass validation"""
        validator = MicroProposalValidator()
        validator._allowed = ["/home/user/*", "/tmp/*"]
        validator._forbidden = []

        plan = [{"action": "read", "parameters": {"file_path": "/tmp/tempfile.txt"}}]
        result = validator.validate(plan)
        assert result == (True, "")

    def test_multiple_steps_all_valid(self):
        """Multiple steps with valid file paths should pass"""
        validator = MicroProposalValidator()
        validator._allowed = ["/project/*", "/docs/*"]
        validator._forbidden = ["/system/*"]

        plan = [
            {"action": "create", "params": {"file_path": "/project/src/main.py"}},
            {"name": "update", "parameters": {"file_path": "/docs/README.md"}}
        ]
        result = validator.validate(plan)
        assert result == (True, "")

    def test_multiple_steps_with_invalid_middle_step(self):
        """Validation should fail on first invalid step"""
        validator = MicroProposalValidator()
        validator._allowed = ["/project/*"]
        validator._forbidden = ["/system/*"]

        plan = [
            {"action": "create", "parameters": {"file_path": "/project/src/main.py"}},
            {"action": "read", "parameters": {"file_path": "/system/config"}},
            {"action": "update", "parameters": {"file_path": "/project/test.py"}}
        ]
        result = validator.validate(plan)
        assert result == (False, "Path '/system/config' is explicitly forbidden by policy")

    def test_empty_allowed_list_permits_any_non_forbidden(self):
        """Empty allowed list should permit any path that's not forbidden"""
        validator = MicroProposalValidator()
        validator._allowed = []
        validator._forbidden = ["/secret/*"]

        plan = [{"action": "read", "parameters": {"file_path": "/any/path/file.txt"}}]
        result = validator.validate(plan)
        assert result == (True, "")

    def test_fnmatch_pattern_matching(self):
        """fnmatch patterns should work correctly for path matching"""
        validator = MicroProposalValidator()
        validator._allowed = ["/home/user/*.py", "/tmp/test_*.txt"]
        validator._forbidden = ["*.bak", "*.tmp"]

        # Test allowed pattern matching
        plan1 = [{"action": "read", "parameters": {"file_path": "/home/user/script.py"}}]
        result1 = validator.validate(plan1)
        assert result1 == (True, "")

        # Test forbidden pattern matching
        plan2 = [{"action": "write", "parameters": {"file_path": "/home/user/backup.bak"}}]
        result2 = validator.validate(plan2)
        assert result2 == (False, "Path '/home/user/backup.bak' is explicitly forbidden by policy")

    def test_step_with_params_key_instead_of_parameters(self):
        """Should handle 'params' key as alternative to 'parameters'"""
        validator = MicroProposalValidator()
        validator._allowed = ["/test/*"]
        validator._forbidden = []

        plan = [{"action": "read", "params": {"file_path": "/test/file.txt"}}]
        result = validator.validate(plan)
        assert result == (True, "")

    def test_step_with_name_key_instead_of_action(self):
        """Should handle 'name' key as alternative to 'action'"""
        validator = MicroProposalValidator()
        validator._allowed = ["/test/*"]
        validator._forbidden = []

        plan = [{"name": "read_file", "parameters": {"file_path": "/test/file.txt"}}]
        result = validator.validate(plan)
        assert result == (True, "")

    def test_file_path_not_string_type(self):
        """Non-string file_path should be ignored (not cause validation failure)"""
        validator = MicroProposalValidator()

        # file_path as integer
        plan = [{"action": "read", "parameters": {"file_path": 123}}]
        result = validator.validate(plan)
        assert result == (True, "")

        # file_path as None
        plan2 = [{"action": "write", "parameters": {"file_path": None}}]
        result2 = validator.validate(plan2)
        assert result2 == (True, "")

    def test_validation_stops_at_first_error(self):
        """Validation should stop and return at first failing step"""
        validator = MicroProposalValidator()
        validator._allowed = []
        validator._forbidden = ["/bad/*"]

        plan = [
            {"action": "step1", "parameters": {"file_path": "/bad/path1"}},
            {"action": "step2", "parameters": {"file_path": "/bad/path2"}}
        ]
        result = validator.validate(plan)
        # Should only report first error
        assert result == (False, "Path '/bad/path1' is explicitly forbidden by policy")
        assert "path2" not in result[1]
