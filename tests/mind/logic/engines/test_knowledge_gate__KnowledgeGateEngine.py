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

    def list_phases(self):
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


class _OnePhase(_NoWorkers):
    """intent_repo stand-in declaring one phase implementation."""

    def __init__(self, impl: str) -> None:
        self._impl = impl

    def list_phases(self):
        return ["p"]

    def load_phase(self, phase_id):
        return {"implementation": self._impl}


def _orphans(tmp_path, entry_points, intent_repo=None) -> set[str]:
    ctx = _OrphanContext(tmp_path)
    if intent_repo is not None:
        ctx.intent_repo = intent_repo
    findings = KnowledgeGateEngine()._check_orphan_files(
        ctx, {"entry_points": entry_points}
    )
    return {f.file_path for f in findings}


def test_orphan_check_follows_string_named_modules(tmp_path):
    """Dynamic loads named by string are uses: a dotted ``module.Class`` path
    (service_registry KERNEL_SERVICES) and a ``src/....py`` path (a child
    process launched by file, as consequence_chain runs scenario_runner)."""
    src = tmp_path / "src"
    (src / "pkg").mkdir(parents=True)
    (src / "pkg" / "entry.py").write_text(
        'SERVICES = {"svc": "pkg.service.Service"}\nRUNNER = "src/pkg/runner.py"\n'
    )
    (src / "pkg" / "service.py").write_text("class Service: ...\n")
    (src / "pkg" / "runner.py").write_text("x = 1\n")
    (src / "pkg" / "orphan.py").write_text("x = 1\n")
    flagged = _orphans(tmp_path, ["src/pkg/entry.py"])
    assert "src/pkg/service.py" not in flagged
    assert "src/pkg/runner.py" not in flagged
    assert "src/pkg/orphan.py" in flagged


def test_orphan_check_ignores_docstring_mentions(tmp_path):
    """A module named only in a docstring is still an orphan."""
    src = tmp_path / "src"
    (src / "pkg").mkdir(parents=True)
    (src / "pkg" / "entry.py").write_text(
        '"""Formerly delegated to pkg.retired; see src/pkg/retired.py."""\n'
    )
    (src / "pkg" / "retired.py").write_text("x = 1\n")
    assert "src/pkg/retired.py" in _orphans(tmp_path, ["src/pkg/entry.py"])


def test_orphan_check_seeds_declared_phases(tmp_path):
    """A phase loaded by phase_registry from its .intent implementation path
    is reachable even though nothing imports it."""
    src = tmp_path / "src"
    (src / "pkg").mkdir(parents=True)
    (src / "pkg" / "entry.py").write_text("x = 1\n")
    (src / "pkg" / "audit_phase.py").write_text("class AuditPhase: ...\n")
    assert "src/pkg/audit_phase.py" in _orphans(tmp_path, ["src/pkg/entry.py"])
    assert "src/pkg/audit_phase.py" not in _orphans(
        tmp_path, ["src/pkg/entry.py"], _OnePhase("pkg.audit_phase.AuditPhase")
    )
