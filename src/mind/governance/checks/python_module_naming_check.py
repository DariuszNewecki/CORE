# src/mind/governance/checks/python_module_naming_check.py
"""
Enforces Python module naming conventions.

Verifies:
- code.python_module_naming - All Python files must use snake_case
- code.python_test_module_naming - Test files must be prefixed with 'test_'

Ref: .intent/charter/standards/code_standards.json
"""

from __future__ import annotations

import re
from typing import Any, ClassVar

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.rule_enforcement_check import (
    EnforcementMethod,
    RuleEnforcementCheck,
)
from shared.config import settings
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)

# Valid snake_case pattern: lowercase letters, numbers, underscores only
SNAKE_CASE_PATTERN = re.compile(r"^[a-z0-9_]+$")


# ID: python-module-naming-enforcement
# ID: f1e2d3c4-b5a6-7c8d-9e0f-1a2b3c4d5e6f
class PythonModuleNamingEnforcement(EnforcementMethod):
    """
    Verifies that Python module names use snake_case.

    Valid: my_module.py, data_processor.py, utils.py
    Invalid: MyModule.py, dataProcessor.py, Data-Processor.py
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: a9b8c7d6-e5f4-3a2b-1c0d-9e8f7a6b5c4d
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        findings = []

        for file_path in context.python_files:
            rel_path = str(file_path.relative_to(context.repo_path))
            filename = file_path.name

            # Skip __init__.py - it's always valid
            if filename == "__init__.py":
                continue

            # Remove .py extension for validation
            module_name = filename[:-3] if filename.endswith(".py") else filename

            # Check if it's snake_case
            if not SNAKE_CASE_PATTERN.match(module_name):
                findings.append(
                    self._create_finding(
                        message=f"Python module '{filename}' must use snake_case naming. Found: '{module_name}'",
                        file_path=rel_path,
                        line_number=1,
                    )
                )

        return findings


# ID: python-test-naming-enforcement
# ID: b2c3d4e5-f6a7-8b9c-0d1e-2f3a4b5c6d7e
class PythonTestNamingEnforcement(EnforcementMethod):
    """
    Verifies that Python test files are prefixed with 'test_'.

    Valid: test_utils.py, test_data_processor.py
    Invalid: utils_test.py, processor.py (in tests/ directory)
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: c3d4e5f6-a7b8-9c0d-1e2f-3a4b5c6d7e8f
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        findings = []

        for file_path in context.python_files:
            rel_path = str(file_path.relative_to(context.repo_path))
            filename = file_path.name

            # Check if this is a test file (in tests/ directory or contains 'test' in path)
            path_str = rel_path.replace("\\", "/")
            is_test_file = (
                "tests/" in path_str
                or path_str.startswith("tests/")
                or "/test_" in path_str
            )

            if not is_test_file:
                continue

            # Skip __init__.py
            if filename == "__init__.py":
                continue

            # Test files must start with test_
            if not filename.startswith("test_"):
                findings.append(
                    self._create_finding(
                        message=f"Test file '{filename}' must be prefixed with 'test_'. Rename to 'test_{filename}'",
                        file_path=rel_path,
                        line_number=1,
                    )
                )

        return findings


# ID: d4e5f6a7-b8c9-0d1e-2f3a-4b5c6d7e8f9a
class PythonModuleNamingCheck(RuleEnforcementCheck):
    """
    Enforces Python module naming conventions.

    Ref: .intent/charter/standards/code_standards.json
    """

    policy_rule_ids: ClassVar[list[str]] = [
        "code.python_module_naming",
        "code.python_test_module_naming",
    ]

    policy_file: ClassVar = settings.paths.policy("code_standards")

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        PythonModuleNamingEnforcement(
            rule_id="code.python_module_naming",
            severity=AuditSeverity.ERROR,
        ),
        PythonTestNamingEnforcement(
            rule_id="code.python_test_module_naming",
            severity=AuditSeverity.ERROR,
        ),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
