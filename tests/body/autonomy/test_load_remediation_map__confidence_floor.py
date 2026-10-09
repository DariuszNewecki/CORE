"""#964: the runtime backstop in _load_remediation_map. An ACTIVE entry below
the governed floor, or an entry without an explicit status, never reaches the
remediator (which turns every non-DELEGATE entry into proposals)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from body.autonomy.audit_analyzer import (
    _load_governance_config,
    _load_remediation_map,
)


def _resolver(tmp_path: Path, mappings: str) -> MagicMock:
    (tmp_path / "auto_remediation.yaml").write_text("mappings:\n" + mappings)
    (tmp_path / "governance_paths.yaml").write_text(
        "remediation:\n  min_confidence: 0.80\n"
    )
    resolver = MagicMock()
    resolver.remediation_map_path = tmp_path / "auto_remediation.yaml"
    resolver.governance_config_path = tmp_path / "governance_paths.yaml"
    return resolver


# ID: 2ffd564d-a4cc-4c99-947a-62afe3f2476c
def test_active_below_floor_is_not_dispatched(tmp_path: Path) -> None:
    resolver = _resolver(
        tmp_path,
        "  low.rule:\n    action: fix.x\n    confidence: 0.79\n    status: ACTIVE\n"
        "  ok.rule:\n    action: fix.y\n    confidence: 0.80\n    status: ACTIVE\n",
    )
    loaded = _load_remediation_map(resolver)
    assert "low.rule" not in loaded
    assert loaded["ok.rule"]["status"] == "ACTIVE"


# ID: 2b1c7535-6f1d-4c2b-8ef4-5c5105ec1c0a
def test_missing_status_is_not_treated_as_active(tmp_path: Path) -> None:
    resolver = _resolver(
        tmp_path, "  no.status:\n    action: fix.x\n    confidence: 0.95\n"
    )
    assert "no.status" not in _load_remediation_map(resolver)


# ID: 0dc24994-b372-4895-9972-a9078a41c924
def test_governance_config_that_is_not_text_falls_back() -> None:
    """A resolver whose config does not read as a str (a bare MagicMock) must
    not reach yaml.safe_load: it reads a non-str as a stream until EOF, and a
    mock never signals EOF -- this hung the suite until the host ran out of
    memory (2026-10-09). Run under a memory cap."""
    assert _load_governance_config(MagicMock()) == {}
