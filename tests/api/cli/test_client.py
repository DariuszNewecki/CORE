# tests/api/cli/test_client.py
"""Tests for api.cli.client.CoreApiClient — base_url resolution order."""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# base_url resolution
# ---------------------------------------------------------------------------


def test_defaults_to_loopback_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    from api.cli.client import _DEFAULT_BASE_URL, CoreApiClient

    monkeypatch.delenv("CORE_API_URL", raising=False)

    client = CoreApiClient()

    assert client.base_url == _DEFAULT_BASE_URL


def test_env_var_overrides_default(monkeypatch: pytest.MonkeyPatch) -> None:
    from api.cli.client import CoreApiClient

    monkeypatch.setenv("CORE_API_URL", "http://core-host:8000")

    client = CoreApiClient()

    assert client.base_url == "http://core-host:8000"


def test_explicit_argument_overrides_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    from api.cli.client import CoreApiClient

    monkeypatch.setenv("CORE_API_URL", "http://core-host:8000")

    client = CoreApiClient(base_url="http://explicit-host:9000")

    assert client.base_url == "http://explicit-host:9000"
