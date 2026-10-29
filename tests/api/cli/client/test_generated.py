from __future__ import annotations

from unittest.mock import patch

from api.cli.client import CoreApiClient


# ID: 6fa8d435-82c0-4248-8f66-18169a9f0700
def test_CoreApiClient():
    with patch(
        "api.cli.client.parse_base_url", return_value=("http://127.0.0.1:8000", None)
    ) as mock_parse:
        client = CoreApiClient(base_url="http://127.0.0.1:8000")

    mock_parse.assert_called_once_with("http://127.0.0.1:8000")
    assert client.base_url == "http://127.0.0.1:8000"
    assert client._http_base == "http://127.0.0.1:8000"
    assert client.socket_path is None
    assert client.timeout == 30.0

    # Namespace sub-clients are attached and bound to this client
    assert client.audits is not None
    assert client.fix is not None
    assert client.quality is not None
    assert client.coverage is not None
    assert client.refactor is not None
    assert client.inspect is not None
    assert client.proposals is not None
    assert client.integration is not None
    assert client.census is not None
    assert client.cognitive_roles is not None
    assert client.sync is not None
    assert client.daemon is not None
    assert client.findings is not None
    assert client.integrity is not None
    assert client.lane is not None
    assert client.llm_resources is not None
    assert client.secrets is not None
    assert client.symbols is not None
    assert client.vectors is not None
    assert client.project is not None
