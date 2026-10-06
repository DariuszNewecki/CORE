"""ADR-169 D5: every write CORE makes outside its repository is recorded --
target, relative path, operation, sha256, producer; never the content.

#953 (governor ruling, option A with one boundary): with a CORE database
configured, the ledger is a precondition -- unreachable before the writes
refuses them, lost after them fails the command and keeps the entries. With
no CORE database configured (standalone install), writes proceed and are
reported unrecorded."""

from __future__ import annotations

import hashlib
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from body.services.outside_write_ledger import (
    OutsideWrite,
    OutsideWriteLedgerUnavailable,
    OutsideWriteLog,
    OutsideWritesUnrecorded,
)


_CONFIGURED = "body.services.outside_write_ledger.database_is_configured"


@pytest.fixture
def configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_CONFIGURED, lambda: True)


@pytest.fixture
def standalone(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_CONFIGURED, lambda: False)


@asynccontextmanager
async def _down():
    raise ConnectionError("no database")
    yield  # pragma: no cover


def _registry_down():
    return patch("body.services.service_registry.ServiceRegistry.session", _down)


def _session_registry(session: MagicMock):
    @asynccontextmanager
    async def _session():
        yield session

    return patch("body.services.service_registry.ServiceRegistry.session", _session)


def test_wrote_records_relative_path_and_hash_not_content(tmp_path: Path) -> None:
    dest = tmp_path / ".intent/rules/pack.json"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"secret-ish content")
    log = OutsideWriteLog(tmp_path, produced_by="project.adopt_pack")

    log.wrote(dest)

    assert log.entries == [
        OutsideWrite(
            ".intent/rules/pack.json",
            "write",
            hashlib.sha256(b"secret-ish content").hexdigest(),
        )
    ]


def test_deleted_has_no_hash(tmp_path: Path) -> None:
    log = OutsideWriteLog(tmp_path, produced_by="project.scout")
    log.deleted(tmp_path / ".intent/rules/scout_inducted.json")
    assert log.entries == [
        OutsideWrite(".intent/rules/scout_inducted.json", "delete", None)
    ]


async def test_flush_inserts_every_entry_once(tmp_path: Path, configured) -> None:
    (tmp_path / "a").write_text("1")
    (tmp_path / "b").write_text("2")
    log = OutsideWriteLog(tmp_path, produced_by="project.new")
    log.wrote(tmp_path / "a")
    log.wrote(tmp_path / "b")
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()

    with _session_registry(session):
        await log.flush()

    sql, rows = session.execute.await_args.args
    assert "INSERT INTO core.outside_writes" in str(sql)
    assert [r["path"] for r in rows] == ["a", "b"]
    assert {r["produced_by"] for r in rows} == {"project.new"}
    assert rows[0]["target_root"] == tmp_path.resolve().as_posix()
    assert "content" not in rows[0]
    session.commit.assert_awaited_once()
    assert log.entries == []


async def test_flush_with_nothing_is_a_no_op(tmp_path: Path, configured) -> None:
    with _registry_down():
        await OutsideWriteLog(tmp_path, produced_by="x").flush()  # no session


async def test_unreachable_ledger_after_writes_raises_and_keeps_entries(
    tmp_path: Path, configured
) -> None:
    (tmp_path / "a").write_text("1")
    log = OutsideWriteLog(tmp_path, produced_by="project.new")
    log.wrote(tmp_path / "a")

    with _registry_down(), pytest.raises(OutsideWritesUnrecorded) as exc:
        await log.flush()

    assert "NOT recorded" in str(exc.value)
    assert "project.new" in str(exc.value)
    assert [e.path for e in log.entries] == ["a"]  # kept, never dropped


async def test_require_ledger_refuses_when_configured_but_unreachable(
    tmp_path: Path, configured
) -> None:
    log = OutsideWriteLog(tmp_path, produced_by="project.new")
    with _registry_down(), pytest.raises(OutsideWriteLedgerUnavailable) as exc:
        await log.require_ledger()
    assert "refused" in str(exc.value)


async def test_require_ledger_passes_when_reachable(tmp_path: Path, configured) -> None:
    session = MagicMock()
    session.execute = AsyncMock()
    with _session_registry(session):
        await OutsideWriteLog(tmp_path, produced_by="x").require_ledger()
    (sql,) = session.execute.await_args.args
    assert "core.outside_writes" in str(sql)


async def test_standalone_install_neither_requires_nor_records(
    tmp_path: Path, standalone, caplog: pytest.LogCaptureFixture
) -> None:
    """The boundary: no CORE database configured -> no ledger to require; the
    writes proceed and the unrecorded paths are named, never silently."""
    (tmp_path / "a").write_text("1")
    log = OutsideWriteLog(tmp_path, produced_by="project.new")
    with _registry_down():  # any session attempt would raise
        await log.require_ledger()
        log.wrote(tmp_path / "a")
        await log.flush()

    assert "standalone install" in caplog.text
    assert "not recorded" in caplog.text
    assert log.entries == []
