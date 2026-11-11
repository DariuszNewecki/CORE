"""`core-admin record check` (#1328 step 6): the workshop pair and the exit codes.

Fixtures in tests/fixtures/records/ are made up.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from cli.resources.record import app as record_app


FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "records"
RUNNER = CliRunner()
ROOT = typer.Typer()
ROOT.add_typer(record_app, name="record")


def _run(*args: str):
    return RUNNER.invoke(ROOT, ["record", "check", *args])


def test_pass_text_exit_0() -> None:
    result = _run(
        str(FIXTURES / "workshop_pass.json"), "--catalog", "publication_rules"
    )
    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    assert lines[0] == "Verdict: pass (proven)"
    assert lines[1] == (
        "Proven against the facts in this record; it does not vouch that they are true."
    )
    assert "Catalog: publication_rules (10 rules)" in result.output
    assert "Findings: none" in result.output
    assert result.output.count("pass       proven") == 10


def test_missing_level_text_exit_1_with_the_one_authority_finding() -> None:
    result = _run(
        str(FIXTURES / "workshop_missing_level.json"), "--catalog", "publication_rules"
    )
    assert result.exit_code == 1, result.output
    assert "Verdict: fail (proven)" in result.output
    assert "publication.authority" in result.output.split("Findings:")[1]
    assert (
        "    DRT-21 (blocking): a decision_right needs exactly one level ref, has 0"
        in result.output
    )
    assert result.output.count("(blocking)") == 1


def test_json_is_the_full_verdict() -> None:
    result = _run(
        str(FIXTURES / "workshop_missing_level.json"),
        "--catalog",
        "publication_rules",
        "--format",
        "json",
    )
    assert result.exit_code == 1, result.output
    data = json.loads(result.stdout)
    assert data["format"] == "record-verdict/1"
    assert (data["outcome"], data["evidence_class"]) == ("fail", "proven")
    assert len(data["record_sha256"]) == 64
    assert len(data["parts"]) == 10
    findings = [f for p in data["parts"] for f in p["findings"]]
    assert [(f["rule"], f["item"], f["blocking"]) for f in findings] == [
        ("publication.authority", "DRT-21", True)
    ]

    passing = _run(
        str(FIXTURES / "workshop_pass.json"),
        "--catalog",
        "publication_rules",
        "--format",
        "json",
    )
    assert passing.exit_code == 0
    assert json.loads(passing.stdout)["outcome"] == "pass"


def test_dressing_only_exit_2() -> None:
    result = _run(
        str(FIXTURES / "dressing_only.json"), "--catalog", "publication_rules"
    )
    assert result.exit_code == 2, result.output
    assert "Verdict: undecided (proven)" in result.output
    assert (
        "DOC-21 (not blocking): dressing paragraph 1 uses normative word(s): shall"
        in result.output
    )


def test_attested_verdict_says_core_did_not_settle_it(tmp_path: Path) -> None:
    record = json.loads((FIXTURES / "workshop_pass.json").read_text(encoding="utf-8"))
    record["pre_findings"] = [
        {
            "item": "DRT-21",
            "rule": "sign_off",
            "message": "awaits sign-off",
            "blocking": False,
        }
    ]
    path = tmp_path / "record.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    result = _run(str(path), "--catalog", "publication_rules")
    assert result.exit_code == 2, result.output
    lines = result.output.splitlines()
    assert lines[0] == "Verdict: undecided (attested)"
    assert lines[1].startswith("Not settled by CORE: a human must decide")


@pytest.mark.parametrize(
    ("content", "catalog"),
    [
        ("not json", "publication_rules"),
        ("[1, 2]", "publication_rules"),
        ('{"format": "other/1", "items": {}}', "publication_rules"),
        (None, "publication_rules"),  # no such file
        ('{"format": "library-snapshot/1", "items": {}}', "no_such_catalog"),
    ],
)
def test_bad_input_exit_3(tmp_path: Path, content: str | None, catalog: str) -> None:
    path = tmp_path / "record.json"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    result = _run(str(path), "--catalog", catalog)
    assert result.exit_code == 3, result.output
    assert "could not run" in result.output


def test_bad_format_option_exit_3() -> None:
    result = _run(
        str(FIXTURES / "workshop_pass.json"),
        "--catalog",
        "publication_rules",
        "--format",
        "xml",
    )
    assert result.exit_code == 3


def test_usage_error_exits_3_not_2() -> None:
    assert _run(str(FIXTURES / "workshop_pass.json")).exit_code == 3  # no --catalog
    assert _run("--catalog", "publication_rules").exit_code == 3  # no record


def test_help_states_the_exit_codes() -> None:
    result = RUNNER.invoke(ROOT, ["record", "check", "--help"])
    assert result.exit_code == 0
    for text in ("0 pass", "1 fail", "2 undecided", "3 the"):
        assert text in result.output
