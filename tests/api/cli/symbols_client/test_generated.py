from __future__ import annotations

from unittest.mock import MagicMock

from api.cli.symbols_client import SymbolsClient


# ID: e86d4464-2439-4d0d-b033-0269f241246f
def test_SymbolsClient():
    facade = MagicMock()
    client = SymbolsClient(facade)
    assert client._facade is facade
