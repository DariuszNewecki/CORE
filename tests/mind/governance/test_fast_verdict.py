"""ADR-168 D4.3 fast verdict: producer feedback that names what it did not evaluate.

Two layers:
- classification on a controlled audit result (blocking vs. not evaluated,
  never PASS, NO_CHANGES);
- one real run on an adopter project built from the bundled floor and the
  real ``adopt-pack`` delivery of ``core/starter-python``, with git, so the
  change scope, the rules and the findings are the genuine ones.
"""

from __future__ import annotations

import importlib.resources
import shutil
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mind.governance.fast_verdict import (
    BLOCKED,
    CLEAR_IN_SCOPE,
    NO_CHANGES,
    run_fast_verdict,
)
from shared.infrastructure.intent.intent_repository import IntentRepository


_BARE_EXCEPT = "def f():\n    try:\n        return 1\n    except:\n        pass\n"


def _audit_result(findings: list[dict], **stats) -> dict:
    return {
        "findings": findings,
        "stats": {
            "skipped_context_level_ids": stats.get("context", []),
            "failed_rule_ids": stats.get("failed", []),
        },
        "skipped_rules": stats.get("services", []),
        "law_state": {"relationship": "MATCH", "drift_paths": []},
    }


def _block(rule_id: str, **context) -> dict:
    return {
        "check_id": rule_id,
        "severity": "block",
        "file_path": "src/a.py",
        "line_number": 3,
        "message": "m",
        "context": context,
    }


async def _judge(tmp_path: Path, result: dict) -> dict:
    (tmp_path / "src").mkdir(exist_ok=True)
    (tmp_path / "src" / "a.py").write_text("x = 1\n")
    repo = MagicMock()
    repo.get_rule.side_effect = lambda rid: type(
        "R", (), {"content": {"enforcement": "blocking"}}
    )()
    with patch(
        "mind.governance.fast_verdict.run_stateless_audit",
        AsyncMock(return_value=result),
    ):
        return await run_fast_verdict(repo, tmp_path, files=["src/a.py"])


@pytest.mark.asyncio
async def test_a_blocking_violation_is_blocked(tmp_path: Path) -> None:
    out = await _judge(tmp_path, _audit_result([_block("r.one")]))
    assert out["verdict"] == BLOCKED
    assert out["blocking"] == [
        {"rule_id": "r.one", "file": "src/a.py", "line": 3, "message": "m"}
    ]
    assert out["authoritative"] is False


@pytest.mark.asyncio
async def test_unavailable_blocking_finding_is_not_a_violation(tmp_path: Path) -> None:
    """A check that could not run is named as not evaluated, never as BLOCKED."""
    finding = _block("r.runtime", finding_type="ENFORCEMENT_UNAVAILABLE")
    out = await _judge(tmp_path, _audit_result([finding]))
    assert out["verdict"] == CLEAR_IN_SCOPE
    assert out["not_evaluated"]["unavailable"] == ["r.runtime"]


@pytest.mark.asyncio
async def test_everything_not_evaluated_is_named(tmp_path: Path) -> None:
    result = _audit_result(
        [],
        context=["ctx.rule"],
        failed=["crashed.rule"],
        services=[{"rule_id": "db.rule", "enforcement": "blocking"}],
    )
    out = await _judge(tmp_path, result)
    assert out["verdict"] == CLEAR_IN_SCOPE
    ne = out["not_evaluated"]
    assert ne["context_level"] == [{"rule_id": "ctx.rule", "enforcement": "blocking"}]
    assert ne["needs_services"] == [{"rule_id": "db.rule", "enforcement": "blocking"}]
    assert ne["failed"] == ["crashed.rule"]


@pytest.mark.asyncio
async def test_never_says_pass(tmp_path: Path) -> None:
    out = await _judge(tmp_path, _audit_result([]))
    assert (
        out["verdict"] != "PASS"
        and "PASS is given only by the full audit" in out["note"]
    )


@pytest.mark.asyncio
async def test_no_files_in_scope_is_no_changes(tmp_path: Path) -> None:
    out = await run_fast_verdict(MagicMock(), tmp_path, files=["gone.py"])
    assert out["verdict"] == NO_CHANGES
    assert out["scope"]["removed"] == ["gone.py"]


# --- a real adopter project -------------------------------------------------


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def adopter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The machinery floor plus core/starter-python, delivered by adopt-pack."""
    from cli.resources.project.adopt_pack import adopt_pack_command

    monkeypatch.setattr(
        "body.services.outside_write_ledger.database_is_configured", lambda: False
    )
    target = tmp_path / "proj"
    shutil.copytree(
        Path(str(importlib.resources.files("shared._machinery_floor"))),
        target / ".intent",
        ignore=shutil.ignore_patterns("__pycache__", "__init__.py"),
    )
    (target / "src" / "pkg").mkdir(parents=True)
    (target / "src" / "pkg" / "ok.py").write_text('"""Ok."""\n')
    import asyncio

    with patch(
        "cli.logic.byor.core_source_root", return_value=tmp_path / "core-install"
    ):
        asyncio.run(
            adopt_pack_command.__wrapped__(
                pack_id="core/starter-python",
                target_dir=target,
                write=True,
                override=[],
            )
        )
    _git(target, "init", "-q")
    _git(target, "add", "-A")
    _git(target, "commit", "-q", "-m", "law")
    return target


@pytest.mark.asyncio
async def test_real_project_change_scope_and_verdicts(adopter: Path) -> None:
    repo = IntentRepository(strict=True, root=adopter / ".intent")

    clean = await run_fast_verdict(repo, adopter)
    assert clean["verdict"] == NO_CHANGES

    (adopter / "src" / "pkg" / "bad.py").write_text(_BARE_EXCEPT)
    blocked = await run_fast_verdict(repo, adopter)
    assert blocked["scope"]["files"] == ["src/pkg/bad.py"]
    assert blocked["verdict"] == BLOCKED
    assert [b["rule_id"] for b in blocked["blocking"]] == ["starter.no_bare_except"]
    assert blocked["blocking"][0]["file"].endswith("bad.py")

    (adopter / "src" / "pkg" / "bad.py").write_text(
        _BARE_EXCEPT.replace("except:", "except OSError:")
    )
    fixed = await run_fast_verdict(repo, adopter)
    assert fixed["verdict"] == CLEAR_IN_SCOPE
    assert fixed["blocking"] == []
    assert fixed["law"]["relationship"] == "MATCH"
