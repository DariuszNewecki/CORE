"""ADR-169 D5: every write CORE makes outside its repository is recorded --
target, relative path, operation, sha256, producer; never the content. A
ledger that cannot be reached is reported, never raised."""

from __future__ import annotations

import hashlib
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from body.services.outside_write_ledger import OutsideWrite, OutsideWriteLog


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


async def test_flush_inserts_every_entry_once(tmp_path: Path) -> None:
    (tmp_path / "a").write_text("1")
    (tmp_path / "b").write_text("2")
    log = OutsideWriteLog(tmp_path, produced_by="project.new")
    log.wrote(tmp_path / "a")
    log.wrote(tmp_path / "b")
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()

    with _session_registry(session):
        assert await log.flush() is True

    sql, rows = session.execute.await_args.args
    assert "INSERT INTO core.outside_writes" in str(sql)
    assert [r["path"] for r in rows] == ["a", "b"]
    assert {r["produced_by"] for r in rows} == {"project.new"}
    assert rows[0]["target_root"] == tmp_path.resolve().as_posix()
    assert "content" not in rows[0]
    session.commit.assert_awaited_once()
    assert log.entries == []


async def test_flush_with_nothing_is_a_no_op(tmp_path: Path) -> None:
    assert await OutsideWriteLog(tmp_path, produced_by="x").flush() is True


async def test_unreachable_ledger_is_logged_not_raised(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (tmp_path / "a").write_text("1")
    log = OutsideWriteLog(tmp_path, produced_by="project.new")
    log.wrote(tmp_path / "a")

    @asynccontextmanager
    async def _down():
        raise ConnectionError("no database")
        yield  # pragma: no cover

    with patch("body.services.service_registry.ServiceRegistry.session", _down):
        assert await log.flush() is False

    assert "NOT recorded" in caplog.text
    assert "a" in caplog.text
