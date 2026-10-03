from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock, patch

from mind.logic.engines.ast_gate.checks.capability_checks import CapabilityChecks


# ID: e654fd62-f3b5-4f27-9423-21d9575c4175
def test_CapabilityChecks_check_capability_assignment():
    repo_root = Path("/repo")
    intent_root = Path("/repo/intent")

    path_resolver = MagicMock()
    path_resolver.repo_root = repo_root
    path_resolver.intent_root = intent_root

    checker = CapabilityChecks(path_resolver)

    source = "def public_func():\n    pass\n"
    tree = ast.parse(source)
    file_path = repo_root / "src" / "module.py"

    graph = {"symbols": {"public_func": {"capability": "unassigned"}}}

    mock_kg_service = MagicMock()
    mock_kg_service.get_graph_sync.return_value = graph

    mock_public_symbols = [("public_func", 1)]
    mock_symbol_info = {"capability": "unassigned"}

    with (
        patch(
            "mind.logic.engines.ast_gate.checks.capability_checks.KnowledgeService",
            return_value=mock_kg_service,
        ),
        patch(
            "mind.logic.engines.ast_gate.checks.capability_checks._extract_public_symbols",
            return_value=mock_public_symbols,
        ),
        patch(
            "mind.logic.engines.ast_gate.checks.capability_checks._find_symbol_in_kg",
            return_value=mock_symbol_info,
        ),
    ):
        findings = checker.check_capability_assignment(tree, file_path=file_path)

    assert len(findings) == 1
    assert "public_func" in findings[0]
    assert "unassigned" in findings[0]


# ID: de53488a-a561-4c42-9768-b35040c3a20c
def test_CapabilityChecks():
    repo_root = Path("/repo")
    intent_root = Path("/repo/intent")

    path_resolver = MagicMock()
    path_resolver.repo_root = repo_root
    path_resolver.intent_root = intent_root

    checker = CapabilityChecks(path_resolver)

    source = "def public_func():\n    return 1\n"
    tree = ast.parse(source)
    file_path = Path("/repo/src/mind/mod.py")

    mock_graph = {
        "symbols": {
            "public_func": {"capability": "unassigned"},
        }
    }
    mock_kg_service = MagicMock()
    mock_kg_service.get_graph_sync.return_value = mock_graph

    with (
        patch(
            "mind.logic.engines.ast_gate.checks.capability_checks._extract_public_symbols",
            return_value=[("public_func", 1)],
        ),
        patch(
            "mind.logic.engines.ast_gate.checks.capability_checks._find_symbol_in_kg",
            return_value={"capability": "unassigned"},
        ),
        patch(
            "mind.logic.engines.ast_gate.checks.capability_checks.KnowledgeService",
            return_value=mock_kg_service,
        ),
    ):
        findings = checker.check_capability_assignment(tree, file_path=file_path)

    assert isinstance(findings, list)
    assert len(findings) == 1
    assert "public_func" in findings[0]
