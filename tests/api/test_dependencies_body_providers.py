"""api.dependencies is the DI root for Body services the API needs (no_body_bypass)."""

from __future__ import annotations

import ast
from pathlib import Path

from api.dependencies import (
    get_capability_docs_generator,
    get_drift_analysis,
    get_scout_analyzer,
)
from body.analyzers.scout_analyzer import ScoutAnalyzer
from body.introspection.drift_service import run_drift_analysis_async
from body.introspection.generate_capability_docs import main as generate_docs_main


def test_scout_analyzer_provider_returns_a_fresh_analyzer() -> None:
    first, second = get_scout_analyzer(), get_scout_analyzer()
    assert isinstance(first, ScoutAnalyzer)
    assert first is not second


def test_drift_and_docs_providers_return_the_body_callables() -> None:
    assert get_drift_analysis() is run_drift_analysis_async
    assert get_capability_docs_generator() is generate_docs_main


def test_v1_routes_import_no_body_module() -> None:
    """Regression (governor inbox 2026-10-02): routes took Body services by
    direct import; they now receive them from api.dependencies."""
    routes = Path(__file__).resolve().parents[2] / "src" / "api" / "v1"
    offenders: list[str] = []
    for path in sorted(routes.glob("*_routes.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                "body"
            ):
                offenders.append(f"{path.name}: from {node.module}")
            elif isinstance(node, ast.Import):
                offenders += [
                    f"{path.name}: import {a.name}"
                    for a in node.names
                    if a.name.startswith("body")
                ]
    assert offenders == []
