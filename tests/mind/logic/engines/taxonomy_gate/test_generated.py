from __future__ import annotations

from unittest.mock import MagicMock

from mind.logic.engines.taxonomy_gate import (
    _DECORATOR_BACKING_CHECK,
    TaxonomyGateEngine,
)


# ID: 132ecf7d-924c-492b-85fc-2e8746ba48b1
async def test_TaxonomyGateEngine_verify_context() -> None:
    resolver = MagicMock()
    engine = TaxonomyGateEngine(path_resolver=resolver)

    context = MagicMock()
    context.repo_path = "/repo/root"

    expected_findings = [MagicMock(name="finding")]
    engine._build_decorator_backing_findings = MagicMock(return_value=expected_findings)

    params = {"check_type": _DECORATOR_BACKING_CHECK}

    result = await engine.verify_context(context, params)

    engine._build_decorator_backing_findings.assert_called_once_with("/repo/root")
    assert result == expected_findings


from pathlib import Path
from typing import Any

import pytest


@pytest.mark.asyncio
# ID: 0bb4ffc7-6a20-4322-9780-3506f8e5d4ea
async def test_taxonomy_gate_engine_verify() -> None:
    path_resolver = MagicMock()
    engine = TaxonomyGateEngine(path_resolver=path_resolver)

    params: dict[str, Any] = {"check_type": "taxonomy_alignment"}

    result = await engine.verify(
        Path("src/mind/logic/engines/taxonomy_gate.py"), params
    )

    assert result.ok is False
    assert result.violations == []
    assert "context-level" in result.message
    assert "verify_context" in result.message
    assert "taxonomy_alignment" in result.message





# ID: 940b9066-6920-4bec-b78d-c1830ef94820
def test_TaxonomyGateEngine_is_context_level_for() -> None:
    path_resolver = MagicMock()
    engine = TaxonomyGateEngine(path_resolver=path_resolver)

    assert (
        engine.is_context_level_for("operational_capabilities_decorator_backing")
        is True
    )
    assert engine.is_context_level_for("sensor_supported_by_declaration") is True
    assert engine.is_context_level_for("self_resolve_resolver_owned") is True
    assert engine.is_context_level_for("action_supported_by_declaration") is True
    assert engine.is_context_level_for("exemption_debt_declared") is True
    assert engine.is_context_level_for("some_other_check") is False
    assert engine.is_context_level_for(None) is False
