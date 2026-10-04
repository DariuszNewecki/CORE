# tests/shared/infrastructure/test_principal_binding.py
"""Principal binding loader: fail closed on every defect (ADR-132 D10.2)."""

from __future__ import annotations

import os
import pwd
from pathlib import Path

import pytest

from shared.infrastructure.principal_binding import GOVERNOR, load_principal_binding


ME = os.getuid()
MY_ACCOUNT = pwd.getpwuid(ME).pw_name


def _write(tmp_path: Path, text: str, mode: int = 0o644) -> Path:
    tmp_path.chmod(0o755)
    path = tmp_path / "principals.yaml"
    path.write_text(text, encoding="utf-8")
    path.chmod(mode)
    return path


def test_binds_account_to_governor(tmp_path: Path) -> None:
    path = _write(tmp_path, f"principals:\n  {MY_ACCOUNT}: {GOVERNOR}\n")
    binding = load_principal_binding(path, trusted_owner_uid=ME)
    assert binding.error is None
    assert binding.role_for(ME) == GOVERNOR
    assert binding.accounts_by_uid[ME] == MY_ACCOUNT


def test_missing_file_binds_nobody(tmp_path: Path) -> None:
    binding = load_principal_binding(tmp_path / "absent.yaml", trusted_owner_uid=ME)
    assert binding.role_for(ME) is None
    assert binding.error and "does not exist" in binding.error


def test_untrusted_owner_binds_nobody(tmp_path: Path) -> None:
    path = _write(tmp_path, f"principals:\n  {MY_ACCOUNT}: {GOVERNOR}\n")
    binding = load_principal_binding(path)  # deployment default: root only
    assert binding.role_for(ME) is None
    assert binding.error and "owned by uid" in binding.error


@pytest.mark.parametrize("mode", [0o664, 0o646])
def test_group_or_world_writable_file_binds_nobody(tmp_path: Path, mode: int) -> None:
    path = _write(tmp_path, f"principals:\n  {MY_ACCOUNT}: {GOVERNOR}\n", mode)
    binding = load_principal_binding(path, trusted_owner_uid=ME)
    assert binding.role_for(ME) is None
    assert binding.error and "writable" in binding.error


def test_writable_directory_binds_nobody(tmp_path: Path) -> None:
    path = _write(tmp_path, f"principals:\n  {MY_ACCOUNT}: {GOVERNOR}\n")
    tmp_path.chmod(0o775)
    binding = load_principal_binding(path, trusted_owner_uid=ME)
    assert binding.role_for(ME) is None
    assert binding.error and "writable" in binding.error


@pytest.mark.parametrize(
    "text",
    [
        "not: [valid\n",
        "- a list\n",
        "principals: []\n",
        f"principals:\n  {MY_ACCOUNT}: governor\n",
        f"principals:\n  {MY_ACCOUNT}: 7\n",
        "principals:\n  no-such-account-xyz: principal.governor\n",
    ],
)
def test_malformed_binding_binds_nobody(tmp_path: Path, text: str) -> None:
    binding = load_principal_binding(_write(tmp_path, text), trusted_owner_uid=ME)
    assert binding.role_for(ME) is None
    assert binding.error


def test_two_governors_bind_nobody(tmp_path: Path) -> None:
    text = f"principals:\n  {MY_ACCOUNT}: {GOVERNOR}\n  root: {GOVERNOR}\n"
    binding = load_principal_binding(_write(tmp_path, text), trusted_owner_uid=ME)
    assert binding.role_for(ME) is None
    assert binding.error and "more than one" in binding.error


def test_non_governor_role_is_bound_as_written(tmp_path: Path) -> None:
    text = f"principals:\n  {MY_ACCOUNT}: principal.operator\n"
    binding = load_principal_binding(_write(tmp_path, text), trusted_owner_uid=ME)
    assert binding.role_for(ME) == "principal.operator"
