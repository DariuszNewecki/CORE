"""Tests for Scout CLI logic — detect phase, fallback loading, output builders.

Source: src/cli/logic/scout.py

Tests target the deterministic, I/O-light helpers that do not require an LLM
or a live CoreContext: full-repo signal extraction, fallback candidate loading,
rules/mappings document construction, and enforcement normalization invariants.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import yaml

from cli.logic.scout import (
    _build_mappings_document,
    _build_rules_document,
    _candidate_cache_key,
    _evict_candidate_cache,
    _extract_repo_signals,
    _format_signal_report,
    _load_candidate_cache,
    _load_fallback_candidates,
    _save_candidate_cache,
)


# ── _extract_repo_signals ──────────────────────────────────────────────────────


def test_extract_counts_python_files(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("def foo(): pass\n")
    (tmp_path / "b.py").write_text("class Bar: pass\n")

    signals = _extract_repo_signals(tmp_path)

    assert signals["total_py_files"] == 2
    assert signals["files_parsed"] == 2
    assert signals["files_failed"] == 0


def test_extract_skips_venv_directories(tmp_path: Path) -> None:
    (tmp_path / "src.py").write_text("x = 1\n")
    venv = tmp_path / ".venv"
    venv.mkdir()
    (venv / "lib.py").write_text("x = 2\n")

    signals = _extract_repo_signals(tmp_path)

    assert signals["total_py_files"] == 1


def test_extract_counts_test_files(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_foo.py").write_text("def test_ok(): pass\n")
    (tmp_path / "src.py").write_text("def foo(): pass\n")

    signals = _extract_repo_signals(tmp_path)

    assert signals["test_files"] == 1


def test_extract_print_count(tmp_path: Path) -> None:
    (tmp_path / "mod.py").write_text("print('a')\nprint('b')\nx = 1\n")

    signals = _extract_repo_signals(tmp_path)

    assert signals["print_call_count"] == 2


def test_extract_bare_except_count(tmp_path: Path) -> None:
    src = (
        "try:\n    pass\nexcept:\n    pass\n"
        "try:\n    pass\nexcept Exception:\n    pass\n"
    )
    (tmp_path / "mod.py").write_text(src)

    signals = _extract_repo_signals(tmp_path)

    assert signals["bare_except_count"] == 1
    assert signals["typed_except_pass_count"] == 1


def test_extract_bare_except_does_not_count_typed(tmp_path: Path) -> None:
    src = (
        "try:\n    pass\nexcept Exception:\n    pass\n"
        "try:\n    pass\nexcept BaseException:\n    x = 1\n"
    )
    (tmp_path / "mod.py").write_text(src)

    signals = _extract_repo_signals(tmp_path)

    assert signals["bare_except_count"] == 0
    assert signals["typed_except_pass_count"] == 1


def test_extract_future_annotations(tmp_path: Path) -> None:
    (tmp_path / "with_fa.py").write_text(
        "from __future__ import annotations\ndef foo(): pass\n"
    )
    (tmp_path / "without_fa.py").write_text("def foo(): pass\n")

    signals = _extract_repo_signals(tmp_path)

    assert signals["future_annotations_files"] == 1


def test_extract_type_checking_guard(tmp_path: Path) -> None:
    src = (
        "from __future__ import annotations\n"
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    import os\n"
    )
    (tmp_path / "mod.py").write_text(src)

    signals = _extract_repo_signals(tmp_path)

    assert signals["type_checking_files"] == 1


def test_extract_public_defs_and_annotations(tmp_path: Path) -> None:
    src = (
        "def public_annotated() -> None: pass\n"
        "def public_unannotated(): pass\n"
        "def _private(): pass\n"
    )
    (tmp_path / "mod.py").write_text(src)

    signals = _extract_repo_signals(tmp_path)

    assert signals["public_defs"] == 2
    assert signals["public_defs_annotated"] == 1


def test_extract_public_defs_docstring(tmp_path: Path) -> None:
    src = (
        'def with_doc() -> None:\n    """Has a docstring."""\n    pass\n'
        "def without_doc() -> None: pass\n"
    )
    (tmp_path / "mod.py").write_text(src)

    signals = _extract_repo_signals(tmp_path)

    assert signals["public_defs_docstring"] == 1


def test_extract_import_aliases_tracked(tmp_path: Path) -> None:
    (tmp_path / "mod.py").write_text("import typing as t\nimport os\n")

    signals = _extract_repo_signals(tmp_path)

    aliases = dict(signals["top_aliases"])
    assert "import typing as t" in aliases


def test_extract_empty_repo(tmp_path: Path) -> None:
    signals = _extract_repo_signals(tmp_path)

    assert signals["total_py_files"] == 0
    assert signals["files_parsed"] == 0
    assert signals["public_defs"] == 0


# ── _format_signal_report ──────────────────────────────────────────────────────


def test_format_signal_report_includes_key_fields(tmp_path: Path) -> None:
    signals = {
        "total_py_files": 10,
        "files_parsed": 10,
        "files_failed": 0,
        "test_files": 2,
        "has_src_layout": True,
        "public_defs": 20,
        "public_defs_annotated": 15,
        "public_defs_docstring": 10,
        "public_classes": 5,
        "public_classes_docstring": 4,
        "future_annotations_files": 8,
        "type_checking_files": 3,
        "bare_except_count": 1,
        "typed_except_pass_count": 0,
        "print_call_count": 2,
        "abstract_methods": 0,
        "py_typed": False,
        "top_aliases": [("import typing as t", 8)],
        "top_decorators": [("staticmethod", 5)],
        "ci_signals": {},
    }
    text = _format_signal_report(signals)

    assert "10" in text  # total files
    assert "print" in text.lower()
    assert "75%" in text  # 15/20 annotated
    assert "import typing as t" in text


def test_format_signal_report_zero_public_symbols_no_crash() -> None:
    signals = {
        "total_py_files": 1,
        "files_parsed": 1,
        "files_failed": 0,
        "test_files": 0,
        "has_src_layout": False,
        "public_defs": 0,
        "public_defs_annotated": 0,
        "public_defs_docstring": 0,
        "public_classes": 0,
        "public_classes_docstring": 0,
        "future_annotations_files": 0,
        "type_checking_files": 0,
        "bare_except_count": 0,
        "typed_except_pass_count": 0,
        "print_call_count": 0,
        "abstract_methods": 0,
        "py_typed": False,
        "top_aliases": [],
        "top_decorators": [],
        "ci_signals": {},
    }
    text = _format_signal_report(signals)
    assert "n/a" in text  # pct of 0-of-0 is n/a


def test_format_signal_report_ci_signals_included() -> None:
    signals = {
        "total_py_files": 5,
        "files_parsed": 5,
        "files_failed": 0,
        "test_files": 0,
        "has_src_layout": False,
        "public_defs": 0,
        "public_defs_annotated": 0,
        "public_defs_docstring": 0,
        "public_classes": 0,
        "public_classes_docstring": 0,
        "future_annotations_files": 0,
        "type_checking_files": 0,
        "bare_except_count": 0,
        "typed_except_pass_count": 0,
        "print_call_count": 0,
        "abstract_methods": 0,
        "py_typed": False,
        "top_aliases": [],
        "top_decorators": [],
        "ci_signals": {"mypy_configured": True, "mypy_strict": True},
    }
    text = _format_signal_report(signals)
    assert "mypy" in text
    assert "strict" in text


# ── _load_fallback_candidates ──────────────────────────────────────────────────


def test_fallback_candidates_loaded_from_starter(tmp_path: Path) -> None:
    """Fallback loads rule IDs from starter.json; engine comes from catalog matching."""
    rules_path = tmp_path / "examples" / "starter-intent" / ".intent" / "rules"
    rules_path.mkdir(parents=True)

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

    candidates = _load_fallback_candidates(tmp_path)

    assert len(candidates) == 1
    c = candidates[0]
    assert c["rule_id"] == "scout.docstrings"
    assert c["enforcement"] == "reporting"
    # engine is NOT present here — it's added by _match_enforcement in induce_rules()
    assert "engine" not in c


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


def test_build_rules_document_declared_only_has_enforcement_note() -> None:
    c = _make_candidate(enforcement_matched=False)
    c.pop("engine", None)
    c.pop("params", None)
    doc = json.loads(_build_rules_document([c]))
    rule = doc["rules"][0]
    assert "enforcement_note" in rule
    assert "declared" in rule["enforcement_note"]


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


# ── Candidate cache helpers ────────────────────────────────────────────────────


_SAMPLE_CANDIDATES = [
    {
        "rule_id": "scout.no_print",
        "statement": "MUST NOT use print().",
        "enforcement": "reporting",
        "rationale": "6 print() calls found.",
        "evidence_sample": "",
        "ramp_note": "",
    }
]


def test_candidate_cache_key_deterministic(tmp_path: Path) -> None:
    key1 = _candidate_cache_key("signals text", tmp_path)
    key2 = _candidate_cache_key("signals text", tmp_path)
    assert key1 == key2
    assert len(key1) == 16
    assert key1.isalnum()


def test_candidate_cache_key_differs_on_different_signals(tmp_path: Path) -> None:
    assert _candidate_cache_key("signals A", tmp_path) != _candidate_cache_key(
        "signals B", tmp_path
    )


def test_candidate_cache_key_differs_on_prompt_change(tmp_path: Path) -> None:
    prompt_dir = tmp_path / "var" / "prompts" / "scout_rule_inducer"
    prompt_dir.mkdir(parents=True)
    system_txt = prompt_dir / "system.txt"

    system_txt.write_text("original prompt")
    key_before = _candidate_cache_key("same signals", tmp_path)

    system_txt.write_text("updated prompt")
    key_after = _candidate_cache_key("same signals", tmp_path)

    assert key_before != key_after


def test_load_candidate_cache_miss(tmp_path: Path) -> None:
    result = _load_candidate_cache(tmp_path, "nonexistent")
    assert result is None


def test_save_and_load_candidate_cache(tmp_path: Path) -> None:
    key = _candidate_cache_key("test signals", tmp_path)
    fh = MagicMock()
    cache_dir = tmp_path / "var" / "cache" / "scout"

    def fake_ensure_dir(rel: str) -> None:
        (tmp_path / rel).mkdir(parents=True, exist_ok=True)

    def fake_write_runtime_text(rel: str, content: str) -> None:
        (tmp_path / rel).write_text(content, encoding="utf-8")

    fh.ensure_dir.side_effect = fake_ensure_dir
    fh.write_runtime_text.side_effect = fake_write_runtime_text

    _save_candidate_cache(fh, key, _SAMPLE_CANDIDATES)
    loaded = _load_candidate_cache(tmp_path, key)

    assert loaded == _SAMPLE_CANDIDATES


def test_save_candidate_cache_failure_does_not_raise(tmp_path: Path) -> None:
    fh = MagicMock()
    fh.ensure_dir.side_effect = OSError("disk full")
    _save_candidate_cache(fh, "somekey", _SAMPLE_CANDIDATES)  # must not raise


def test_evict_candidate_cache_removes_file(tmp_path: Path) -> None:
    key = _candidate_cache_key("evict signals", tmp_path)
    cache_dir = tmp_path / "var" / "cache" / "scout"
    cache_dir.mkdir(parents=True)
    cache_file = cache_dir / f"{key}.json"
    cache_file.write_text(json.dumps(_SAMPLE_CANDIDATES))

    _evict_candidate_cache(tmp_path, key)

    assert not cache_file.exists()


def test_evict_candidate_cache_noop_when_absent(tmp_path: Path) -> None:
    _evict_candidate_cache(tmp_path, "missing_key")  # must not raise
