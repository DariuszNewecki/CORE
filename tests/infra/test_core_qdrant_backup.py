# tests/infra/test_core_qdrant_backup.py
"""core-qdrant-backup: nightly Qdrant snapshots and their restore (#1081).

The real script runs against a fake Qdrant (an HTTP server in a thread that
speaks the few REST calls the script uses). These tests prove the rules: every
collection is snapshotted, checked against the server's sha256 and deleted from
the server again; a failed run keeps every older backup and is never counted as
one; retention keeps the newest N complete runs; restore uploads each snapshot
and fails when a count differs or a collection would be overwritten.
"""

from __future__ import annotations

import datetime
import hashlib
import importlib.machinery
import importlib.util
import json
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import ModuleType
from urllib.parse import parse_qs, unquote, urlsplit

import pytest


REPO = Path(__file__).resolve().parents[2]


def _load(name: str, path: Path) -> ModuleType:
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    loader.exec_module(module)
    return module


qb = _load("core_qdrant_backup", REPO / "infra" / "scripts" / "core-qdrant-backup")

NOW = datetime.datetime(2026, 10, 23, 2, 0, 0, tzinfo=datetime.UTC)


class FakeQdrant:
    """State of the fake server: collections (name -> points) and snapshots."""

    def __init__(self, collections: dict[str, int]) -> None:
        self.collections = dict(collections)
        self.snapshots: dict[str, dict[str, bytes]] = {}
        self.bad_checksum: set[str] = set()
        self.restore_points: dict[str, int] = {}
        self.uploads: list[tuple[str, bytes, dict]] = []
        self.calls: list[str] = []

    def body_for(self, name: str) -> bytes:
        return f"snapshot of {name} with {self.collections[name]} points".encode()


def _handler(state: FakeQdrant):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args) -> None:
            pass

        def _send(self, status: int, payload: object = None, raw: bytes | None = None):
            data = raw if raw is not None else json.dumps({"result": payload}).encode()
            self.send_response(status)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _route(self, method: str) -> None:
            url = urlsplit(self.path)
            parts = [unquote(p) for p in url.path.strip("/").split("/")]
            query = parse_qs(url.query)
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else b""
            state.calls.append(f"{method} {url.path}")
            if parts == ["collections"] and method == "GET":
                names = [{"name": n} for n in state.collections]
                return self._send(200, {"collections": names})
            name = parts[1]
            rest = parts[2:]
            if rest == ["points", "count"]:
                if name not in state.collections:
                    return self._send(404, raw=b'{"status":"not found"}')
                return self._send(200, {"count": state.collections[name]})
            if rest == ["snapshots"] and method == "POST":
                data = state.body_for(name)
                snap = f"{name}-1.snapshot"
                state.snapshots.setdefault(name, {})[snap] = data
                checksum = hashlib.sha256(data).hexdigest()
                if name in state.bad_checksum:
                    checksum = "0" * 64
                return self._send(
                    200, {"name": snap, "size": len(data), "checksum": checksum}
                )
            if rest == ["snapshots", "upload"] and method == "POST":
                state.uploads.append((name, body, query))
                state.collections[name] = state.restore_points.get(name, 0)
                return self._send(200, True)
            if len(rest) == 2 and rest[0] == "snapshots":
                snaps = state.snapshots.get(name, {})
                if rest[1] not in snaps:
                    return self._send(404, raw=b'{"status":"not found"}')
                if method == "GET":
                    return self._send(200, raw=snaps[rest[1]])
                if method == "DELETE":
                    del snaps[rest[1]]
                    return self._send(200, True)
            return self._send(400, raw=b'{"status":"bad route"}')

        def do_GET(self) -> None:
            self._route("GET")

        def do_POST(self) -> None:
            self._route("POST")

        def do_DELETE(self) -> None:
            self._route("DELETE")

    return Handler


@pytest.fixture
def server():
    started: list[ThreadingHTTPServer] = []

    def start(collections: dict[str, int]) -> tuple[FakeQdrant, str]:
        state = FakeQdrant(collections)
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), _handler(state))
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        started.append(httpd)
        return state, f"http://127.0.0.1:{httpd.server_address[1]}"

    yield start
    for httpd in started:
        httpd.shutdown()
        httpd.server_close()


def _backup(url: str, backup_dir: Path, keep: int = 7, now=NOW) -> int:
    return qb.backup(qb.Qdrant(url), backup_dir, keep, now)


def test_backup_snapshots_every_collection_and_cleans_the_server(server, tmp_path):
    state, url = server({"core-code": 5, "governance_claims": 2})
    assert _backup(url, tmp_path) == 0
    run = tmp_path / "20261023T020000Z"
    manifest = json.loads((run / "manifest.json").read_text())
    got = {e["collection"]: e for e in manifest["collections"]}
    assert set(got) == {"core-code", "governance_claims"}
    for name, entry in got.items():
        data = (run / entry["file"]).read_bytes()
        assert data == state.body_for(name)
        assert entry["sha256"] == hashlib.sha256(data).hexdigest()
        assert (
            entry["points_before"] == entry["points_after"] == state.collections[name]
        )
    assert all(not snaps for snaps in state.snapshots.values())
    assert not list(tmp_path.glob(".partial-*"))


