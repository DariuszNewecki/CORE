"""Law apply: the custodian-only writer, the signed ledger line, prepare/apply.

The custodian is the account running the tests, so the writer's account
tripwire is exercised without a real ``core-law`` account; the refusal for
any other account is tested directly.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from body.governance.law_custody import service
from body.governance.law_custody.ledger import (
    LEDGER_REL,
    SIGNING_NAMESPACE,
    LedgerSignError,
    canonical_bytes,
    count_changed_lines,
)
from body.governance.law_custody.writer import (
    CustodyError,
    current_account,
    require_custodian,
)


ME = current_account()


@pytest.fixture
def key(tmp_path: Path) -> Path:
    path = tmp_path / "keys" / "ledger"
    path.parent.mkdir()
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(path)], check=True
    )
    return path


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / ".intent" / "custody").mkdir(parents=True)
    (repo / ".specs").mkdir()
    (repo / ".specs" / "a.md").write_text("old a\n")
    (repo / ".specs" / "gone.md").write_text("to remove\n")
    (repo / "src").mkdir()
    (repo / "infra").mkdir()
    (repo / ".git").mkdir()
    (repo / ".env").write_text("SECRET=1\n")
    md = (
        "# p\n\n## Declared warnings\n\n- meaning changes\n\n"
        "## Remove\n\n- `.specs/gone.md`\n"
    )
    proposal = repo / "var" / "law-proposals" / "0007-test"
    (proposal / "files" / ".specs").mkdir(parents=True)
    (proposal / "proposal.md").write_text(md)
    (proposal / "files" / ".specs" / "a.md").write_text("new a\n")
    (proposal / "files" / ".specs" / "b.md").write_text("new b\n")
    return repo


def _clean_checks(tree: Path) -> dict[str, Any]:
    assert (tree / ".specs" / "a.md").read_text() == "new a\n"  # batch applied
    assert not (tree / ".specs" / "gone.md").exists()
    assert not (tree / ".specs").is_symlink()  # governed text is copied
    assert (tree / "infra").is_symlink() and (tree / "src").is_symlink()
    for absent in (".git", ".env", "var"):
        assert not (tree / absent).exists()
    return {"refusals": [], "checks": {"law_loads": "ok"}}


def _prepare(
    repo: Path, tmp_path: Path, destinations: list[Path], checks=_clean_checks
):
    return service.prepare(
        repo_root=repo,
        proposals_dir=repo / "var" / "law-proposals",
        proposal_id="0007-test",
        destinations=destinations,
        scratch_parent=tmp_path / "scratch",
        custodian=ME,
        run_checks=checks,
    )


def test_require_custodian(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(CustodyError, match="runs only as core-law"):
        require_custodian({"SUDO_USER": "darek"})
    assert require_custodian({"SUDO_USER": "darek"}, custodian=ME) == "darek"
    with pytest.raises(CustodyError, match="no approver"):
        require_custodian({}, custodian=ME)
    with pytest.raises(CustodyError, match="no approver"):
        require_custodian({"SUDO_USER": ME}, custodian=ME)


def test_apply_writes_both_destinations_and_one_signed_line(
    tmp_path: Path, key: Path
) -> None:
    repo = _repo(tmp_path)
    law = tmp_path / "law"
    (law / ".specs").mkdir(parents=True)
    (law / ".specs" / "a.md").write_text("old a\n")
    (law / ".specs" / "gone.md").write_text("to remove\n")
    prepared = _prepare(repo, tmp_path, [repo, law])
    assert prepared.refusals == []
    assert not list((tmp_path / "scratch").iterdir())  # scratch removed

    outcome = service.apply_prepared(
        prepared, approver="darek", key_path=key, custodian=ME
    )

    assert outcome.ok()
    for root in (repo, law):
        assert (root / ".specs" / "a.md").read_text() == "new a\n"
        assert (root / ".specs" / "b.md").read_text() == "new b\n"
        assert not (root / ".specs" / "gone.md").exists()
        assert (root / LEDGER_REL).read_bytes() == outcome.ledger_line
    line = json.loads(outcome.ledger_line or b"")
    assert line["approver"] == "darek"
    assert line["destinations"] == [str(repo), str(law)]
    assert line["files"] == 3
    assert line["lines_changed"] == 4  # a: -1 +1, b: +1, gone: -1
    assert line["warnings_declared"] == ["meaning changes"]
    assert line["shown_utc"] and line["approved_utc"]

    # The signature verifies against the line without it.
    signature = line.pop("signature")
    (tmp_path / "sig").write_text(signature)
    (tmp_path / "allowed").write_text(
        f'core-law namespaces="{SIGNING_NAMESPACE}" {key.with_suffix(".pub").read_text()}'
    )
    verify = subprocess.run(
        [
            "ssh-keygen",
            "-Y",
            "verify",
            "-f",
            str(tmp_path / "allowed"),
            "-I",
            "core-law",
            "-n",
            SIGNING_NAMESPACE,
            "-s",
            str(tmp_path / "sig"),
        ],
        input=canonical_bytes(line),
        capture_output=True,
        check=False,
    )
    assert verify.returncode == 0, verify.stderr


def test_refusals_write_nothing(tmp_path: Path, key: Path) -> None:
    repo = _repo(tmp_path)
    prepared = _prepare(
        repo,
        tmp_path,
        [repo],
        checks=lambda tree: {
            "refusals": [{"check": "schema", "message": "bad"}],
            "checks": {},
        },
    )
    with pytest.raises(CustodyError, match="refused"):
        service.apply_prepared(prepared, approver="darek", key_path=key, custodian=ME)
    assert (repo / ".specs" / "a.md").read_text() == "old a\n"
    assert not (repo / LEDGER_REL).exists()


def test_changed_after_shown_writes_nothing(tmp_path: Path, key: Path) -> None:
    repo = _repo(tmp_path)
    prepared = _prepare(repo, tmp_path, [repo])
    (repo / ".specs" / "a.md").write_text("someone else\n")
    with pytest.raises(CustodyError, match="changed after"):
        service.apply_prepared(prepared, approver="darek", key_path=key, custodian=ME)
    assert not (repo / ".specs" / "b.md").exists()
    assert not (repo / LEDGER_REL).exists()


def test_missing_key_writes_nothing(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    prepared = _prepare(repo, tmp_path, [repo])
    with pytest.raises(LedgerSignError):
        service.apply_prepared(
            prepared, approver="darek", key_path=tmp_path / "nokey", custodian=ME
        )
    assert (repo / ".specs" / "a.md").read_text() == "old a\n"


def test_failed_second_destination_writes_no_ledger_line(
    tmp_path: Path, key: Path
) -> None:
    repo = _repo(tmp_path)
    missing = tmp_path / "no-such-law"
    prepared = _prepare(repo, tmp_path, [repo, missing])
    outcome = service.apply_prepared(
        prepared, approver="darek", key_path=key, custodian=ME
    )
    assert not outcome.ok()
    assert outcome.outcomes[0].failed is None
    assert (
        outcome.outcomes[1].failed and "not a directory" in outcome.outcomes[1].failed
    )
    assert not (repo / LEDGER_REL).exists()


def test_symlink_in_destination_is_refused(tmp_path: Path, key: Path) -> None:
    repo = _repo(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    law = tmp_path / "law"
    law.mkdir()
    (law / ".specs").symlink_to(outside)
    prepared = _prepare(repo, tmp_path, [law])
    outcome = service.apply_prepared(
        prepared, approver="darek", key_path=key, custodian=ME
    )
    assert outcome.outcomes[0].failed
    assert not list(outside.iterdir())


def test_other_accounts_cannot_write(tmp_path: Path, key: Path) -> None:
    repo = _repo(tmp_path)
    with pytest.raises(CustodyError):
        service.prepare(
            repo_root=repo,
            proposals_dir=repo / "var" / "law-proposals",
            proposal_id="0007-test",
            destinations=[repo],
            scratch_parent=tmp_path / "scratch",
            run_checks=_clean_checks,
        )
    prepared = _prepare(repo, tmp_path, [repo])
    with pytest.raises(CustodyError):
        service.apply_prepared(prepared, approver="darek", key_path=key)
    assert (repo / ".specs" / "a.md").read_text() == "old a\n"


def test_count_changed_lines() -> None:
    assert count_changed_lines(b"a\nb\n", b"a\nc\n") == 2
    assert count_changed_lines(None, b"x\ny\n") == 2
    assert count_changed_lines(b"\xff", b"x") == 0


def test_symlink_inside_destination_is_refused_too(tmp_path: Path, key: Path) -> None:
    # A directory swapped for a link to elsewhere in the same tree still
    # resolves inside it; the writer refuses any symlink on the path.
    repo = _repo(tmp_path)
    law = tmp_path / "law"
    (law / "elsewhere").mkdir(parents=True)
    (law / ".specs").symlink_to(law / "elsewhere")
    prepared = _prepare(repo, tmp_path, [law])
    outcome = service.apply_prepared(
        prepared, approver="darek", key_path=key, custodian=ME
    )
    assert outcome.outcomes[0].failed and "symlink" in outcome.outcomes[0].failed
    assert not list((law / "elsewhere").iterdir())


def test_a_file_in_a_read_only_directory_is_written_in_place(
    tmp_path: Path, key: Path
) -> None:
    # The repository root is root-owned and sticky: core-law owns CLAUDE.md but
    # cannot create files beside it.
    repo = _repo(tmp_path)
    proposal = repo / "var" / "law-proposals" / "0007-test" / "files"
    (proposal / "CLAUDE.md").write_text("new contract\n")
    (repo / "CLAUDE.md").write_text("old contract\n")
    prepared = _prepare(repo, tmp_path, [repo])
    repo.chmod(0o555)
    try:
        outcome = service.apply_prepared(
            prepared, approver="darek", key_path=key, custodian=ME
        )
    finally:
        repo.chmod(0o755)
    assert outcome.ok(), [o.failed for o in outcome.outcomes]
    assert (repo / "CLAUDE.md").read_text() == "new contract\n"
    assert not list(repo.glob(".CLAUDE.md*"))


def test_release_law_receives_only_intent_and_specs(tmp_path: Path, key: Path) -> None:
    """CLAUDE.md is the development tree's alone; release law never holds it."""
    repo = _repo(tmp_path)
    (repo / "CLAUDE.md").write_text("old contract\n")
    proposal = repo / "var" / "law-proposals" / "0007-test" / "files"
    (proposal / "CLAUDE.md").write_text("new contract\n")
    law = tmp_path / "law"
    (law / ".specs").mkdir(parents=True)
    (law / ".intent" / "custody").mkdir(parents=True)
    law.chmod(0o555)  # like /opt/core/law: root-owned, nothing created beside .specs
    try:
        prepared = _prepare(repo, tmp_path, [repo, law])
        outcome = service.apply_prepared(
            prepared, approver="darek", key_path=key, custodian=ME
        )
    finally:
        law.chmod(0o755)

    assert outcome.ok(), [o.failed for o in outcome.outcomes]
    assert (repo / "CLAUDE.md").read_text() == "new contract\n"
    assert not (law / "CLAUDE.md").exists()
    assert (law / ".specs" / "b.md").read_text() == "new b\n"
    assert "CLAUDE.md" in outcome.outcomes[0].written
    assert "CLAUDE.md" not in outcome.outcomes[1].written
