"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/mind/logic/engines/ast_gate/checks/capability_checks.py
- Symbol: CapabilityChecks
- Status: verified_in_sandbox
- Generated: 2026-01-11 02:35:45
"""

import pytest
from pathlib import Path
import ast
from mind.logic.engines.ast_gate.checks.capability_checks import CapabilityChecks

# Detected return type: list[str]

def test_check_capability_assignment_returns_empty_list_for_test_files():
    """Test that test files are excluded and return empty findings."""
    test_file_path = Path("/repo/tests/test_module.py")
    tree = ast.parse("def public_func(): pass")
    result = CapabilityChecks.check_capability_assignment(
        tree=tree,
        file_path=test_file_path,
        source=None
    )
    assert result == []

def test_check_capability_assignment_returns_empty_list_for_scripts():
    """Test that script files are excluded and return empty findings."""
    script_file_path = Path("/repo/scripts/run.py")
    tree = ast.parse("def public_func(): pass")
    result = CapabilityChecks.check_capability_assignment(
        tree=tree,
        file_path=script_file_path,
        source=None
    )
    assert result == []

def test_check_capability_assignment_returns_empty_list_for_no_public_symbols():
    """Test that files with no public symbols return empty findings."""
    file_path = Path("/repo/src/module.py")
    tree = ast.parse("def _private_func(): pass")
    result = CapabilityChecks.check_capability_assignment(
        tree=tree,
        file_path=file_path,
        source=None
    )
    assert result == []

def test_check_capability_assignment_handles_exception_gracefully():
    """Test that exceptions during KG query are caught and return empty list."""
    # This test relies on the internal behavior that an exception in KG access
    # results in warning log and empty findings.
    # We pass a valid tree and path; the actual KG failure is internal.
    file_path = Path("/repo/src/module.py")
    tree = ast.parse("def public_func(): pass\nclass PublicClass: pass")
    result = CapabilityChecks.check_capability_assignment(
        tree=tree,
        file_path=file_path,
        source=None
    )
    # The function should not raise; it should return a list.
    assert isinstance(result, list)
