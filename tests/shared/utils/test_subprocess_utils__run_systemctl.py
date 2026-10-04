"""Tests for ``run_systemctl`` service-account delegation.

After the governor/agent/services account split (2026-10-04), CORE's units
are systemd *user* units of the services account; ``systemctl --user`` from
any other account sees none of them. ``CORE_SERVICE_USER`` names that
account, and ``run_systemctl`` then goes through the root-owned
``core-services`` wrapper via ``sudo -n -u <user>``. These tests pin the
argv in each case and that unset / self-naming values keep plain
``systemctl --user``.
"""

from __future__ import annotations

import os
import pwd
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from shared.utils.subprocess_utils import (
    SERVICE_USER_ENV_VAR,
    SERVICES_WRAPPER,
    run_systemctl,
    systemctl_service_user,
)


_SELF = pwd.getpwuid(os.geteuid()).pw_name


def _completed(
    returncode: int = 0, stdout: str = "", stderr: str = ""
) -> SimpleNamespace:
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


@pytest.mark.parametrize("value", [None, "", "   ", _SELF])
def test_no_delegation_without_a_foreign_service_user(monkeypatch, value) -> None:
    if value is None:
        monkeypatch.delenv(SERVICE_USER_ENV_VAR, raising=False)
    else:
        monkeypatch.setenv(SERVICE_USER_ENV_VAR, value)
    assert systemctl_service_user() is None
    with patch("subprocess.run", return_value=_completed()) as mock_run:
        run_systemctl("is-active", "core-api")
    assert mock_run.call_args.args[0] == [
        "systemctl",
        "--user",
        "is-active",
        "core-api",
    ]


def test_foreign_service_user_routes_through_wrapper(monkeypatch) -> None:
    other = "core" if _SELF != "core" else "core-svc-test"
    monkeypatch.setenv(SERVICE_USER_ENV_VAR, other)
    assert systemctl_service_user() == other
    with patch(
        "subprocess.run", return_value=_completed(stdout="active\n")
    ) as mock_run:
        result = run_systemctl("is-active", "core-api")
    assert mock_run.call_args.args[0] == [
        "sudo",
        "-n",
        "-u",
        other,
        SERVICES_WRAPPER,
        "is-active",
        "core-api",
    ]
    assert result.stdout == "active"
    assert result.returncode == 0


def test_wrapper_refusal_surfaces_as_nonzero_result(monkeypatch) -> None:
    other = "core" if _SELF != "core" else "core-svc-test"
    monkeypatch.setenv(SERVICE_USER_ENV_VAR, other)
    refused = _completed(2, stderr="core-services: action not allowed: daemon-reload\n")
    with patch("subprocess.run", return_value=refused):
        result = run_systemctl("daemon-reload")
    assert result.returncode == 2
    assert "not allowed" in result.stderr
