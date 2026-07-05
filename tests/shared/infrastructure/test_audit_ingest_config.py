# tests/shared/infrastructure/test_audit_ingest_config.py
"""Tests for AuditIngestConfig loader (ADR-098 D5 constraint substrate).

Covers:
- Successful load returns correct cap and enabled_rules.
- Missing file falls back to defaults without raising.
- Non-dict YAML falls back to defaults.
- Bad cap value falls back to default cap.
- enabled_rules not a list falls back to empty list.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from shared.infrastructure.intent.audit_ingest_config import (
    AuditIngestConfig,
    load_audit_ingest_config,
)


def _patch_repo(raw: object | None = None, raises: Exception | None = None):
    repo = MagicMock()
    repo.resolve_rel.return_value = MagicMock()
    if raises:
        repo.load_document.side_effect = raises
    else:
        repo.load_document.return_value = raw
    return patch(
        "shared.infrastructure.intent.audit_ingest_config.get_intent_repository",
        return_value=repo,
    )


# ID: 51daff2e-de47-42d7-a3b8-0c15400d49bc
def test_load_returns_correct_values() -> None:
    """Happy path: values from YAML are returned in the frozen dataclass."""
    raw = {
        "version": "1.0.0",
        "quality_ingest_cap": 10,
        "enabled_rules": ["quality.security_audit"],
    }
    with _patch_repo(raw=raw):
        cfg = load_audit_ingest_config()

    assert cfg.quality_ingest_cap == 10
    assert cfg.enabled_rules == ["quality.security_audit"]
    assert isinstance(cfg, AuditIngestConfig)


# ID: 092e4f67-7675-44c2-bf19-b4e661b7a150
def test_load_falls_back_on_missing_file() -> None:
    """Missing file triggers a warning and returns safe defaults."""
    with _patch_repo(raises=FileNotFoundError("not found")):
        cfg = load_audit_ingest_config()

    assert cfg.quality_ingest_cap == 25
    assert cfg.enabled_rules == []


def test_load_falls_back_on_non_dict_yaml() -> None:
    """YAML that parses to a non-dict returns defaults."""
    with _patch_repo(raw="this is just a string"):
        cfg = load_audit_ingest_config()

    assert cfg.quality_ingest_cap == 25
    assert cfg.enabled_rules == []


def test_load_falls_back_on_bad_cap_type() -> None:
    """Non-integer quality_ingest_cap falls back to 25."""
    raw = {"quality_ingest_cap": "not-an-int", "enabled_rules": []}
    with _patch_repo(raw=raw):
        cfg = load_audit_ingest_config()

    assert cfg.quality_ingest_cap == 25


def test_load_falls_back_on_non_list_rules() -> None:
    """enabled_rules that is not a list falls back to empty list."""
    raw = {"quality_ingest_cap": 25, "enabled_rules": "quality.security_audit"}
    with _patch_repo(raw=raw):
        cfg = load_audit_ingest_config()

    assert cfg.enabled_rules == []


def test_config_is_frozen() -> None:
    """AuditIngestConfig must be immutable (frozen dataclass)."""
    cfg = AuditIngestConfig(quality_ingest_cap=25, enabled_rules=[])
    with pytest.raises((AttributeError, TypeError)):
        cfg.quality_ingest_cap = 50  # type: ignore[misc]
