"""Tests for Scout CLI logic — detect phase, fallback loading, output builders.

Source: src/cli/logic/scout.py

Tests target the deterministic, I/O-light helpers that do not require an LLM
or a live CoreContext: signal detection from a temp filesystem, fallback
candidate loading, rules/mappings document construction, and the enforcement
normalization invariants.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from cli.logic.scout import (
    _build_mappings_document,
    _build_rules_document,
    _detect_repo_signals,
    _format_signals,
    _load_fallback_candidates,
)


# ── _detect_repo_signals ───────────────────────────────────────────────────────


def test_detect_counts_python_files(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("def foo(): pass\n")
    (tmp_path / "b.py").write_text("class Bar: pass\n")

    signals, _ = _detect_repo_signals(tmp_path)

    assert signals["total_py_files"] == 2
    assert signals["sampled_files"] == 2


def test_detect_entry_points_sampled_first(tmp_path: Path) -> None:
    # Create many files so entry point must be prioritised
    for i in range(20):
        (tmp_path / f"mod_{i}.py").write_text("x = 1\n")
    (tmp_path / "main.py").write_text("def main(): pass\n")

    _signals, sample_text = _detect_repo_signals(tmp_path)

    # main.py must appear in the sample despite alphabetical ordering
    assert "main.py" in sample_text


def test_detect_identifies_test_directory(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_foo.py").write_text("def test_ok(): pass\n")

    signals, _ = _detect_repo_signals(tmp_path)

    assert signals["has_tests"] is True


def test_detect_no_tests_when_absent(tmp_path: Path) -> None:
    (tmp_path / "src.py").write_text("x = 1\n")

    signals, _ = _detect_repo_signals(tmp_path)

    assert signals["has_tests"] is False


def test_detect_print_count(tmp_path: Path) -> None:
    (tmp_path / "mod.py").write_text("print('a')\nprint('b')\nx = 1\n")

    signals, _ = _detect_repo_signals(tmp_path)

    assert signals["print_calls"] == 2


def test_detect_bare_except_count(tmp_path: Path) -> None:
    src = "try:\n    pass\nexcept:\n    pass\ntry:\n    pass\nexcept Exception:\n    pass\n"
    (tmp_path / "mod.py").write_text(src)

    signals, _ = _detect_repo_signals(tmp_path)

    assert signals["bare_except_occurrences"] >= 1


def test_detect_id_anchors_counted(tmp_path: Path) -> None:
    src = "# ID: abc123\ndef foo(): pass\n# ID: def456\nclass Bar: pass\n"
    (tmp_path / "mod.py").write_text(src)

    signals, _ = _detect_repo_signals(tmp_path)

    assert signals["id_anchors_found"] == 2


def test_detect_empty_repo(tmp_path: Path) -> None:
    signals, sample_text = _detect_repo_signals(tmp_path)

    assert signals["total_py_files"] == 0
    assert signals["sampled_files"] == 0
    assert sample_text == ""


# ── _format_signals ────────────────────────────────────────────────────────────


def test_format_signals_includes_key_fields() -> None:
    signals = {
        "total_py_files": 10,
        "sampled_files": 5,
        "has_src_layout": True,
        "has_tests": True,
        "public_symbols_estimate": 20,
        "docstrings_present_estimate": 10,
        "id_anchors_found": 0,
        "print_calls": 3,
        "bare_except_occurrences": 1,
        "future_annotations_files": 4,
        "type_annotations_present": True,
        "decorator_usage": False,
    }
    text = _format_signals(signals, "--- sample.py ---\ndef foo(): pass")

    assert "10" in text  # total files
    assert "print" in text.lower()
    assert "sample.py" in text


def test_format_signals_zero_public_symbols_no_crash() -> None:
    signals = {
        "total_py_files": 1,
        "sampled_files": 1,
        "has_src_layout": False,
        "has_tests": False,
        "public_symbols_estimate": 0,
        "docstrings_present_estimate": 0,
        "id_anchors_found": 0,
        "print_calls": 0,
        "bare_except_occurrences": 0,
        "future_annotations_files": 0,
        "type_annotations_present": False,
        "decorator_usage": False,
    }
    text = _format_signals(signals, "")
    assert "n/a" in text  # docstring % and id % are n/a when no public symbols


# ── _load_fallback_candidates ──────────────────────────────────────────────────


def test_fallback_candidates_loaded_from_starter(tmp_path: Path) -> None:
    """Fallback loads from CORE repo root, not the target repo."""
    # Build a minimal starter-intent structure under tmp_path as a fake core_root
    rules_path = tmp_path / "examples" / "starter-intent" / ".intent" / "rules"
    rules_path.mkdir(parents=True)
    mappings_path = (
        tmp_path / "examples" / "starter-intent" / ".intent" / "enforcement" / "mappings"
    )
    mappings_path.mkdir(parents=True)

    rules_doc = {
        "kind": "rule_document",
        "metadata": {"id": "rules.starter"},
        "rules": [
            {
                "id": "starter.docstrings",
                "statement": "Public functions MUST have a docstring.",
                "enforcement": "reporting",
            }
        ],
    }
    (rules_path / "starter.json").write_text(json.dumps(rules_doc))

    mappings_doc = {
        "mappings": {
            "starter.docstrings": {
                "engine": "ast_gate",
                "params": {"check_type": "docstrings_present"},
                "scope": {"applies_to": ["src/**/*.py"], "excludes": []},
            }
        }
    }
    (mappings_path / "starter.yaml").write_text(yaml.dump(mappings_doc))

    candidates = _load_fallback_candidates(tmp_path)

    assert len(candidates) == 1
    c = candidates[0]
    # Rule ID re-namespaced from starter.* to scout.*
    assert c["rule_id"] == "scout.docstrings"
    assert c["engine"] == "ast_gate"
    assert c["enforcement"] == "reporting"


def test_fallback_missing_files_returns_empty(tmp_path: Path) -> None:
    result = _load_fallback_candidates(tmp_path)
    assert result == []


# ── _build_rules_document ─────────────────────────────────────────────────────


def _make_candidate(**overrides: object) -> dict:
    base: dict = {
        "rule_id": "scout.docstrings",
        "statement": "Public functions MUST have a docstring.",
        "enforcement": "reporting",
        "rationale": "~50% missing",
        "engine": "ast_gate",
        "params": {"check_type": "docstrings_present"},
        "scope": {"applies_to": ["src/**/*.py"], "excludes": []},
        "evidence_sample": "",
        "ramp_note": "",
    }
    return {**base, **overrides}


def test_build_rules_document_valid_json() -> None:
    doc_str = _build_rules_document([_make_candidate()])
    doc = json.loads(doc_str)

    assert doc["kind"] == "rule_document"
    assert doc["metadata"]["id"] == "rules.scout_inducted"
    assert len(doc["rules"]) == 1
    assert doc["rules"][0]["id"] == "scout.docstrings"


def test_build_rules_document_multiple_rules() -> None:
    c2 = _make_candidate(rule_id="scout.no_print", statement="No print().")
    doc = json.loads(_build_rules_document([_make_candidate(), c2]))

    assert len(doc["rules"]) == 2
    ids = {r["id"] for r in doc["rules"]}
    assert ids == {"scout.docstrings", "scout.no_print"}


# ── _build_mappings_document ──────────────────────────────────────────────────


def test_build_mappings_document_valid_yaml() -> None:
    doc_str = _build_mappings_document([_make_candidate()])
    doc = yaml.safe_load(doc_str)

    assert "mappings" in doc
    assert "scout.docstrings" in doc["mappings"]
    entry = doc["mappings"]["scout.docstrings"]
    assert entry["engine"] == "ast_gate"
    assert entry["params"] == {"check_type": "docstrings_present"}


def test_build_mappings_excludes_omitted_when_empty() -> None:
    c = _make_candidate(scope={"applies_to": ["**/*.py"], "excludes": []})
    doc = yaml.safe_load(_build_mappings_document([c]))
    entry = doc["mappings"]["scout.docstrings"]
    assert "excludes" not in entry.get("scope", {})


def test_build_mappings_excludes_present_when_non_empty() -> None:
    c = _make_candidate(
        scope={"applies_to": ["src/**/*.py"], "excludes": ["tests/**/*.py"]}
    )
    doc = yaml.safe_load(_build_mappings_document([c]))
    entry = doc["mappings"]["scout.docstrings"]
    assert entry["scope"]["excludes"] == ["tests/**/*.py"]
