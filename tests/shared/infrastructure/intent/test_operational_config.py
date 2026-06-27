# tests/shared/infrastructure/intent/test_operational_config.py
"""
Loader tests for shared.infrastructure.intent.operational_config.

Covers:
- Default fallback when YAML is empty or absent
- Field override propagates correctly
- Type-mismatch falls back to default and logs a warning
- Nested workers section loads independently per sub-key
- bool-before-int dispatch (DaemonConfig.set_debug)
- tuple[str, ...] dispatch (BlackboardConfig.telemetry_subject_prefixes)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from shared.infrastructure.intent.operational_config import (
    BlackboardConfig,
    DaemonConfig,
    EmbeddingConfig,
    LLMConfig,
    OperationalConfig,
    WorkerCallSiteRewriterConfig,
    WorkersConfig,
    WorkerViolationRemediatorConfig,
    _load_from_sec,
    load_operational_config,
)


# ---------------------------------------------------------------------------
# _load_from_sec — unit tests for the generic loader
# ---------------------------------------------------------------------------


def test_empty_dict_returns_all_defaults() -> None:
    cfg = _load_from_sec({}, LLMConfig)
    assert cfg == LLMConfig()
    assert cfg.default_max_tokens == 4096
    assert cfg.http_timeout_sec == 60


def test_override_single_int_field() -> None:
    cfg = _load_from_sec({"default_max_tokens": 8192}, LLMConfig)
    assert cfg.default_max_tokens == 8192
    assert cfg.http_timeout_sec == 60  # unchanged


def test_override_float_field() -> None:
    cfg = _load_from_sec({"provider_request_timeout_sec": 200.5}, EmbeddingConfig)
    assert cfg.provider_request_timeout_sec == 200.5
    assert cfg.chunk_size == 512  # unchanged


def test_override_bool_field() -> None:
    cfg = _load_from_sec({"set_debug": True}, DaemonConfig)
    assert cfg.set_debug is True
    assert cfg.one_shot_interval_sec == 300  # unchanged


def test_bool_not_confused_with_int() -> None:
    # True is 1 in Python; the loader must dispatch to _get_bool, not _get_int
    cfg = _load_from_sec({"set_debug": True, "one_shot_interval_sec": 60}, DaemonConfig)
    assert cfg.set_debug is True
    assert isinstance(cfg.set_debug, bool)
    assert cfg.one_shot_interval_sec == 60


def test_override_tuple_field() -> None:
    cfg = _load_from_sec(
        {"telemetry_subject_prefixes": ["a.b::", "c.d::"]}, BlackboardConfig
    )
    assert cfg.telemetry_subject_prefixes == ("a.b::", "c.d::")


def test_tuple_default_preserved_when_absent() -> None:
    cfg = _load_from_sec({}, BlackboardConfig)
    assert cfg.telemetry_subject_prefixes == ("loop_hold.sample::",)


def test_invalid_int_falls_back_to_default(caplog: pytest.LogCaptureFixture) -> None:
    import logging

    with caplog.at_level(logging.WARNING):
        cfg = _load_from_sec({"default_max_tokens": "not-an-int"}, LLMConfig)
    assert cfg.default_max_tokens == 4096
    assert "default_max_tokens" in caplog.text


def test_invalid_bool_falls_back_to_default(caplog: pytest.LogCaptureFixture) -> None:
    import logging

    with caplog.at_level(logging.WARNING):
        cfg = _load_from_sec({"set_debug": "yes"}, DaemonConfig)
    assert cfg.set_debug is False
    assert "set_debug" in caplog.text


def test_invalid_tuple_falls_back_to_default(caplog: pytest.LogCaptureFixture) -> None:
    import logging

    with caplog.at_level(logging.WARNING):
        cfg = _load_from_sec({"telemetry_subject_prefixes": 42}, BlackboardConfig)
    assert cfg.telemetry_subject_prefixes == ("loop_hold.sample::",)
    assert "telemetry_subject_prefixes" in caplog.text


# ---------------------------------------------------------------------------
# Workers — nested dataclass dispatch
# ---------------------------------------------------------------------------


def test_workers_empty_dict_returns_all_defaults() -> None:
    cfg = _load_from_sec({}, WorkersConfig)
    assert cfg.call_site_rewriter == WorkerCallSiteRewriterConfig()
    assert cfg.violation_remediator == WorkerViolationRemediatorConfig()


def test_workers_nested_override() -> None:
    raw = {"call_site_rewriter": {"claim_limit": 99}}
    cfg = _load_from_sec(raw, WorkersConfig)
    assert cfg.call_site_rewriter.claim_limit == 99
    assert cfg.doc_writer.batch_size == 25  # unchanged


def test_workers_nested_multi_field_override() -> None:
    raw = {
        "violation_remediator": {
            "claim_limit": 10,
            "scan_limit": 50,
            "min_role_confidence": 0.80,
        }
    }
    cfg = _load_from_sec(raw, WorkersConfig)
    vr = cfg.violation_remediator
    assert vr.claim_limit == 10
    assert vr.scan_limit == 50
    assert vr.min_role_confidence == 0.80
    assert vr.ceremony_timeout_sec == 30  # unchanged


def test_workers_non_mapping_subsection_falls_back(
    caplog: pytest.LogCaptureFixture,
) -> None:
    import logging

    with caplog.at_level(logging.WARNING):
        cfg = _load_from_sec({"call_site_rewriter": "bad"}, WorkersConfig)
    assert cfg.call_site_rewriter == WorkerCallSiteRewriterConfig()
    assert "call_site_rewriter" in caplog.text


# ---------------------------------------------------------------------------
# load_operational_config — integration with mocked IntentRepository
# ---------------------------------------------------------------------------


def _mock_repo(raw: dict) -> MagicMock:
    repo = MagicMock()
    repo.resolve_rel.return_value = "enforcement/config/operational_config.yaml"
    repo.load_document.return_value = raw
    return repo


def test_load_returns_operational_config_instance() -> None:
    with patch(
        "shared.infrastructure.intent.operational_config.get_intent_repository",
        return_value=_mock_repo({}),
    ):
        cfg = load_operational_config()
    assert isinstance(cfg, OperationalConfig)


def test_load_applies_yaml_overrides() -> None:
    raw = {"llm": {"default_max_tokens": 2048}, "daemon": {"set_debug": True}}
    with patch(
        "shared.infrastructure.intent.operational_config.get_intent_repository",
        return_value=_mock_repo(raw),
    ):
        cfg = load_operational_config()
    assert cfg.llm.default_max_tokens == 2048
    assert cfg.daemon.set_debug is True
    assert cfg.llm.http_timeout_sec == 60  # default preserved


def test_load_falls_back_on_missing_file(caplog: pytest.LogCaptureFixture) -> None:
    import logging

    with caplog.at_level(logging.WARNING):
        with patch(
            "shared.infrastructure.intent.operational_config.get_intent_repository",
            side_effect=FileNotFoundError("no intent repo"),
        ):
            cfg = load_operational_config()
    assert isinstance(cfg, OperationalConfig)
    assert cfg == OperationalConfig()
    assert "fallback defaults" in caplog.text


def test_load_falls_back_on_non_dict_document(caplog: pytest.LogCaptureFixture) -> None:
    import logging

    repo = _mock_repo(None)
    repo.load_document.return_value = ["not", "a", "dict"]
    with caplog.at_level(logging.WARNING):
        with patch(
            "shared.infrastructure.intent.operational_config.get_intent_repository",
            return_value=repo,
        ):
            cfg = load_operational_config()
    assert isinstance(cfg, OperationalConfig)
    assert cfg == OperationalConfig()
    assert "did not parse as a dict" in caplog.text
