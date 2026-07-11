# tests/api/v1/test_scout_route.py

"""Tests for POST /project/scout route."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from api.v1.scout_routes import ScoutRequest, scout_project


def _make_request(repo_path: str = "/opt/dev/CORE") -> MagicMock:
    req = MagicMock()
    req.app.state.core_context.git_service.repo_path = Path(repo_path)
    req.app.state.core_context.cognitive_service = None
    return req


def _mock_analysis(
    ok: bool = True, signals_text: str = "signals", signals_raw: dict | None = None
) -> MagicMock:
    result = MagicMock()
    result.ok = ok
    result.data = {
        "signals_text": signals_text,
        "signals_raw": signals_raw or {"total_py_files": 3},
        "cache_key": "abc123",
    }
    return result


_SAMPLE_CANDIDATES = [
    {
        "rule_id": "scout.no_bare_except",
        "statement": "No bare except.",
        "enforcement": "blocking",
        "rationale": "hides bugs",
        "enforcement_matched": True,
        "engine": "regex_gate",
        "params": {},
        "scope": {"applies_to": ["**/*.py"], "excludes": []},
    }
]


# ---------------------------------------------------------------------------
# Missing .intent/ → 400
# ---------------------------------------------------------------------------


async def test_scout_no_intent_dir_raises_400(tmp_path: Path) -> None:
    body = ScoutRequest(path=str(tmp_path))
    request = _make_request()

    with pytest.raises(HTTPException) as exc_info:
        await scout_project(body=body, request=request)
    assert exc_info.value.status_code == 400
    assert ".intent/" in exc_info.value.detail


# ---------------------------------------------------------------------------
# Existing inducted rules + no reset → 409
# ---------------------------------------------------------------------------


async def test_scout_existing_inducted_no_reset_raises_409(tmp_path: Path) -> None:
    intent = tmp_path / ".intent" / "rules"
    intent.mkdir(parents=True)
    (intent / "scout_inducted.json").write_text("{}")

    body = ScoutRequest(path=str(tmp_path), reset=False)
    request = _make_request()

    with pytest.raises(HTTPException) as exc_info:
        await scout_project(body=body, request=request)
    assert exc_info.value.status_code == 409


# ---------------------------------------------------------------------------
# Happy path — fallback candidates returned
# ---------------------------------------------------------------------------


async def test_scout_happy_path_fallback(tmp_path: Path) -> None:
    (tmp_path / ".intent").mkdir()

    body = ScoutRequest(path=str(tmp_path))
    request = _make_request()

    with (
        patch(
            "body.analyzers.scout_analyzer.ScoutAnalyzer",
            return_value=MagicMock(execute=AsyncMock(return_value=_mock_analysis())),
        ),
        patch(
            "cli.logic.scout._load_fallback_candidates",
            return_value=_SAMPLE_CANDIDATES,
        ),
        patch(
            "cli.logic.scout._load_enforcement_catalog",
            return_value=[],
        ),
        patch(
            "cli.logic.scout._match_enforcement",
            side_effect=lambda c, _cat: c,
        ),
    ):
        result = await scout_project(body=body, request=request)

    assert result["candidate_count"] == 1
    assert result["candidates"][0]["rule_id"] == "scout.no_bare_except"
    assert "signals" in result


# ---------------------------------------------------------------------------
# Analyzer failure → 500
# ---------------------------------------------------------------------------


async def test_scout_analyzer_failure_raises_500(tmp_path: Path) -> None:
    (tmp_path / ".intent").mkdir()

    body = ScoutRequest(path=str(tmp_path))
    request = _make_request()

    bad_analysis = MagicMock()
    bad_analysis.ok = False
    bad_analysis.data = {"error": "parse failed"}

    with patch(
        "body.analyzers.scout_analyzer.ScoutAnalyzer",
        return_value=MagicMock(execute=AsyncMock(return_value=bad_analysis)),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await scout_project(body=body, request=request)
    assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# reset=True allows re-run when inducted file exists
# ---------------------------------------------------------------------------


async def test_scout_reset_skips_409(tmp_path: Path) -> None:
    intent = tmp_path / ".intent" / "rules"
    intent.mkdir(parents=True)
    (intent / "scout_inducted.json").write_text("{}")

    body = ScoutRequest(path=str(tmp_path), reset=True)
    request = _make_request()

    with (
        patch(
            "body.analyzers.scout_analyzer.ScoutAnalyzer",
            return_value=MagicMock(execute=AsyncMock(return_value=_mock_analysis())),
        ),
        patch(
            "cli.logic.scout._load_fallback_candidates", return_value=_SAMPLE_CANDIDATES
        ),
        patch("cli.logic.scout._load_enforcement_catalog", return_value=[]),
        patch("cli.logic.scout._match_enforcement", side_effect=lambda c, _cat: c),
    ):
        result = await scout_project(body=body, request=request)

    assert result["candidate_count"] == 1
