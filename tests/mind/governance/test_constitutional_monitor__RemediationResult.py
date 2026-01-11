"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/mind/governance/constitutional_monitor.py
- Symbol: RemediationResult
- Status: verified_in_sandbox
- Generated: 2026-01-11 01:21:37
"""

import pytest
from mind.governance.constitutional_monitor import RemediationResult

# Detected return type: RemediationResult is a dataclass-like class, not a function.
# It is synchronous, not async.

def test_remediation_result_creation_with_defaults():
    """Test creating a RemediationResult with only required fields."""
    result = RemediationResult(success=True, fixed_count=5, failed_count=2)
    assert result.success == True
    assert result.fixed_count == 5
    assert result.failed_count == 2
    assert result.error == None

def test_remediation_result_creation_with_error():
    """Test creating a RemediationResult with an error message."""
    result = RemediationResult(
        success=False,
        fixed_count=0,
        failed_count=10,
        error="Validation failed"
    )
    assert result.success == False
    assert result.fixed_count == 0
    assert result.failed_count == 10
    assert result.error == "Validation failed"

def test_remediation_result_equality():
    """Test that two instances with the same data are equal."""
    result1 = RemediationResult(success=True, fixed_count=1, failed_count=0, error=None)
    result2 = RemediationResult(success=True, fixed_count=1, failed_count=0, error=None)
    # Using '==' for value comparison as per rules
    assert result1 == result2

def test_remediation_result_inequality():
    """Test that instances with different data are not equal."""
    result1 = RemediationResult(success=True, fixed_count=1, failed_count=0)
    result2 = RemediationResult(success=False, fixed_count=1, failed_count=0)
    assert result1 != result2
