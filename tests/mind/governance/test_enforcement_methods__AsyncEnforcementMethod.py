"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/mind/governance/enforcement_methods.py
- Symbol: AsyncEnforcementMethod
- Status: verified_in_sandbox
- Generated: 2026-01-11 01:40:45
"""

import pytest
from mind.governance.enforcement_methods import AsyncEnforcementMethod
from mind.governance.enforcement_methods import AuditSeverity, AuditFinding
from typing import Any

# DETECTED: AsyncEnforcementMethod is an abstract base class (ABC) with an async abstract method 'verify_async'.
# Therefore, test functions that instantiate and test concrete implementations must be async.
# We will create a concrete test subclass for testing.

class ConcreteAsyncEnforcer(AsyncEnforcementMethod):
    """Concrete implementation for testing the abstract base class."""
    async def verify_async(self, context: Any, rule_data: dict[str, Any]) -> list[AuditFinding]:
        # Simple implementation that returns a finding using the helper method
        return [self._create_finding("Test finding", "/full/path/to/file.txt", 42)]

@pytest.mark.asyncio
async def test_async_enforcement_method_initialization():
    """Test that AsyncEnforcementMethod initializes with correct rule_id and severity."""
    rule_id = "test_rule_123"
    severity = AuditSeverity.WARNING

    enforcer = ConcreteAsyncEnforcer(rule_id=rule_id, severity=severity)

    assert enforcer.rule_id == rule_id
    assert enforcer.severity == severity

@pytest.mark.asyncio
async def test_async_enforcement_method_default_severity():
    """Test that AsyncEnforcementMethod uses ERROR as default severity."""
    rule_id = "test_rule_456"

    enforcer = ConcreteAsyncEnforcer(rule_id=rule_id)

    assert enforcer.rule_id == rule_id
    assert enforcer.severity == AuditSeverity.ERROR

@pytest.mark.asyncio
async def test_async_enforcement_method_create_finding_with_all_params():
    """Test the _create_finding helper method with all parameters provided."""
    rule_id = "test_rule_789"
    severity = AuditSeverity.INFO
    message = "Test finding message"
    file_path = "/absolute/path/to/source.py"
    line_number = 100

    enforcer = ConcreteAsyncEnforcer(rule_id=rule_id, severity=severity)
    finding = enforcer._create_finding(
        message=message,
        file_path=file_path,
        line_number=line_number
    )

    assert finding.check_id == rule_id
    assert finding.severity == severity
    assert finding.message == message
    assert finding.file_path == file_path
    assert finding.line_number == line_number

@pytest.mark.asyncio
async def test_async_enforcement_method_create_finding_without_optional_params():
    """Test the _create_finding helper method without optional file_path and line_number."""
    rule_id = "test_rule_abc"
    severity = AuditSeverity.ERROR
    message = "Another test finding"

    enforcer = ConcreteAsyncEnforcer(rule_id=rule_id, severity=severity)
    finding = enforcer._create_finding(message=message)

    assert finding.check_id == rule_id
    assert finding.severity == severity
    assert finding.message == message
    assert finding.file_path is None
    assert finding.line_number is None

@pytest.mark.asyncio
async def test_async_enforcement_method_verify_async_returns_list_of_findings():
    """Test that verify_async method returns a list of AuditFinding objects."""
    rule_id = "test_rule_def"
    enforcer = ConcreteAsyncEnforcer(rule_id=rule_id)

    # Create dummy context and rule_data
    context = object()
    rule_data = {"key": "value"}

    findings = await enforcer.verify_async(context=context, rule_data=rule_data)

    assert isinstance(findings, list)
    assert len(findings) == 1
    assert isinstance(findings[0], AuditFinding)
    assert findings[0].check_id == rule_id
    assert findings[0].message == "Test finding"
    assert findings[0].file_path == "/full/path/to/file.txt"
    assert findings[0].line_number == 42

@pytest.mark.asyncio
async def test_async_enforcement_method_cannot_instantiate_abstract_class():
    """Test that AsyncEnforcementMethod cannot be instantiated directly due to abstract method."""
    with pytest.raises(TypeError):
        # This should fail because verify_async is abstract
        AsyncEnforcementMethod(rule_id="abstract_test")
