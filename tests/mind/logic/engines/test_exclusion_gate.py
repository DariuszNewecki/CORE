"""architecture.intent.excludes_exempt_something — an exclude entry that
matches no file, only out-of-scope files, or only files that would not
violate anyway is reported; a live exemption, and one the probe cannot
decide, is kept."""

from __future__ import annotations

from pathlib import Path

import pytest

from mind.governance.executable_rule import ExecutableRule
from mind.logic.engines.ast_gate.engine import ASTGateEngine
from mind.logic.engines.exclusion_gate import (
    EXEMPTS_NOTHING,
    NO_FILE,
    OUT_OF_SCOPE,
    ExclusionGateEngine,
    _repo_files,
    find_dead_excludes,
)
from shared.path_resolver import PathResolver


_FILES = [
    "src/shared/utils/subprocess_utils.py",
    "src/body/clean.py",
    "src/will/workers/test_runner_sensor.py",
    "tests/test_something.py",
]


def _rule(
    excludes: list[str],
    *,
    engine: str = "ast_gate",
    scope: list[str] | None = None,
    context_level: bool = False,
) -> ExecutableRule:
    return ExecutableRule(
        rule_id="demo.rule",
        engine=engine,
        params={"check_type": "forbidden_primitives"},
        enforcement="warning",
        scope=scope or ["src/**/*.py"],
        exclusions=excludes,
        is_context_level=context_level,
    )


def _probe(violating: set[str], undecided: frozenset[str] = frozenset()):
    calls: list[str] = []

    async def probe(rule: ExecutableRule, path: Path) -> bool | None:
        rel = path.relative_to(Path("/repo")).as_posix()
        calls.append(rel)
        if rel in undecided:
            return None
        return rel in violating

    probe.calls = calls  # type: ignore[attr-defined]
    return probe


async def _judge(rule: ExecutableRule, probe) -> list[tuple[str, str]]:
    dead = await find_dead_excludes([rule], _FILES, Path("/repo"), probe)
    return [(d.entry, d.reason) for d in dead]


async def test_entry_matching_no_file_is_dead() -> None:
    assert await _judge(_rule(["src/gone.py"]), _probe(set())) == [
        ("src/gone.py", NO_FILE)
    ]


async def test_entry_matching_only_outside_applies_to_is_dead() -> None:
    assert await _judge(_rule(["tests/**"]), _probe(set())) == [
        ("tests/**", OUT_OF_SCOPE)
    ]


async def test_entry_whose_files_would_not_violate_is_dead() -> None:
    """The 2026-10-07 case: a test-file glob that covers a production module."""
    probe = _probe(violating=set())
    assert await _judge(_rule(["src/will/**/test_*.py"]), probe) == [
        ("src/will/**/test_*.py", EXEMPTS_NOTHING)
    ]
    assert probe.calls == ["src/will/workers/test_runner_sensor.py"]


async def test_live_exemption_is_kept() -> None:
    probe = _probe(violating={"src/shared/utils/subprocess_utils.py"})
    assert await _judge(_rule(["src/shared/utils/subprocess_utils.py"]), probe) == []


async def test_entry_is_live_if_any_covered_file_violates() -> None:
    probe = _probe(violating={"src/body/clean.py"})
    assert await _judge(_rule(["src/body/**", "src/will/**"]), probe) == [
        ("src/will/**", EXEMPTS_NOTHING)
    ]


async def test_undecided_probe_keeps_the_entry() -> None:
    probe = _probe(violating=set(), undecided=frozenset({"src/body/clean.py"}))
    assert await _judge(_rule(["src/body/clean.py"]), probe) == []


@pytest.mark.parametrize(
    "kwargs",
    [{"engine": "llm_gate"}, {"engine": "ast_gate", "context_level": True}],
)
async def test_unprobed_engines_judged_on_matching_only(kwargs: dict) -> None:
    probe = _probe(violating=set())
    rule = _rule(["src/body/clean.py", "src/gone.py"], **kwargs)
    assert await _judge(rule, probe) == [("src/gone.py", NO_FILE)]
    assert probe.calls == []


async def test_real_ast_gate_probe_tells_live_from_dead(tmp_path: Path) -> None:
    """End to end with the real engine the rule is mapped to."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "runner.py").write_text(
        "import subprocess\nsubprocess.run(['true'])\n"
    )
    (tmp_path / "src" / "clean.py").write_text("x = 1\n")
    engine = ASTGateEngine(path_resolver=PathResolver(repo_root=tmp_path))
    rule = ExecutableRule(
        rule_id="demo.rule",
        engine="ast_gate",
        params={"check_type": "forbidden_primitives", "forbidden": ["subprocess.run"]},
        enforcement="warning",
        scope=["src/**/*.py"],
        exclusions=["src/runner.py", "src/clean.py"],
    )

    async def probe(r: ExecutableRule, path: Path) -> bool | None:
        result = await engine.verify(path, r.params)
        return bool(result.violations) or not result.ok

    dead = await find_dead_excludes([rule], _repo_files(tmp_path), tmp_path, probe)
    assert [(d.entry, d.reason) for d in dead] == [("src/clean.py", EXEMPTS_NOTHING)]


def test_repo_files_prunes_structural_dirs_but_keeps_hidden_intent(
    tmp_path: Path,
) -> None:
    for rel in (
        ".intent/META/x.json",
        ".git/HEAD",
        "src/__pycache__/a.pyc",
        "src/a.py",
    ):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("")
    assert sorted(_repo_files(tmp_path)) == [".intent/META/x.json", "src/a.py"]


async def test_unknown_check_type_is_refused() -> None:
    findings = await ExclusionGateEngine().verify_context(
        None,  # type: ignore[arg-type]
        {"check_type": "something_else"},
    )
    assert [f.check_id for f in findings] == ["exclusion_gate.unknown_check_type"]


def test_is_context_level_only_for_its_check() -> None:
    assert ExclusionGateEngine.is_context_level_for("excludes_exempt_something")
    assert not ExclusionGateEngine.is_context_level_for("other")
