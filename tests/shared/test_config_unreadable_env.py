"""An unreadable .env is skipped, not a crash at import (#942).

Locking the dev tree's .env away from the assistant's account must not
break every core-admin it starts (python-dotenv raises PermissionError).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from shared.config import _load_dotenv_if_readable


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads any file")
def test_an_unreadable_env_file_is_skipped(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("CONFIG_UNREADABLE_PROBE=1\n")
    env.chmod(0)
    try:
        assert _load_dotenv_if_readable(env) is False
        assert "CONFIG_UNREADABLE_PROBE" not in os.environ
    finally:
        env.chmod(0o600)


def test_a_readable_env_file_is_loaded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CONFIG_PROBE_KEY", raising=False)
    env = tmp_path / ".env"
    env.write_text("CONFIG_PROBE_KEY=1\n")
    assert _load_dotenv_if_readable(env) is True
    assert os.environ.pop("CONFIG_PROBE_KEY") == "1"
