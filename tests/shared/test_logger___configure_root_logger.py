"""Regression tests for shared.logger._configure_root_logger — #828.

Proves the root logger never writes diagnostics to stdout: the RichHandler
(human mode) and the plain StreamHandler (LOG_FORMAT_TYPE=json) both target
stderr. Before this fix both defaulted to stdout, which is what let log
records interleave with CLI commands' structured stdout payloads (e.g.
`core-admin code audit --format json`), breaking naive `json.loads` on the
combined stream.
"""

from __future__ import annotations

import logging
import sys

import pytest
from rich.logging import RichHandler

import shared.logger as logger_module
from shared.logger import _configure_root_logger


@pytest.fixture(autouse=True)
def _restore_root_logger():
    """_configure_root_logger mutates the real root logger via basicConfig(force=True).

    Restore the pre-test handlers/level afterwards so this file doesn't leak
    handler state into the rest of the suite.
    """
    original_handlers = list(logging.root.handlers)
    original_level = logging.root.level
    yield
    logging.root.handlers = original_handlers
    logging.root.setLevel(original_level)


def test_human_mode_rich_handler_targets_stderr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(logger_module, "_LOG_FORMAT_TYPE", "human")
    _configure_root_logger()
    rich_handlers = [h for h in logging.root.handlers if isinstance(h, RichHandler)]
    assert rich_handlers, "expected a RichHandler in human mode"
    assert rich_handlers[0].console.stderr is True
    assert rich_handlers[0].console.file is sys.stderr


def test_json_mode_stream_handler_targets_stderr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(logger_module, "_LOG_FORMAT_TYPE", "json")
    _configure_root_logger()
    stream_handlers = [
        h
        for h in logging.root.handlers
        if isinstance(h, logging.StreamHandler) and not isinstance(h, RichHandler)
    ]
    assert stream_handlers, "expected a plain StreamHandler in json mode"
    assert stream_handlers[0].stream is sys.stderr


def test_configure_root_logger_never_attaches_a_stdout_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Neither format mode should leave a handler writing to stdout.

    This is the exact defect #828 traced back to this function: stdout is
    the CLI's structured-payload channel, never the logger's.
    """
    for fmt in ("human", "json"):
        monkeypatch.setattr(logger_module, "_LOG_FORMAT_TYPE", fmt)
        _configure_root_logger()
        for handler in logging.root.handlers:
            if isinstance(handler, RichHandler):
                stream = handler.console.file
            else:
                stream = getattr(handler, "stream", None)
            assert stream is not sys.stdout, (
                f"{fmt} mode attached a stdout-writing handler: {handler!r}"
            )
