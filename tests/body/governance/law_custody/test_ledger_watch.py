"""LedgerSignatureWatch (#1112): verifies once, again only when the ledger changes.

A throwaway ed25519 key signs the lines exactly as ``law apply`` does; the
durable ledger is a temporary file (``CORE_CUSTODY_LEDGER``).
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from body.governance.law_custody import ledger_watch
from body.governance.law_custody.ledger import (
    CUSTODY_LEDGER_ENV,
    SIGNER_IDENTITY,
    SIGNING_NAMESPACE,
    signed_line_bytes,
)
from body.governance.law_custody.ledger_watch import (
    LedgerSignatureWatch,
    failing_line_findings,
)


@pytest.fixture
def key(tmp_path: Path) -> Path:
    path = tmp_path / "keys" / "ledger"
    path.parent.mkdir()
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(path)], check=True
    )
    return path


@pytest.fixture
def signers(tmp_path: Path, key: Path) -> Path:
    path = tmp_path / "allowed_signers"
    path.write_text(
        f'{SIGNER_IDENTITY} namespaces="{SIGNING_NAMESPACE}" '
        f"{key.with_suffix('.pub').read_text()}"
    )
    return path


@pytest.fixture
def ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "custody" / "ledger.jsonl"
    path.parent.mkdir()
    monkeypatch.setenv(CUSTODY_LEDGER_ENV, str(path))
    return path


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """Counts verify_ledger runs (each one is ssh-keygen per line)."""
    seen: list[Path] = []
    real = ledger_watch.verify_ledger

    def counting(path: Path, allowed: Path):
        seen.append(path)
        return real(path, allowed)

    monkeypatch.setattr(ledger_watch, "verify_ledger", counting)
    return seen


def _line(key: Path, proposal: str) -> str:
    return signed_line_bytes({"proposal": proposal, "approver": "darek"}, key).decode()


def _tamper(raw: str) -> str:
    entry = json.loads(raw)
    entry["approver"] = "someone-else"
    return json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n"


# ID: b291395a-e7b7-42d7-9801-a4be9004498a
def test_rechecks_only_when_the_ledger_changes(
    key: Path, signers: Path, ledger: Path, calls: list[Path]
) -> None:
    ledger.write_text(_line(key, "0001") + _tamper(_line(key, "0002")))
    watch = LedgerSignatureWatch()

    first = watch.check(signers)
    assert first.rechecked and first.checked == 2
    assert [n for n, _ in first.failures] == [2]
    assert len(calls) == 1

    # Unchanged: the last result, no ssh-keygen.
    again = watch.check(signers)
    assert not again.rechecked and again.failures == first.failures
    assert len(calls) == 1

    # Touched (new mtime) but the same bytes: the hash decides, no re-check.
    stat = ledger.stat()
    os.utime(ledger, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
    assert not watch.check(signers).rechecked
    assert len(calls) == 1

    # A new line: re-checked.
    with ledger.open("a") as fh:
        fh.write(_line(key, "0003"))
    after = watch.check(signers)
    assert after.rechecked and after.checked == 3
    assert [n for n, _ in after.failures] == [2]
    assert len(calls) == 2


# ID: c839a569-e18b-4f59-bf21-d33e7c552be1
def test_no_durable_ledger_or_no_signers(
    tmp_path: Path, signers: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(CUSTODY_LEDGER_ENV, str(tmp_path / "absent" / "ledger.jsonl"))
    assert not LedgerSignatureWatch().check(signers).applies

    monkeypatch.setenv(CUSTODY_LEDGER_ENV, str(tmp_path / "ledger.jsonl"))
    state = LedgerSignatureWatch().check(tmp_path / "missing_signers")
    assert state.applies and state.problem and "allowed signers" in state.problem
    assert failing_line_findings(state) == {}
