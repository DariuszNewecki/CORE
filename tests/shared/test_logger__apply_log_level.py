"""shared.logger.apply_log_level -- the plain primitive behind the governed
`logging.reconfigure` action (#889).

The API lifespan used to call the @atomic_action coroutine without awaiting
it (a silent no-op); awaiting it would have raised GovernanceBypassError at
every boot. apply_log_level is what bootstrap calls instead.
"""

from __future__ import annotations

import logging

import pytest

from shared.logger import _configure_root_logger, apply_log_level


@pytest.fixture(autouse=True)
def _restore_root_logger():
    root = logging.getLogger()
    saved_level, saved_handlers = root.level, list(root.handlers)
    try:
        yield
    finally:
        _configure_root_logger()
        root.setLevel(saved_level)
        root.handlers[:] = saved_handlers


def test_apply_log_level_sets_root_level() -> None:
    apply_log_level("warning")
    assert logging.getLogger().level == logging.WARNING
    apply_log_level("DEBUG")
    assert logging.getLogger().level == logging.DEBUG


def test_apply_log_level_rejects_unknown_level() -> None:
    before = logging.getLogger().level
    with pytest.raises(ValueError, match="Invalid log level"):
        apply_log_level("LOUD")
    assert logging.getLogger().level == before


def test_lifespan_no_longer_references_the_governed_coroutine() -> None:
    """Regression pin for #889: the composition root must call the primitive,
    never the @atomic_action (un-awaited = no-op; awaited = bypass error)."""
    from pathlib import Path

    src = Path("src/body/infrastructure/lifespan.py").read_text(encoding="utf-8")
    assert "apply_log_level(" in src
    assert "reconfigure_log_level(" not in src.replace(
        "`reconfigure_log_level(...)`", ""
    )
