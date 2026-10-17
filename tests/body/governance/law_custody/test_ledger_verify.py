"""Ledger signature verification (#1112): a signed line verifies, a tampered one
does not, and ``core-admin law verify`` lists the failing lines and exits 1.

A throwaway ed25519 key stands in for core-law's: it signs with
``signed_line_bytes`` exactly as ``law apply`` does, and the allowed signers
file names it for ``core-law`` in the ledger namespace.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from body.governance.law_custody.ledger import (
    SIGNER_IDENTITY,
    SIGNING_NAMESPACE,
    signed_line_bytes,
    verify_ledger,
    verify_line,
)
from cli.resources.law import app


_LINE = {
    "proposal": "0001-test",
    "approver": "darek",
    "approved_utc": "2026-10-17T00:00:00Z",
    "paths": {".intent/rules/x.json": "ab" * 32},
}


@pytest.fixture
def key(tmp_path: Path) -> Path:
    path = tmp_path / "keys" / "ledger"
    path.parent.mkdir()
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(path)], check=True
    )
    return path


@pytest.fixture
def allowed(tmp_path: Path, key: Path) -> Path:
    path = tmp_path / "allowed_signers"
    path.write_text(
        f'{SIGNER_IDENTITY} namespaces="{SIGNING_NAMESPACE}" '
        f"{key.with_suffix('.pub').read_text()}"
    )
    return path


def _signed(key: Path, line: dict = _LINE) -> str:
    return signed_line_bytes(line, key).decode("ascii").rstrip("\n")


def _tampered(raw: str) -> str:
    entry = json.loads(raw)
    entry["approver"] = "someone-else"
    return json.dumps(entry, sort_keys=True, separators=(",", ":"))


# ID: ad887054-7d64-45d0-a1c2-df52587be5fc
def test_a_signed_line_verifies(key: Path, allowed: Path) -> None:
    assert verify_line(_signed(key), allowed) is None


# ID: 7a72d4c8-ce3c-4fad-a5ad-b8762e623d45
def test_a_tampered_or_unsigned_line_does_not_verify(
    key: Path, allowed: Path, tmp_path: Path
) -> None:
    raw = _signed(key)
    assert verify_line(_tampered(raw), allowed) is not None
    unsigned = json.dumps(_LINE)
    assert verify_line(unsigned, allowed) == "no signature"
    assert verify_line("{not json", allowed).startswith("not JSON")

    # Signed by a key that is not in allowed_signers.
    other = tmp_path / "other"
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(other)], check=True
    )
    assert verify_line(_signed(other), allowed) is not None


# ID: e827be85-625c-4470-a1c3-29d20ad6e40d
def test_law_verify_lists_failing_lines_and_exits_1(
    key: Path, allowed: Path, tmp_path: Path
) -> None:
    good = _signed(key)
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(f"{good}\n{_tampered(good)}\n\n{good}\n")

    checked, failures = verify_ledger(ledger, allowed)
    assert checked == 3
    assert [n for n, _ in failures] == [2]

    args = ["verify", "--ledger", str(ledger), "--allowed-signers", str(allowed)]
    result = CliRunner().invoke(app, [*args, "--json"])
    assert result.exit_code == 1
    report = json.loads(result.output.strip().splitlines()[-1])
    assert report["checked"] == 3
    assert [f["line"] for f in report["failed"]] == [2]

    ledger.write_text(f"{good}\n{good}\n")
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    assert "2 line(s) checked, 0 failed" in result.output
