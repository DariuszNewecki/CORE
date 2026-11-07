from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from api.cli.integration_client import IntegrationClient


# ID: 110aba85-16e0-4382-9866-453c8383a673
async def test_IntegrationClient_lint() -> None:
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"passed": True})

    client = IntegrationClient(facade)

    result = await client.lint()

    facade._request.assert_awaited_once_with("POST", "/v1/lint", timeout=300.0)
    assert result == {"passed": True}


import asyncio


# ID: 61036eec-51e9-4b83-99b3-ccdc4f1c400c
def test_IntegrationClient_integrate() -> None:
    from api.cli.integration_client import IntegrationClient

    facade = MagicMock()
    facade._request = AsyncMock(return_value={"status": "ok", "committed": True})
    client = IntegrationClient(facade)

    expected = {"status": "ok", "committed": True}
    result = asyncio.run(client.integrate("feat: add thing"))

    assert result == expected
    facade._request.assert_awaited_once_with(
        "POST",
        "/v1/integrate",
        json={"commit_message": "feat: add thing"},
        timeout=300.0,
    )





# ID: d4050d5d-e7ee-4363-bd96-3a99911029e5
def test_IntegrationClient():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"status": "ok"})

    client = IntegrationClient(facade)
    assert client._facade is facade

    result = asyncio.run(client.integrate("my commit message"))
    assert result == {"status": "ok"}
    facade._request.assert_awaited_once_with(
        "POST",
        "/v1/integrate",
        json={"commit_message": "my commit message"},
        timeout=300.0,
    )

    facade._request.reset_mock()
    lint_result = asyncio.run(client.lint())
    assert lint_result == {"status": "ok"}
    facade._request.assert_awaited_once_with(
        "POST",
        "/v1/lint",
        timeout=300.0,
    )
