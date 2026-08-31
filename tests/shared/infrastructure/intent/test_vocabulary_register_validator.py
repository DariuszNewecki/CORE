# tests/shared/infrastructure/intent/test_vocabulary_register_validator.py

"""Tests for validate_register_casing's fail-closed bootstrap-guard contract
(#854, ADR-158) -- distinct from check_register_casing's pure-report shape,
exercised separately in
tests/mind/logic/engines/test_artifact_gate__register_casing.py via the
artifact_gate adapter. This file proves the OTHER caller: IntentRepository.__init__
raises GovernanceError in strict mode rather than silently continuing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.infrastructure.intent.errors import GovernanceError
from shared.infrastructure.intent.vocabulary_register_validator import (
    validate_register_casing,
)


def _scaffold(tmp_path: Path, files: dict[str, str]) -> Path:
    intent_root = tmp_path / ".intent"
    for rel, content in files.items():
        dest = intent_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    if "META/enums.json" not in files:
        enums_path = intent_root / "META" / "enums.json"
        enums_path.parent.mkdir(parents=True, exist_ok=True)
        enums_path.write_text('{"definitions": {}}', encoding="utf-8")
    return intent_root


def test_strict_mode_raises_on_violation(tmp_path: Path) -> None:
    intent_root = _scaffold(
        tmp_path, {"rules/example.json": '{"metadata": {"authority": "Policy"}}'}
    )
    with pytest.raises(GovernanceError, match="operational_fields_must_be_lowercase"):
        validate_register_casing(intent_root, strict=True)


def test_non_strict_mode_returns_violations_without_raising(tmp_path: Path) -> None:
    intent_root = _scaffold(
        tmp_path, {"rules/example.json": '{"metadata": {"authority": "Policy"}}'}
    )
    violations = validate_register_casing(intent_root, strict=False)

    assert violations
    assert any("metadata.authority" in v for v in violations)


def test_clean_tree_returns_empty_and_does_not_raise(tmp_path: Path) -> None:
    intent_root = _scaffold(
        tmp_path, {"rules/example.json": '{"metadata": {"authority": "policy"}}'}
    )
    violations = validate_register_casing(intent_root, strict=True)

    assert violations == []
