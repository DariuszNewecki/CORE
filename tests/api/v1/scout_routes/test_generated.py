from __future__ import annotations

from api.v1.scout_routes import ScoutRequest


# ID: b3c8961e-cc97-43e0-a928-0f94dfb9e315
def test_ScoutRequest():
    # Test happy path: create a ScoutRequest with a path and default reset
    request = ScoutRequest(path="/tmp/example")

    # Verify the path and reset values
    assert request.path == "/tmp/example"
    assert request.reset is False

    # Test with reset explicitly set to True
    request_with_reset = ScoutRequest(path="/var/log", reset=True)
    assert request_with_reset.path == "/var/log"
    assert request_with_reset.reset is True


from unittest.mock import AsyncMock, MagicMock, patch

from api.v1.scout_routes import scout_project


# ID: 0f4e889b-f4d7-41be-981a-55e5a3bed6ae
async def test_scout_project(tmp_path):
    # Set up a fake target repo with .intent/ present and no existing inducted file
    target = tmp_path / "repo"
    (target / ".intent").mkdir(parents=True)

    body = MagicMock()
    body.path = str(target)
    body.reset = False

    # Fake analyzer
    analysis = MagicMock()
    analysis.ok = True
    analysis.data = {"signals_text": "some signals", "signals_raw": {"x": 1}}
    analyzer = MagicMock()
    analyzer.execute = AsyncMock(return_value=analysis)

    # Build request with app.state.core_context
    core_context = MagicMock()
    core_context.git_service.repo_path = tmp_path
    request = MagicMock()
    request.app.state.core_context = core_context
    # Ensure cognitive_service is None so we go straight to fallback
    core_context.cognitive_service = None

    fallback_candidates = [{"rule_id": "R1", "statement": "do X"}]
    catalog = {"items": []}
    matched_candidates = [
        {"rule_id": "R1", "statement": "do X", "enforcement_matched": True}
    ]

    with (
        patch(
            "cli.logic.scout._load_fallback_candidates",
            return_value=fallback_candidates,
        ),
        patch(
            "cli.logic.scout._load_enforcement_catalog",
            return_value=catalog,
        ),
        patch(
            "cli.logic.scout._match_enforcement",
            side_effect=lambda c, cat: matched_candidates[0],
        ),
    ):
        result = await scout_project(body=body, request=request, analyzer=analyzer)

    analyzer.execute.assert_awaited_once_with(repo_path=target.resolve())
    assert result["path"] == str(target.resolve())
    assert result["signals"] == {"x": 1}
    assert result["candidate_count"] == 1
    assert result["matched"] == 1
    assert result["candidates"][0]["enforcement_matched"] is True
