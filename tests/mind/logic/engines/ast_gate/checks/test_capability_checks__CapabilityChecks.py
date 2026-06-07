"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/mind/logic/engines/ast_gate/checks/capability_checks.py
- Symbol: CapabilityChecks
- Status: verified_in_sandbox
- Generated: 2026-01-11 02:35:45
- 2026-06-07 (#572 Cat B batch 14):
    * CapabilityChecks is no longer a stateless class — its __init__
      takes a PathResolver, and ``check_capability_assignment`` is an
      instance method that consults ``self._paths`` for capability-
      taxonomy lookups. The autogen vintage called the method
      classmethod-style (``CapabilityChecks.check_capability_assignment(
      tree=..., file_path=..., source=None)``), tripping
      ``TypeError: missing 1 required positional argument: 'self'``.
      Tests now thread a ``checks`` fixture that constructs the class
      with a MagicMock PathResolver — the path_resolver attribute is
      only consulted on KG-lookup paths the tests below don't exercise.
"""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from mind.logic.engines.ast_gate.checks.capability_checks import CapabilityChecks


@pytest.fixture
def checks() -> CapabilityChecks:
    """CapabilityChecks instance backed by a MagicMock PathResolver. The
    method exercised below short-circuits on test-file / script-file /
    no-public-symbol paths before ever touching ``self._paths``."""
    return CapabilityChecks(path_resolver=MagicMock())


def test_check_capability_assignment_returns_empty_list_for_test_files(checks):
    """Test files are excluded — short-circuited before the KG lookup."""
    test_file_path = Path("/repo/tests/test_module.py")
    tree = ast.parse("def public_func(): pass")
    result = checks.check_capability_assignment(
        tree=tree, file_path=test_file_path, source=None
    )
    assert result == []


def test_check_capability_assignment_returns_empty_list_for_scripts(checks):
    """Script files are excluded — short-circuited before the KG lookup."""
    script_file_path = Path("/repo/scripts/run.py")
    tree = ast.parse("def public_func(): pass")
    result = checks.check_capability_assignment(
        tree=tree, file_path=script_file_path, source=None
    )
    assert result == []


def test_check_capability_assignment_returns_empty_list_for_no_public_symbols(checks):
    """Files with only private symbols (underscore-prefixed) return empty
    findings — the public-symbol scan finds nothing to check."""
    file_path = Path("/repo/src/module.py")
    tree = ast.parse("def _private_func(): pass")
    result = checks.check_capability_assignment(
        tree=tree, file_path=file_path, source=None
    )
    assert result == []


def test_check_capability_assignment_handles_exception_gracefully(checks):
    """A file with public symbols reaches the KG-lookup path; with a
    MagicMock path_resolver the lookup is non-functional but the source's
    broad except returns an empty list rather than propagating. The
    invariant the test pins: the call returns a list, no raise."""
    file_path = Path("/repo/src/module.py")
    tree = ast.parse("def public_func(): pass\nclass PublicClass: pass")
    result = checks.check_capability_assignment(
        tree=tree, file_path=file_path, source=None
    )
    assert isinstance(result, list)
