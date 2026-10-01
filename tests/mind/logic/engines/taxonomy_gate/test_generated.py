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
