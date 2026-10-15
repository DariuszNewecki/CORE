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
    # The directory is not writable: core-law owns .claude/settings.json but
    # cannot create files beside it.
    repo = _repo(tmp_path)
    proposal = repo / "var" / "law-proposals" / "0007-test" / "files"
    (proposal / ".claude").mkdir()
    (proposal / ".claude" / "settings.json").write_text('{"new": 1}\n')
    (repo / ".claude").mkdir()
    (repo / ".claude" / "settings.json").write_text('{"old": 1}\n')
    prepared = _prepare(repo, tmp_path, [repo])
    (repo / ".claude").chmod(0o555)
    try:
        outcome = service.apply_prepared(
            prepared, approver="darek", key_path=key, custodian=ME
        )
    finally:
        (repo / ".claude").chmod(0o755)
    assert outcome.ok(), [o.failed for o in outcome.outcomes]
    assert (repo / ".claude" / "settings.json").read_text() == '{"new": 1}\n'
    assert not list((repo / ".claude").glob(".settings.json*"))


def test_release_law_receives_only_intent_and_specs(tmp_path: Path, key: Path) -> None:
    """Release law never holds .claude/settings.json; only the dev tree does."""
    repo = _repo(tmp_path)
    (repo / ".claude").mkdir()
    (repo / ".claude" / "settings.json").write_text('{"old": 1}\n')
    proposal = repo / "var" / "law-proposals" / "0007-test" / "files"
    (proposal / ".claude").mkdir()
    (proposal / ".claude" / "settings.json").write_text('{"new": 1}\n')
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
    assert (repo / ".claude" / "settings.json").read_text() == '{"new": 1}\n'
    assert not (law / ".claude").exists()
    assert (law / ".specs" / "b.md").read_text() == "new b\n"
    assert ".claude/settings.json" in outcome.outcomes[0].written
    assert ".claude/settings.json" not in outcome.outcomes[1].written


