"""Regression tests for shared.logger._configure_root_logger — #828, and the
2026-09-21 journal-instrument fix.

#828: the root logger never writes diagnostics to stdout — both format modes
target stderr, so log records cannot interleave with CLI commands'
structured stdout payloads.

2026-09-21: the shared logger renders nothing. It used to install a Rich
handler for every process that imported it (``logic_no_terminal_rendering``
finding on ``logger.py``, D10's first production delegation), which under
systemd meant 80-column Rich wrapping in journald and, worse, every journal
line at PRIORITY=6 — ``journalctl -p err`` returned nothing whatever
happened (17,585 of 17,585 daemon entries at 6 on the night measured). Now:
a plain one-line-per-record handler in both modes; when stderr is not a
terminal every line carries its sd-daemon priority prefix so journald
stores the real level; Rich is the CLI's decision (``cli.logging_ui``),
taken only when a human is on stderr.
"""

from __future__ import annotations

import ast
import logging
import sys
from pathlib import Path

import pytest

import shared.logger as logger_module
from shared.logger import (
    HumanFormatter,
    JsonFormatter,
    SdDaemonPrefixFormatter,
    _configure_root_logger,
)


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


def _stderr_handlers() -> list[logging.StreamHandler]:
    return [
        h
        for h in logging.root.handlers
        if isinstance(h, logging.StreamHandler)
        and getattr(h, "stream", None) is sys.stderr
    ]


# ID: 6992bac3-953d-4945-8f83-c5f86807ed1c
@pytest.mark.parametrize("fmt", ["human", "json"])
def test_both_modes_install_one_plain_stderr_handler(
    monkeypatch: pytest.MonkeyPatch, fmt: str
) -> None:
    monkeypatch.setattr(logger_module, "_LOG_FORMAT_TYPE", fmt)
    monkeypatch.setattr(logger_module, "_stderr_is_tty", lambda: True)
    _configure_root_logger()
    handlers = _stderr_handlers()
    assert len(handlers) == 1, "expected exactly one plain stderr StreamHandler"
    expected = JsonFormatter if fmt == "json" else HumanFormatter
    assert type(handlers[0].formatter) is expected


# ID: b1df1d72-e221-4a7e-bffd-a70a4e17ff22
@pytest.mark.parametrize("fmt", ["human", "json"])
def test_non_tty_wraps_formatter_with_sd_daemon_prefix(
    monkeypatch: pytest.MonkeyPatch, fmt: str
) -> None:
    """Under systemd (no TTY) both modes carry the priority prefix — the JSON
    path goes to journald too."""
    monkeypatch.setattr(logger_module, "_LOG_FORMAT_TYPE", fmt)
    monkeypatch.setattr(logger_module, "_stderr_is_tty", lambda: False)
    _configure_root_logger()
    (handler,) = _stderr_handlers()
    assert isinstance(handler.formatter, SdDaemonPrefixFormatter)
    record = logging.LogRecord("t", logging.ERROR, "f.py", 1, "boom", None, None)
    assert handler.formatter.format(record).startswith("<3>")


# ID: 2d419b6a-52c8-4696-8002-6ab9826a15d8
def test_tty_human_mode_has_no_priority_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    """A human on stderr must not see ``<6>`` noise (the CLI adds Rich on top)."""
    monkeypatch.setattr(logger_module, "_LOG_FORMAT_TYPE", "human")
    monkeypatch.setattr(logger_module, "_stderr_is_tty", lambda: True)
    _configure_root_logger()
    (handler,) = _stderr_handlers()
    record = logging.LogRecord("t", logging.INFO, "f.py", 1, "hi", None, None)
    assert not handler.formatter.format(record).startswith("<")


# ID: 6ba39db2-3b51-4d26-bffb-17f266c49cd0
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
            stream = getattr(handler, "stream", None)
            assert stream is not sys.stdout, (
                f"{fmt} mode attached a stdout-writing handler: {handler!r}"
            )


# ID: 522436b4-7754-4c03-8883-31887e2ad086
def test_human_formatter_is_one_line_per_record() -> None:
    record = logging.LogRecord(
        "will.x", logging.WARNING, "f.py", 1, "a %s", ("b",), None
    )
    line = HumanFormatter().format(record)
    assert "\n" not in line
    assert line.endswith(" WARNING will.x: a b")
    assert line[:4].isdigit() and line[10] == "T" and "Z " in line  # ISO-8601 UTC stamp


# ID: 8c3d8e59-787c-4604-b4a5-eb9b46cb159e
def test_sd_daemon_prefix_covers_every_line_of_a_traceback() -> None:
    """journald assigns priority per line; a traceback must not drop to 6
    after its first line."""
    try:
        raise ValueError("boom")
    except ValueError:
        record = logging.LogRecord(
            "will.y", logging.ERROR, "f.py", 2, "failed", None, sys.exc_info()
        )
    lines = SdDaemonPrefixFormatter(HumanFormatter()).format(record).split("\n")
    assert len(lines) > 2
    assert all(line.startswith("<3>") for line in lines)
    warn = logging.LogRecord("w", logging.WARNING, "f.py", 3, "w", None, None)
    assert SdDaemonPrefixFormatter(HumanFormatter()).format(warn).startswith("<4>")
    crit = logging.LogRecord("c", logging.CRITICAL, "f.py", 4, "c", None, None)
    assert SdDaemonPrefixFormatter(JsonFormatter()).format(crit).startswith("<2>{")


# ID: 72144ee6-50f4-44ae-bc5a-3d28bce3e141
def test_shared_logger_imports_no_terminal_renderer() -> None:
    """The source-level guard for the rule finding this fix closes:
    ``shared/logger.py`` must not import Rich or construct a Console."""
    tree = ast.parse(Path(logger_module.__file__).read_text(encoding="utf-8"))
    rich_imports = [
        node
        for node in ast.walk(tree)
        if (isinstance(node, ast.ImportFrom) and (node.module or "").startswith("rich"))
        or (
            isinstance(node, ast.Import)
            and any(a.name.startswith("rich") for a in node.names)
        )
    ]
    assert not rich_imports, (
        "shared/logger.py must not import Rich — rendering belongs to cli.logging_ui"
    )
    console_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Console"
    ]
    assert not console_calls
