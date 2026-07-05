"""Regression test for issue #150: _check_capability_assignment must
honor exclude_patterns even when a symbol's file_path is None.

Before the fix, the substring check `any(p in symbol_data.get("file_path", "")
for p in exclude_patterns)` silently bypassed exclusion whenever file_path
was missing — patterns like "tests/" would never match the empty fallback.

The fix synthesizes a path from `module` via _resolve_symbol_path and
matches with fnmatch, mirroring _check_ast_duplication.
"""

from __future__ import annotations

from mind.logic.engines.knowledge_gate import KnowledgeGateEngine


class _FakeContext:
    """Minimal AuditorContext stand-in — only symbols_map is consulted by
    _check_capability_assignment."""

    def __init__(self, symbols_map: dict) -> None:
        self.symbols_map = symbols_map


def test_capability_assignment_excludes_module_path_when_file_path_missing():
    symbols_map = {
        "sym-1": {
            "name": "PublicTestHelper",
            "is_public": True,
            "file_path": None,
            "module": "tests.helpers.public_helper",
            "key": "unassigned",
            "line_number": 12,
        },
    }
    engine = KnowledgeGateEngine()
    findings = engine._check_capability_assignment(
        _FakeContext(symbols_map),
        {"exclude_patterns": ["src/tests/*"]},
    )
    assert findings == [], (
        "symbol with file_path=None and module under tests/ must be filtered "
        "by the synthesized 'src/tests/...' path; without the fix the "
        "substring check silently bypassed exclusion"
    )


def test_capability_assignment_flags_unassigned_when_not_excluded():
    symbols_map = {
        "sym-1": {
            "name": "PublicApiSymbol",
            "is_public": True,
            "file_path": "src/api/public.py",
            "module": "api.public",
            "key": "unassigned",
            "line_number": 7,
        },
    }
    engine = KnowledgeGateEngine()
    findings = engine._check_capability_assignment(
        _FakeContext(symbols_map),
        {"exclude_patterns": ["*tests/*", "*scripts/*"]},
    )
    assert len(findings) == 1
    assert findings[0].check_id == "linkage.capability.unassigned"
    assert findings[0].file_path == "src/api/public.py"


class _NoWorkers:
    """intent_repo stand-in: orphan_file_check seeds from declared workers."""

    def list_workers(self):
        return []


class _OrphanContext:
    """Minimal AuditorContext stand-in for _check_orphan_files — only
    repo_path and intent_repo.list_workers() are consulted."""

    def __init__(self, repo_path) -> None:
        self.repo_path = repo_path
        self.intent_repo = _NoWorkers()


def test_orphan_check_resolves_dotdot_relative_imports(tmp_path):
    """Regression: a file reachable only via `from ..x import y` must NOT be
    flagged orphan.

    Before the fix, get_imports ignored ``ast.ImportFrom.level``, so a
    ``..``-relative target never resolved and any file reachable only that way
    was falsely flagged — exactly how src/mind/coherence/llm_judge.py (reached
    via ``from ..llm_judge import judge_contradiction_pair`` in the CCC checks)
    landed in the assisted-remediation lane. The level-aware resolution closes
    the gap; the true orphan below proves detection still fires.
    """
    src = tmp_path / "src"
    (src / "pkg" / "deep").mkdir(parents=True)
    (src / "pkg" / "__init__.py").write_text("")
    (src / "pkg" / "deep" / "__init__.py").write_text("")
    # The entry point reaches `shared` only through a 2-level relative import.
    # The bare module name "shared" does NOT resolve from src-root, so only
    # level-aware resolution (base = src/pkg/) finds src/pkg/shared.py.
    (src / "pkg" / "deep" / "entry.py").write_text("from ..shared import thing\n")
    (src / "pkg" / "shared.py").write_text("thing = 1\n")
    (src / "orphan.py").write_text("x = 1\n")

    engine = KnowledgeGateEngine()
    findings = engine._check_orphan_files(
        _OrphanContext(tmp_path),
        {"entry_points": ["src/pkg/deep/entry.py"]},
    )
    flagged = {f.file_path for f in findings}
    assert "src/pkg/shared.py" not in flagged, (
        "relative-import-reachable file falsely flagged orphan — "
        "ImportFrom.level not honored"
    )
    assert "src/orphan.py" in flagged, (
        "a genuinely unreachable file must still be flagged"
    )
