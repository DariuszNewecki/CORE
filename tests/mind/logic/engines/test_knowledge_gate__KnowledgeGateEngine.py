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
