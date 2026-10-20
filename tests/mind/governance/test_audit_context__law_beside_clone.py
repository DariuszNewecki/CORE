"""ADR-132 D2: the audit walks the law kept beside a sparse clone.

A services clone carries no ``.intent/`` (sparse checkout); the law lives
beside it (MIND) and policies load from there. ``get_files`` must still
return the law files for an ``.intent/``-scoped per-file rule — otherwise the
rule is SCOPE_INERT — and name them ``.intent/...`` exactly as a normal
checkout does, so findings keep stable subject paths.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from mind.governance.audit_context import AuditorContext
from mind.governance.executable_rule import ExecutableRule
from mind.governance.rule_executor import clear_eval_cache, execute_rule
from mind.logic.engines.regex_gate import RegexGateEngine


SCOPE = ".intent/taxonomies/*.yaml"
REL = ".intent/taxonomies/x.yaml"


def _context(repo: Path, law_root: Path) -> AuditorContext:
    ctx = AuditorContext(repo)
    ctx.intent_repo = SimpleNamespace(root=law_root)
    ctx.invalidate_file_cache()
    ctx._per_file_scopes_cache = [SCOPE, "src/**/*.py"]
    return ctx


def _write_law(intent_root: Path) -> Path:
    f = intent_root / "taxonomies" / "x.yaml"
    f.parent.mkdir(parents=True)
    f.write_text("capabilities:\n  - claude.summarize\n", encoding="utf-8")
    (intent_root / "rules").mkdir()
    (intent_root / "rules" / "other.yaml").write_text("a: 1\n", encoding="utf-8")
    return f


def _write_src(repo: Path) -> None:
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "m.py").write_text("x = 1\n", encoding="utf-8")


def test_sparse_clone_walks_law_beside_it(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write_src(repo)
    law = _write_law(tmp_path / "law" / ".intent")

    ctx = _context(repo, tmp_path / "law" / ".intent")
    files = ctx.get_files([SCOPE])

    assert files == [law]
    assert ctx.rel_path(law) == REL
    # The code side is unchanged.
    assert [ctx.rel_path(p) for p in ctx.get_files(["src/**/*.py"])] == ["src/m.py"]


def test_normal_checkout_is_unchanged(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write_src(repo)
    law = _write_law(repo / ".intent")

    ctx = _context(repo, repo / ".intent")
    files = ctx.get_files([SCOPE])

    assert files == [law.resolve()]
    assert ctx.rel_path(files[0]) == REL
    assert len(ctx._file_list_cache or []) == 2  # x.yaml + src/m.py, once each


def test_clone_with_own_intent_is_not_walked_twice(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write_src(repo)
    own = _write_law(repo / ".intent")
    _write_law(tmp_path / "law" / ".intent")

    ctx = _context(repo, tmp_path / "law" / ".intent")

    assert ctx.get_files([SCOPE]) == [own.resolve()]


@pytest.fixture
def _real_regex_gate(monkeypatch: pytest.MonkeyPatch):
    engine = RegexGateEngine()
    monkeypatch.setattr(
        "mind.logic.engines.registry.EngineRegistry.get", lambda engine_id: engine
    )
    clear_eval_cache()
    yield
    clear_eval_cache()


@pytest.mark.usefixtures("_real_regex_gate")
async def test_regex_gate_finding_on_law_file_names_intent_path(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _write_src(repo)
    _write_law(tmp_path / "law" / ".intent")
    ctx = _context(repo, tmp_path / "law" / ".intent")
    rule = ExecutableRule(
        rule_id="capability.taxonomy.no_model_specific_names",
        engine="regex_gate",
        params={"forbidden_patterns": [r"\bclaude\b"]},
        enforcement="blocking",
        scope=[SCOPE],
        rule_content_hash="abc123",
    )

    findings = await execute_rule(rule, ctx)

    assert [f.file_path for f in findings] == [REL]
    assert not any(f.check_id.endswith(".enforcement_failure") for f in findings)