def test_a_checksum_mismatch_fails_the_run_and_keeps_older_backups(server, tmp_path):
    state, url = server({"core-code": 5, "core-docs": 3})
    assert _backup(url, tmp_path, now=NOW - datetime.timedelta(days=1)) == 0
    state.bad_checksum.add("core-docs")
    assert _backup(url, tmp_path, keep=1) == 1
    assert [p.name for p in qb.complete_runs(tmp_path)] == ["20261022T020000Z"]
    assert (tmp_path / ".partial-20261023T020000Z").is_dir()
    # the server's snapshot is deleted even when the download is refused
    assert all(not snaps for snaps in state.snapshots.values())


def test_retention_keeps_the_newest_complete_runs(server, tmp_path):
    _, url = server({"core-code": 1})
    for day in range(4):
        assert (
            _backup(url, tmp_path, keep=2, now=NOW + datetime.timedelta(days=day)) == 0
        )
    assert [p.name for p in qb.complete_runs(tmp_path)] == [
        "20261025T020000Z",
        "20261026T020000Z",
    ]


def test_prune_never_deletes_the_last_run_and_drops_old_partials(tmp_path):
    for name in ("20261020T020000Z", "20261021T020000Z"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "manifest.json").write_text("{}")
    (tmp_path / ".partial-20261019T020000Z").mkdir()
    (tmp_path / "20261019T020000Z").mkdir()  # no manifest: not a run, left alone
    (tmp_path / "notes").mkdir()
    qb.prune(tmp_path, keep=0)
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "20261019T020000Z",
        "20261021T020000Z",
        "notes",
    ]


def test_restore_uploads_each_snapshot_and_compares_counts(server, tmp_path, capsys):
    _, src = server({"core-code": 5, "core-docs": 3})
    assert _backup(src, tmp_path) == 0
    target, dst = server({})
    target.restore_points = {"core-code": 5, "core-docs": 3}
    run = tmp_path / "20261023T020000Z"
    assert qb.restore(qb.Qdrant(dst), run, replace=False, only=None) == 0
    names = [u[0] for u in target.uploads]
    assert names == ["core-code", "core-docs"]
    _name, body, query = target.uploads[0]
    assert query["priority"] == ["snapshot"]
    data = (run / "core-code.snapshot").read_bytes()
    assert query["checksum"] == [hashlib.sha256(data).hexdigest()]
    boundary = re.search(rb"^--(\w+)\r\n", body).group(1)
    assert b'name="snapshot"' in body
    assert body.endswith(b"\r\n--" + boundary + b"--\r\n")
    assert data in body
    assert "2/2 ok" in capsys.readouterr().out


def test_restore_fails_when_a_count_differs(server, tmp_path, capsys):
    _, src = server({"core-code": 5})
    assert _backup(src, tmp_path) == 0
    target, dst = server({})
    target.restore_points = {"core-code": 4}
    run = tmp_path / "20261023T020000Z"
    assert qb.restore(qb.Qdrant(dst), run, replace=False, only=None) == 1
    assert "DIFFERS" in capsys.readouterr().out


def test_restore_refuses_an_existing_collection_without_replace(server, tmp_path):
    _, src = server({"core-code": 5})
    assert _backup(src, tmp_path) == 0
    target, dst = server({"core-code": 9})
    run = tmp_path / "20261023T020000Z"
    assert qb.restore(qb.Qdrant(dst), run, replace=False, only=None) == 1
    assert target.uploads == []
    target.restore_points = {"core-code": 5}
    assert qb.restore(qb.Qdrant(dst), run, replace=True, only=None) == 0


def test_restore_refuses_a_tampered_file(server, tmp_path):
    _, src = server({"core-code": 5})
    assert _backup(src, tmp_path) == 0
    run = tmp_path / "20261023T020000Z"
    (run / "core-code.snapshot").write_bytes(b"tampered")
    target, dst = server({})
    assert qb.restore(qb.Qdrant(dst), run, replace=False, only=None) == 1
    assert target.uploads == []


def test_main_backup_uses_qdrant_url_from_the_environment(
    server, tmp_path, monkeypatch
):
    _, url = server({"core-code": 1})
    monkeypatch.setenv("QDRANT_URL", url)
    assert qb.main(["backup", "--dir", str(tmp_path)]) == 0
    assert len(qb.complete_runs(tmp_path)) == 1


def test_main_reports_an_unreachable_server(tmp_path):
    assert (
        qb.main(["backup", "--url", "http://127.0.0.1:9", "--dir", str(tmp_path)]) == 1
    )
