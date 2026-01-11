"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/body/evaluators/atomic_actions_evaluator.py
- Symbol: AtomicActionViolation
- Status: verified_in_sandbox
- Generated: 2026-01-11 03:28:17
"""

from pathlib import Path

from body.evaluators.atomic_actions_evaluator import AtomicActionViolation


# Detected return type: AtomicActionViolation is a dataclass-like class, not a function
# Tests will verify proper initialization and attribute access


def test_atomic_action_violation_initialization_with_required_fields():
    """Test basic initialization with required fields only."""
    violation = AtomicActionViolation(
        file_path=Path("/full/path/to/file.py"),
        function_name="test_function",
        rule_id="ATOMIC_001",
        message="Function violates atomic action pattern",
    )

    assert violation.file_path == Path("/full/path/to/file.py")
    assert violation.function_name == "test_function"
    assert violation.rule_id == "ATOMIC_001"
    assert violation.message == "Function violates atomic action pattern"
    assert violation.line_number is None
    assert violation.severity == "error"
    assert violation.suggested_fix is None


def test_atomic_action_violation_initialization_with_all_fields():
    """Test initialization with all fields provided."""
    violation = AtomicActionViolation(
        file_path=Path("/another/path/module.py"),
        function_name="process_data",
        rule_id="ATOMIC_002",
        message="Function contains multiple responsibilities",
        line_number=42,
        severity="warning",
        suggested_fix="Split into separate atomic functions",
    )

    assert violation.file_path == Path("/another/path/module.py")
    assert violation.function_name == "process_data"
    assert violation.rule_id == "ATOMIC_002"
    assert violation.message == "Function contains multiple responsibilities"
    assert violation.line_number == 42
    assert violation.severity == "warning"
    assert violation.suggested_fix == "Split into separate atomic functions"


def test_atomic_action_violation_with_custom_severity():
    """Test initialization with custom severity value."""
    violation = AtomicActionViolation(
        file_path=Path("/path/to/file.py"),
        function_name="validate_input",
        rule_id="ATOMIC_003",
        message="Function does too much validation",
        severity="info",
    )

    assert violation.severity == "info"
    assert violation.file_path == Path("/path/to/file.py")
    assert violation.function_name == "validate_input"


def test_atomic_action_violation_with_line_number_only():
    """Test initialization with line_number but no suggested_fix."""
    violation = AtomicActionViolation(
        file_path=Path("/full/path.py"),
        function_name="calculate",
        rule_id="ATOMIC_004",
        message="Function mixes calculation and I/O",
        line_number=15,
    )

    assert violation.line_number == 15
    assert violation.suggested_fix is None
    assert violation.severity == "error"  # Default value


def test_atomic_action_violation_with_suggested_fix_only():
    """Test initialization with suggested_fix but no line_number."""
    violation = AtomicActionViolation(
        file_path=Path("/complete/path.py"),
        function_name="handle_request",
        rule_id="ATOMIC_005",
        message="Function handles both parsing and processing",
        suggested_fix="Extract parsing logic to separate function",
    )

    assert violation.suggested_fix == "Extract parsing logic to separate function"
    assert violation.line_number is None
    assert violation.severity == "error"  # Default value


def test_atomic_action_violation_file_path_equality():
    """Test that file_path comparisons work correctly with Path objects."""
    violation1 = AtomicActionViolation(
        file_path=Path("/same/path.py"),
        function_name="func1",
        rule_id="ATOMIC_006",
        message="Message 1",
    )

    violation2 = AtomicActionViolation(
        file_path=Path("/same/path.py"),
        function_name="func2",
        rule_id="ATOMIC_007",
        message="Message 2",
    )

    assert violation1.file_path == violation2.file_path
    assert str(violation1.file_path) == "/same/path.py"


def test_atomic_action_violation_attribute_immutability():
    """Test that attributes can be accessed but are not meant to be modified (frozen-like)."""
    violation = AtomicActionViolation(
        file_path=Path("/test/path.py"),
        function_name="original_func",
        rule_id="ATOMIC_008",
        message="Original message",
    )

    # Verify initial values
    assert violation.function_name == "original_func"
    assert violation.message == "Original message"

    # Note: The class doesn't appear to be frozen, but we're testing the initial state
    # In practice, these would likely be treated as immutable


def test_atomic_action_violation_with_empty_strings():
    """Test initialization with empty string values where allowed."""
    violation = AtomicActionViolation(
        file_path=Path("/path.py"), function_name="", rule_id="", message=""
    )

    assert violation.function_name == ""
    assert violation.rule_id == ""
    assert violation.message == ""
    assert violation.severity == "error"  # Default unchanged


def test_atomic_action_violation_with_none_values_explicit():
    """Test explicit None values for optional fields."""
    violation = AtomicActionViolation(
        file_path=Path("/explicit/path.py"),
        function_name="func",
        rule_id="ATOMIC_009",
        message="Test message",
        line_number=None,
        suggested_fix=None,
    )

    assert violation.line_number is None
    assert violation.suggested_fix is None
    assert violation.severity == "error"  # Default


def test_multiple_atomic_action_violations_distinct():
    """Test that multiple instances maintain separate attribute values."""
    violation1 = AtomicActionViolation(
        file_path=Path("/first.py"),
        function_name="first_func",
        rule_id="ATOMIC_010",
        message="First violation",
    )

    violation2 = AtomicActionViolation(
        file_path=Path("/second.py"),
        function_name="second_func",
        rule_id="ATOMIC_011",
        message="Second violation",
        line_number=100,
        severity="critical",
    )

    assert violation1.file_path != violation2.file_path
    assert violation1.function_name != violation2.function_name
    assert violation1.rule_id != violation2.rule_id
    assert violation1.message != violation2.message
    assert violation1.line_number != violation2.line_number
    assert violation1.severity != violation2.severity
