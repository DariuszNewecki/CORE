# tests/body/governance/law_custody/test_record_only.py
"""Record-only law proposals apply without the typed id (governor redesign 2026-10-12).

Record-only: text under .specs/ only, nothing removed, no computed warning,
no refusal. Anything else keeps needing the governor's typed approval.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from body.governance.law_custody.law_warnings import LawWarning
from body.governance.law_custody.proposal import LawProposal, ProposedFile
from body.governance.law_custody.service import PreparedApply, record_only_refusal
from cli.resources.law import app


def _prepared(
    paths: list[str],
    *,
    removals: tuple[str, ...] = (),
    warnings: list[LawWarning] | None = None,
    refusals: list[dict[str, str]] | None = None,
) -> PreparedApply:
    proposal = LawProposal(
        proposal_id="0099-x",
        files=tuple(ProposedFile(path=p, content=b"x", sha256="0") for p in paths),
        removals=removals,
        proposal_md="",
        declared_warnings=(),
        digest="d",
    )
    return PreparedApply(
        proposal=proposal,
        repo_root=Path("."),
        destinations=[],
        old={},
        checks={},
        refusals=refusals or [],
        computed_warnings=warnings or [],
        shown_utc="t",
    )


def test_an_adr_addendum_is_record_only() -> None:
    assert record_only_refusal(_prepared([".specs/decisions/ADR-1.md"])) is None


@pytest.mark.parametrize(
    ("prepared", "why"),
    [
        (_prepared([".intent/rules/x.json"]), ".specs/"),
        (_prepared(["CLAUDE.md", ".specs/decisions/ADR-1.md"]), "CLAUDE.md"),
        (_prepared([".specs/a.md"], removals=(".specs/b.md",)), "removes"),
        (
            _prepared(
                [".specs/a.md"],
                warnings=[
                    LawWarning(category="assistant_contract", path="a", message="m")
                ],
            ),
            "warnings",
        ),
        (_prepared([".specs/a.md"], refusals=[{"check": "schema"}]), "refused"),
    ],
)
def test_anything_else_needs_the_typed_id(prepared: PreparedApply, why: str) -> None:
    reason = record_only_refusal(prepared)
    assert reason is not None and why in reason


def test_auto_apply_runs_only_as_core_law() -> None:
    result = CliRunner().invoke(app, ["auto-apply", "--write"])
    assert result.exit_code == 1
    assert "runs only as core-law" in result.output


def test_digest_separates_automatic_from_typed(tmp_path: Path) -> None:
    import json
    from datetime import UTC, datetime

    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    ledger = tmp_path / ".intent" / "custody" / "ledger.jsonl"
    ledger.parent.mkdir(parents=True)
    lines = [
        {
            "proposal": "0100-a",
            "approver": "auto:record-only",
            "approved_utc": now,
            "paths": {".specs/a.md": "h"},
        },
        {
            "proposal": "0101-b",
            "approver": "darek",
            "approved_utc": now,
            "paths": {".intent/x": "h"},
        },
        {
            "proposal": "0001-old",
            "approver": "darek",
            "approved_utc": "2026-01-01T00:00:00Z",
            "paths": {},
        },
    ]
    ledger.write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    result = CliRunner().invoke(app, ["digest", "--repo", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "Applied automatically (record-only): 1" in result.output
    assert "Approved by you: 1" in result.output
    assert "0001-old" not in result.output


# -- law apply-merge: the post-merge path (one-path flow, 2026-10-12) ----------


def test_apply_merge_runs_only_as_core_law() -> None:
    result = CliRunner().invoke(
        app,
        [
            "apply-merge",
            "merge-abc",
            "--proposals-dir",
            "/x",
            "--merge-commit",
            "a" * 40,
            "--merged-by",
            "darek",
            "--repo",
            "/x",
            "--write",
        ],
    )
    assert result.exit_code == 1
    assert "runs only as core-law" in result.output


def test_apply_merge_refuses_under_sudo_and_a_short_sha(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cli.resources.law.apply as apply_mod

    monkeypatch.setattr(apply_mod, "current_account", lambda: "core-law")
    args = [
        "apply-merge",
        "merge-abc",
        "--proposals-dir",
        "/x",
        "--merged-by",
        "d",
        "--repo",
        "/x",
        "--write",
    ]
    monkeypatch.setenv("SUDO_USER", "darek")
    under_sudo = CliRunner().invoke(app, [*args, "--merge-commit", "a" * 40])
    assert under_sudo.exit_code == 1 and "not through sudo" in under_sudo.output
    monkeypatch.delenv("SUDO_USER")
    short = CliRunner().invoke(app, [*args, "--merge-commit", "abc123"])
    assert short.exit_code == 1 and "full sha" in short.output


def test_apply_merge_records_the_merge_as_the_approver(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import cli.resources.law.apply as apply_mod

    seen: dict = {}
    prepared = _prepared([".intent/rules/x.json"])
    monkeypatch.setattr(apply_mod, "current_account", lambda: "core-law")
    monkeypatch.delenv("SUDO_USER", raising=False)
    monkeypatch.setattr(apply_mod, "prepare", lambda **kw: prepared)
    monkeypatch.setattr(apply_mod, "_render", lambda p: None)

    class _Outcome:
        def ok(self) -> bool:
            return True

    def _apply(p, *, approver, key_path):
        seen["approver"] = approver
        return _Outcome()

    monkeypatch.setattr(apply_mod, "apply_prepared", _apply)
    sha = "b" * 40
    result = CliRunner().invoke(
        app,
        [
            "apply-merge",
            "merge-x",
            "--proposals-dir",
            str(tmp_path),
            "--merge-commit",
            sha,
            "--merged-by",
            "darek",
            "--repo",
            str(tmp_path),
            "--write",
        ],
    )
    assert result.exit_code == 0, result.output
    assert seen["approver"] == f"github-merge {sha} by darek"