def test_durable_ledger_takes_the_line_and_no_working_tree_does(
    tmp_path: Path, key: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With the host's durable ledger present, the signed line is appended
    there only: a deploy must not leave records in the development tree or
    the release law, where a checkout reset or a law resync drops them."""
    from body.governance.law_custody.ledger import (
        CUSTODY_LEDGER_ENV,
        durable_ledger,
        ledger_file,
    )

    custody = tmp_path / "custody"
    custody.mkdir()
    durable = custody / "ledger.jsonl"
    durable.write_bytes(b'{"earlier": "record"}\n')
    monkeypatch.setenv(CUSTODY_LEDGER_ENV, str(durable))
    repo = _repo(tmp_path)
    law = tmp_path / "law"
    (law / ".specs").mkdir(parents=True)
    (law / ".specs" / "a.md").write_text("old a\n")
    (law / ".specs" / "gone.md").write_text("to remove\n")

    outcome = service.apply_prepared(
        _prepare(repo, tmp_path, [repo, law]),
        approver="darek",
        key_path=key,
        custodian=ME,
    )

    assert outcome.ok()
    assert durable.read_bytes() == b'{"earlier": "record"}\n' + outcome.ledger_line
    for root in (repo, law):
        assert (root / ".specs" / "b.md").read_text() == "new b\n"
        assert not (root / LEDGER_REL).exists()
    assert durable_ledger() == durable
    assert ledger_file(repo) == durable


def test_without_a_durable_ledger_the_repository_ledger_is_read(tmp_path: Path) -> None:
    from body.governance.law_custody.ledger import durable_ledger, ledger_file

    assert durable_ledger() is None  # conftest points at a missing directory
    assert ledger_file(tmp_path) == tmp_path / LEDGER_REL


def _module_checks(tree: Path) -> dict[str, Any]:
    """The reference gate's question, asked of the scratch tree's src/."""
    if (tree / "src" / "will" / "workers" / "new_sensor.py").exists():
        return {"refusals": [], "checks": {"references": "ok"}}
    message = (
        "implementation.module 'will.workers.new_sensor' is not a module under src/"
    )
    return {"refusals": [{"check": "references", "message": message}], "checks": {}}


def _code_tree(tmp_path: Path) -> Path:
    """The merge commit's code: it has the module the dev tree lacks."""
    code = tmp_path / "code"
    (code / "src" / "will" / "workers").mkdir(parents=True)
    (code / "src" / "will" / "workers" / "new_sensor.py").write_text("X = 1\n")
    (code / ".specs").mkdir()
    (code / ".specs" / "a.md").write_text("code tree's copy, never used\n")
    return code


def test_law_is_checked_against_the_code_tree_when_given(tmp_path: Path) -> None:
    """2026-10-13: 354d17fd's worker law was refused because its module was
    looked up in the lagging development checkout, not in 354d17fd."""
    repo = _repo(tmp_path)
    refused = _prepare(repo, tmp_path, [repo], checks=_module_checks)
    assert "not a module under src/" in refused.refusals[0]["message"]

    code = _code_tree(tmp_path)
    seen: dict[str, Path] = {}

    def checks(tree: Path) -> dict[str, Any]:
        seen["src"] = (tree / "src").resolve()
        seen["specs_a"] = tree / ".specs" / "a.md"
        assert (tree / ".specs" / "a.md").read_text() == "new a\n"  # proposal
        assert (tree / ".specs" / "gone.md").exists() is False
        return _module_checks(tree)

    accepted = service.prepare(
        repo_root=repo,
        proposals_dir=repo / "var" / "law-proposals",
        proposal_id="0007-test",
        destinations=[repo],
        scratch_parent=tmp_path / "scratch",
        custodian=ME,
        run_checks=checks,
        code_tree=code,
    )
    assert accepted.refusals == []
    assert seen["src"] == (code / "src").resolve()
    assert accepted.old[".specs/a.md"] == b"old a\n"  # current law: the dev tree


def test_governed_text_comes_from_the_dev_tree_not_the_code_tree(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    (repo / ".intent" / "custody" / "dev.txt").write_text("dev law\n")
    code = _code_tree(tmp_path)
    (code / ".intent").mkdir()

    def checks(tree: Path) -> dict[str, Any]:
        assert (tree / ".intent" / "custody" / "dev.txt").read_text() == "dev law\n"
        assert not (tree / ".intent").is_symlink()
        assert (tree / "src").resolve() == (code / "src").resolve()
        assert not (tree / "infra").exists()  # only the code tree's entries
        return {"refusals": [], "checks": {}}

    service.prepare(
        repo_root=repo,
        proposals_dir=repo / "var" / "law-proposals",
        proposal_id="0007-test",
        destinations=[repo],
        scratch_parent=tmp_path / "scratch",
        custodian=ME,
        run_checks=checks,
        code_tree=code,
    )


@pytest.mark.parametrize("bad", ["relative/code", "missing", "a-file"])
def test_a_code_tree_that_is_not_an_absolute_directory_is_refused(
    tmp_path: Path, bad: str
) -> None:
    repo = _repo(tmp_path)
    (tmp_path / "a-file").write_text("x\n")
    code = Path(bad) if bad.startswith("relative") else tmp_path / bad
    with pytest.raises(CustodyError, match="absolute existing directory"):
        service.prepare(
            repo_root=repo,
            proposals_dir=repo / "var" / "law-proposals",
            proposal_id="0007-test",
            destinations=[repo],
            scratch_parent=tmp_path / "scratch",
            custodian=ME,
            run_checks=_clean_checks,
            code_tree=code,
        )


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def test_a_rerun_after_a_failed_write_compares_with_the_committed_law(
    tmp_path: Path, key: Path
) -> None:
    """#966 (law 0025): the failed first attempt left the new bytes in the
    dev tree and wrote no ledger line; the rerun read them as current and
    recorded lines_changed 0 and no computed warnings."""
    repo = _repo(tmp_path)
    (repo / ".git").rmdir()
    _git(repo, "init", "-q")
    _git(repo, "add", ".specs")
    _git(repo, "commit", "-qm", "law of record")
    missing = tmp_path / "no-such-law"

    first = service.apply_prepared(
        _prepare(repo, tmp_path, [repo, missing]),
        approver="darek",
        key_path=key,
        custodian=ME,
    )
    assert not first.ok()  # repo written, second destination failed, no ledger line
    assert (repo / ".specs" / "a.md").read_text() == "new a\n"

    rerun = _prepare(repo, tmp_path, [repo])
    leftovers = [
        w for w in rerun.computed_warnings if w.category == "unrecorded_prior_write"
    ]
    assert {w.path for w in leftovers} == {
        ".specs/a.md",
        ".specs/b.md",
        ".specs/gone.md",
    }
    outcome = service.apply_prepared(
        rerun, approver="darek", key_path=key, custodian=ME
    )
    assert outcome.ok()
    line = json.loads(outcome.ledger_line)
    # a.md: old a -> new a (2 lines), b.md new (1), gone.md removed (1)
    assert line["lines_changed"] == 4
    assert {w["category"] for w in line["warnings_computed"]} >= {
        "unrecorded_prior_write"
    }


def test_a_recorded_identical_apply_is_not_a_leftover(
    tmp_path: Path, key: Path
) -> None:
    repo = _repo(tmp_path)
    first = service.apply_prepared(
        _prepare(repo, tmp_path, [repo]), approver="darek", key_path=key, custodian=ME
    )
    assert first.ok()
    (repo / ".specs" / "gone.md").write_text("to remove\n")  # let it apply again
    again = _prepare(repo, tmp_path, [repo])
    assert not [
        w for w in again.computed_warnings if w.category == "unrecorded_prior_write"
    ]
