"""Tests for ``api.openapi_document`` — the committed OpenAPI contract.

ADR-087 D9 (amended 2026-10-03) puts the authoritative contract in CORE; the
ADR-146 amendment of the same day makes it the boundary core-cli builds against.
These tests pin which routes the contract publishes and that the committed copy
matches what the code renders.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from api.openapi_document import OPENAPI_DOCUMENT, render_openapi_document


REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def rendered() -> str:
    return render_openapi_document()


@pytest.fixture(scope="module")
def spec(rendered: str) -> dict:
    return json.loads(rendered)


def test_render_is_stable_json_with_trailing_newline(rendered: str) -> None:
    assert rendered.endswith("}\n")
    assert rendered == render_openapi_document()


def test_carries_stability_policy(spec: dict) -> None:
    assert "x-stability-policy" in spec["info"]


@pytest.mark.parametrize(
    "path",
    [
        "/v1/lint",
        "/v1/quality/imports",
        "/v1/quality/tests",
        "/v1/integrity/baseline",
        "/v1/integrity/verify",
        "/v1/integrate",
    ],
)
def test_governed_repository_checks_are_public(spec: dict, path: str) -> None:
    """Consumer operations on the governed repository (ADR-146 amendment)."""
    assert path in spec["paths"]


@pytest.mark.parametrize(
    "path",
    [
        "/v1/quality/lint",
        "/v1/quality/system",
        "/v1/quality/gates",
        "/v1/quality/policy-coverage",
        "/v1/sync/vectors",
        "/v1/sync/code-vectors",
    ],
)
def test_internal_routes_stay_out_of_the_contract(spec: dict, path: str) -> None:
    assert path not in spec["paths"]


def test_quality_imports_takes_no_body(spec: dict) -> None:
    """The ignored ``target_files`` parameter is gone from the contract."""
    assert "requestBody" not in spec["paths"]["/v1/quality/imports"]["post"]


def test_committed_copy_is_current(rendered: str) -> None:
    """``core-admin docs generate --write`` refreshes the committed copy."""
    committed = (REPO_ROOT / OPENAPI_DOCUMENT).read_text(encoding="utf-8")
    assert committed == rendered, (
        f"{OPENAPI_DOCUMENT} is stale — run `core-admin docs generate --write`"
    )
