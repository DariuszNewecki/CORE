# tests/cli/resources/workers/test_export_run.py
"""`workers export-run` — write path, --stdout parity, refusal exit codes (#893).

Calls the undecorated coroutine (`.__wrapped__`) with a SimpleNamespace ctx
(the consequence_chain precedent) so no DB is needed: the query service is
replaced with a stub returning canned rows.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
import typer

import cli.resources.workers.export_run as er
from body.services.blackboard_service.blackboard_run_export import (
    build_run_export,
    serialize_run_export,
)


RID = "11111111-2222-4333-8444-555555555555"


def _ctx(repo_root: Path) -> SimpleNamespace:
    return SimpleNamespace(
        obj=SimpleNamespace(git_service=SimpleNamespace(repo_path=str(repo_root)))
    )


def _row(entry_id: str, subject: str, created_at: str) -> dict[str, Any]:
    return {
        "id": entry_id,
        "worker_uuid": None,
        "entry_type": "report",
        "phase": "execution",
        "status": "resolved",
        "subject": subject,
        "payload": {"run_id": RID},
        "first_payload": None,
        "resolution_mechanism": None,
        "claimed_by": None,
        "claimed_at": None,
        "resolved_at": None,
        "created_at": created_at,
        "updated_at": created_at,
        "last_seen_at": created_at,
        "occurrence_count": 1,
        "orphan_release_count": 0,
    }


def _complete_run() -> list[dict[str, Any]]:
    return [
        _row("e1", f"goal_run.{RID}.start", "2026-09-13T11:24:36.969586+00:00"),
        _row("e2", f"goal_run.{RID}.outcome", "2026-09-13T11:24:38.459744+00:00"),
    ]


def _stub_service(monkeypatch, rows: list[dict[str, Any]]) -> None:
    svc = SimpleNamespace(fetch_entries_by_run_id=AsyncMock(return_value=rows))
    monkeypatch.setattr(er, "BlackboardQueryService", lambda: svc)


async def _call(ctx, run_id: str, *, partial: bool = False, to_stdout: bool = False):
    return await er.export_run_cmd.__wrapped__(
        ctx, run_id, partial=partial, to_stdout=to_stdout
    )


def _expected_path(repo_root: Path) -> Path:
    return repo_root / "var" / "exports" / "blackboard_runs" / f"{RID}.json"


async def test_writes_canonical_file_under_var_exports(monkeypatch, tmp_path) -> None:
    _stub_service(monkeypatch, _complete_run())
    await _call(_ctx(tmp_path), RID)
    out = _expected_path(tmp_path)
    assert out.exists()
    expected = serialize_run_export(build_run_export(RID, _complete_run()))
    assert out.read_bytes() == expected


async def test_re_export_is_byte_identical(monkeypatch, tmp_path) -> None:
    _stub_service(monkeypatch, _complete_run())
    await _call(_ctx(tmp_path), RID)
    first = _expected_path(tmp_path).read_bytes()
    await _call(_ctx(tmp_path), RID)
    assert _expected_path(tmp_path).read_bytes() == first


async def test_stdout_emits_the_same_bytes_and_writes_nothing(
    monkeypatch, tmp_path, capfdbinary
) -> None:
    _stub_service(monkeypatch, _complete_run())
    await _call(_ctx(tmp_path), RID, to_stdout=True)
    captured = capfdbinary.readouterr()
    assert captured.out == serialize_run_export(build_run_export(RID, _complete_run()))
    assert not _expected_path(tmp_path).exists()


async def test_unknown_run_exits_1_and_writes_nothing(monkeypatch, tmp_path) -> None:
    _stub_service(monkeypatch, [])
    with pytest.raises(typer.Exit) as exc:
        await _call(_ctx(tmp_path), RID)
    assert exc.value.exit_code == 1
    assert not _expected_path(tmp_path).exists()


async def test_incomplete_run_exits_1_without_partial(monkeypatch, tmp_path) -> None:
    _stub_service(monkeypatch, _complete_run()[:1])
    with pytest.raises(typer.Exit) as exc:
        await _call(_ctx(tmp_path), RID)
    assert exc.value.exit_code == 1
    assert not _expected_path(tmp_path).exists()


async def test_incomplete_run_exports_stamped_partial_with_flag(
    monkeypatch, tmp_path
) -> None:
    _stub_service(monkeypatch, _complete_run()[:1])
    await _call(_ctx(tmp_path), RID, partial=True)
    body = _expected_path(tmp_path).read_bytes()
    assert b'"completeness":"partial"' in body
