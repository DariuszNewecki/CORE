"""Tests for shared.infrastructure.intent.action_risk.load_safe_auto_approval_envelope
(#853) — the loader for the independently governed safe_auto_approval_envelope
section of .intent/enforcement/config/action_risk.yaml.

Fail-closed contract (mirrors audit_verdict.py): any load/parse/validation
failure returns the {"_error": True, ...} sentinel, never a hardcoded
fallback. will.autonomy.safe_auto_approval_envelope.validate_envelope
treats that sentinel as "deny" — see
tests/will/autonomy/test_safe_auto_approval_envelope.py::test_envelope_load_failure_denies
for that consumption-side proof.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

from shared.infrastructure.intent.action_risk import load_safe_auto_approval_envelope


_VALID_ENVELOPE = {
    "safe_auto_approval_envelope": {
        "authorized_actions": ["fix.imports", "fix.ids"],
        "authorized_path_prefixes": ["src/", "tests/"],
        "authorized_extensions": [".py"],
    }
}


def _load_with_document(document) -> dict:
    mock_repo = Mock()
    mock_repo.resolve_rel.return_value = "enforcement/config/action_risk.yaml"
    mock_repo.load_document.return_value = document
    with patch(
        "shared.infrastructure.intent.intent_repository.get_intent_repository",
        return_value=mock_repo,
    ):
        return load_safe_auto_approval_envelope()


def test_valid_envelope_loads_with_correct_types() -> None:
    result = _load_with_document(_VALID_ENVELOPE)
    assert "_error" not in result
    assert result["authorized_actions"] == frozenset({"fix.imports", "fix.ids"})
    assert result["authorized_path_prefixes"] == ("src/", "tests/")
    assert result["authorized_extensions"] == (".py",)


def test_document_not_a_dict_returns_error_sentinel() -> None:
    result = _load_with_document(["not", "a", "dict"])
    assert result.get("_error") is True
    assert "did not parse as a dict" in result["reason"]


def test_missing_envelope_section_returns_error_sentinel() -> None:
    result = _load_with_document({"actions": {"fix.format": "safe"}})
    assert result.get("_error") is True
    assert "safe_auto_approval_envelope" in result["reason"]


def test_envelope_not_a_dict_returns_error_sentinel() -> None:
    result = _load_with_document({"safe_auto_approval_envelope": ["not", "a", "dict"]})
    assert result.get("_error") is True


def test_missing_required_key_returns_error_sentinel() -> None:
    malformed = {
        "safe_auto_approval_envelope": {
            "authorized_actions": ["fix.imports"],
            "authorized_path_prefixes": ["src/"],
            # authorized_extensions missing
        }
    }
    result = _load_with_document(malformed)
    assert result.get("_error") is True
    assert "authorized_extensions" in result["reason"]


def test_empty_list_value_returns_error_sentinel() -> None:
    malformed = dict(_VALID_ENVELOPE)
    malformed["safe_auto_approval_envelope"] = {
        **_VALID_ENVELOPE["safe_auto_approval_envelope"],
        "authorized_actions": [],
    }
    result = _load_with_document(malformed)
    assert result.get("_error") is True


def test_non_string_entry_returns_error_sentinel() -> None:
    malformed = dict(_VALID_ENVELOPE)
    malformed["safe_auto_approval_envelope"] = {
        **_VALID_ENVELOPE["safe_auto_approval_envelope"],
        "authorized_actions": ["fix.imports", 123],
    }
    result = _load_with_document(malformed)
    assert result.get("_error") is True


def test_loader_exception_returns_error_sentinel_not_a_raise() -> None:
    """The loader must never propagate a raw exception to the caller — it
    always converts failures into the sentinel dict, matching the
    fail-closed contract validate_envelope relies on."""
    with patch(
        "shared.infrastructure.intent.intent_repository.get_intent_repository",
        side_effect=RuntimeError("boom"),
    ):
        result = load_safe_auto_approval_envelope()
    assert result.get("_error") is True
    assert "boom" in result["reason"]


def test_real_action_risk_yaml_loads_the_governed_envelope() -> None:
    """End-to-end against the real .intent/enforcement/config/action_risk.yaml
    on disk (via the real IntentRepository, not mocked) — proves the section
    added for #853 actually parses and contains the five governor-named
    actions."""
    result = load_safe_auto_approval_envelope()
    assert "_error" not in result
    assert result["authorized_actions"] == frozenset(
        {"fix.imports", "fix.ids", "fix.logging", "fix.headers", "fix.format"}
    )
    assert set(result["authorized_path_prefixes"]) == {"src/", "tests/"}
    assert result["authorized_extensions"] == (".py",)
