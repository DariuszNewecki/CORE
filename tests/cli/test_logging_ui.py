# tests/cli/test_logging_ui.py
"""``cli.logging_ui.install_rich_log_handler`` — Rich log rendering is the
CLI's decision, taken only when a human is on stderr (2026-09-21 journal
instrument fix; ``architecture.channels.cli_rendering_allowed``).

- TTY + human mode → the shared logger's plain stderr handler is replaced by
  a RichHandler on stderr, root level preserved;
- no TTY (systemd, pipes) → nothing changes: the plain handler and its
  sd-daemon priority prefix stay, which is what keeps ``journalctl -p err``
  truthful;
- JSON mode → nothing changes even on a TTY.
"""

from __future__ import annotations

import logging
import sys

import pytest
from rich.logging import RichHandler

from cli.logging_ui import install_rich_log_handler


@pytest.fixture(autouse=True)
def _restore_root_logger():
    original_handlers = list(logging.root.handlers)
    original_level = logging.root.level
    yield
    logging.root.handlers = original_handlers
    logging.root.setLevel(original_level)


def _plain_stderr_handler() -> logging.StreamHandler:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(message)s"))
    return handler


# ID: d82354dd-b824-46a5-9c4c-1b75105e183c
def test_tty_human_mode_installs_rich_on_stderr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys.stderr, "isatty", lambda: True, raising=False)
    monkeypatch.delenv("LOG_FORMAT_TYPE", raising=False)
    logging.root.handlers = [_plain_stderr_handler()]
    logging.root.setLevel(logging.WARNING)

    assert install_rich_log_handler() is True

    rich = [h for h in logging.root.handlers if isinstance(h, RichHandler)]
    assert len(rich) == 1
    assert rich[0].console.stderr is True and rich[0].console.file is sys.stderr
    assert rich[0].level == logging.WARNING
    plain = [
        h
        for h in logging.root.handlers
        if isinstance(h, logging.StreamHandler) and not isinstance(h, RichHandler)
    ]
    assert not plain, "the plain stderr handler must be replaced, not doubled"


# ID: 4b89306e-a7ec-4253-afbb-c1b06c161451
def test_no_tty_leaves_the_plain_handler_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys.stderr, "isatty", lambda: False, raising=False)
    monkeypatch.delenv("LOG_FORMAT_TYPE", raising=False)
    plain = _plain_stderr_handler()
    logging.root.handlers = [plain]

    assert install_rich_log_handler() is False
    assert logging.root.handlers == [plain]


# ID: 44fb3f60-b3b2-4264-b4d6-70e6b3462608
def test_json_mode_never_installs_rich_even_on_a_tty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys.stderr, "isatty", lambda: True, raising=False)
    monkeypatch.setenv("LOG_FORMAT_TYPE", "json")
    plain = _plain_stderr_handler()
    logging.root.handlers = [plain]

    assert install_rich_log_handler() is False
    assert logging.root.handlers == [plain]
