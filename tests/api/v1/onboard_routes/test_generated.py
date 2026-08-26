from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from api.v1.onboard_routes import promote_onboard


# ID: ea2bba0f-d890-4e69-bf91-682f8a22d891
class TestPromoteOnboard:
    # ID: 4d3c895c-d429-4d0f-b33d-aa5356b5ece6
    async def test_happy_path(self):
        """Happy path: promote_staged succeeds, returns promoted dict."""
        # Arrange
        mock_request = MagicMock()
        mock_core_context = MagicMock()
        mock_request.app.state.core_context = mock_core_context
        mock_body = MagicMock()
        mock_body.path = "/tmp/staged-onboard"

        with patch("cli.logic.byor.promote_staged", new=AsyncMock()) as mock_promote:
            mock_promote.return_value = None

            # Act
            result = await promote_onboard(body=mock_body, request=mock_request)

            # Assert
            assert result == {
                "path": str(Path(mock_body.path).resolve()),
                "promoted": True,
            }
            mock_promote.assert_awaited_once_with(
                context=mock_core_context, path=Path(mock_body.path).resolve()
            )

    # ID: d6bb95e2-f4e5-4d02-9061-8eb94301b4ea
    async def test_system_exit_raises_http_400(self):
        """SystemExit propagates as HTTP 400."""
        mock_request = MagicMock()
        mock_request.app.state.core_context = MagicMock()
        mock_body = MagicMock()
        mock_body.path = "/tmp/missing"

        with patch(
            "cli.logic.byor.promote_staged", new=AsyncMock(side_effect=SystemExit())
        ) as mock_promote:
            with pytest.raises(HTTPException) as exc_info:
                await promote_onboard(body=mock_body, request=mock_request)
            assert exc_info.value.status_code == 400
            mock_promote.assert_awaited_once()

    # ID: 5014b4ba-c8ff-4a18-a4f4-a0c45d72e388
    async def test_generic_exception_raises_http_500(self):
        """Generic exception becomes HTTP 500 with message."""
        mock_request = MagicMock()
        mock_request.app.state.core_context = MagicMock()
        mock_body = MagicMock()
        mock_body.path = "/tmp/failing"

        with patch(
            "cli.logic.byor.promote_staged",
            new=AsyncMock(side_effect=ValueError("boom")),
        ) as mock_promote:
            with pytest.raises(HTTPException) as exc_info:
                await promote_onboard(body=mock_body, request=mock_request)
            assert exc_info.value.status_code == 500
            assert "boom" in str(exc_info.value.detail)
            mock_promote.assert_awaited_once()



from api.v1.onboard_routes import onboard_project


# ID: 73bd2a1d-77a4-4033-a38e-9e2c88482ec2
async def test_onboard_project():
    body = MagicMock()
    body.path = "/tmp/external-repo"
    body.write = True
    body.stage = False

    request = MagicMock()
    core_context = MagicMock()
    core_context.git_service.repo_path.resolve.return_value = Path("/tmp/core")
    request.app.state.core_context = core_context

    target_path = Path("/tmp/external-repo")

    # Patch the module-level Path (note: Path imported at top of onboard_routes.
    # The previous attempt patched with return_value=target_path but the symbol
    # calls Path(body.path).resolve() - we need the resolved Path returned)
    with patch("api.v1.onboard_routes.Path") as mock_path:
        mock_path.return_value = target_path
        # initialize_repository is imported locally inside onboard_project, so
        # patch it at its defining module (cli.logic.byor)
        with patch(
            "cli.logic.byor.initialize_repository", new_callable=AsyncMock
        ) as mock_init:
            result = await onboard_project(body, request)

    mock_init.assert_awaited_once_with(
        context=core_context,
        path=target_path,
        dry_run=False,
        stage_dir=None,
    )
    assert result == {
        "path": "/tmp/external-repo",
        "mode": "write",
        "stage_dir": None,
    }
