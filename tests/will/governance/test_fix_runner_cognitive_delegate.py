# tests/will/governance/test_fix_runner_cognitive_delegate.py
"""Tests for fix_runner._build_cognitive_delegate (ADR-140 D9 pattern, #769).

Mirrors ProposalExecutor._build_cognitive_delegate's routing-by-
cognitive_capability logic, extended to the governor CLI/API dispatch
path (run_and_persist_flow), which flows with cognitive steps did not
previously reach.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from will.governance.fix_runner import _build_cognitive_delegate


def test_returns_none_for_unknown_flow_id() -> None:
    with patch("will.governance.fix_runner.flow_registry") as mock_registry:
        mock_registry.get.return_value = None
        result = _build_cognitive_delegate("flow.does_not_exist", MagicMock())
    assert result is None


def test_returns_none_when_flow_has_no_cognitive_steps() -> None:
    from body.flows.registry import StepKind

    flow_def = MagicMock()
    flow_def.steps = [MagicMock(kind=StepKind.ACTION)]

    with patch("will.governance.fix_runner.flow_registry") as mock_registry:
        mock_registry.get.return_value = flow_def
        result = _build_cognitive_delegate("flow.fix_code", MagicMock())
    assert result is None


def test_routes_modularity_analysis_to_modularity_delegate() -> None:
    from body.flows.registry import StepKind
    from will.agents.modularity_cognitive_delegate import ModularityCognitiveDelegate

    flow_def = MagicMock()
    flow_def.steps = [MagicMock(kind=StepKind.COGNITIVE)]
    flow_def.cognitive_capability = "modularity_analysis"

    with patch("will.governance.fix_runner.flow_registry") as mock_registry:
        mock_registry.get.return_value = flow_def
        result = _build_cognitive_delegate("flow.fix_modularity", MagicMock())

    assert isinstance(result, ModularityCognitiveDelegate)


def test_routes_test_generation_to_test_gen_delegate() -> None:
    from body.flows.registry import StepKind
    from will.agents.test_gen_cognitive_delegate import TestGenCognitiveDelegate

    flow_def = MagicMock()
    flow_def.steps = [MagicMock(kind=StepKind.COGNITIVE)]
    flow_def.cognitive_capability = "test_generation"

    with patch("will.governance.fix_runner.flow_registry") as mock_registry:
        mock_registry.get.return_value = flow_def
        result = _build_cognitive_delegate("flow.build_test_for_symbol", MagicMock())

    assert isinstance(result, TestGenCognitiveDelegate)


def test_returns_none_for_unregistered_capability() -> None:
    from body.flows.registry import StepKind

    flow_def = MagicMock()
    flow_def.steps = [MagicMock(kind=StepKind.COGNITIVE)]
    flow_def.cognitive_capability = "some_future_capability"

    with patch("will.governance.fix_runner.flow_registry") as mock_registry:
        mock_registry.get.return_value = flow_def
        result = _build_cognitive_delegate("flow.future", MagicMock())

    assert result is None
