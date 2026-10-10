"""ADR-168 D2 law & facts: provenance-bearing answers, honest about limits.

Runs against a small adopter-shaped repository built from the bundled machinery
floor, plus one rule and its mapping, so it proves the answers for a project
other than CORE.
"""

from __future__ import annotations

import importlib.resources
import json
import shutil
from pathlib import Path

import pytest

from shared.infrastructure.assistant_surface.law_facts import (
    DECISION_HISTORY,
    LAW,
    UNKNOWN,
    LawFacts,
)


_RULE_ID = "governance.constitution.read_only"


def _floor() -> Path:
    return Path(str(importlib.resources.files("shared._machinery_floor")))


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    intent = tmp_path / ".intent"
    shutil.copytree(
        _floor(), intent, ignore=shutil.ignore_patterns("__pycache__", "__init__.py")
    )
    rules = intent / "rules" / "architecture"
    rules.mkdir(parents=True, exist_ok=True)
    (rules / "safety.json").write_text(
        json.dumps(
            {
                "kind": "rules",
                "metadata": {"id": "architecture.safety"},
                "rules": [
                    {
                        "id": _RULE_ID,
                        "statement": ".intent/** MUST be treated as immutable.",
                        "enforcement": "blocking",
                        "authority": "policy",
                        "phase": "runtime",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    mappings = intent / "enforcement" / "mappings" / "architecture"
    mappings.mkdir(parents=True, exist_ok=True)
    (mappings / "safety.yaml").write_text(
        f"mappings:\n  {_RULE_ID}:\n    engine: passive_gate\n    params:\n"
        "      enforced_by: body.governance.intent_guard.IntentGuard\n"
        "      enforcement_note: Tier-1 invariant.\n",
        encoding="utf-8",
    )
    adrs = tmp_path / ".specs" / "decisions"
    adrs.mkdir(parents=True)
    (adrs / "ADR-007-example.md").write_text(
        "---\nkind: adr\nid: ADR-007\ntitle: 'ADR-007 — Example'\nstatus: accepted\n---\n\n"
        "# ADR-007\n\n### D1 — First decision\n\n### D2 — Second decision\n",
        encoding="utf-8",
    )
    (adrs / "ADR-008-draft.md").write_text(
        "---\nkind: adr\nid: ADR-008\ntitle: 'ADR-008 — Draft'\nstatus: draft\n---\n",
        encoding="utf-8",
    )
    return tmp_path


def test_can_write_intent_answers_law_and_enforcement_separately(repo: Path) -> None:
    """The canonical question. 'Forbidden' alone would overstate CORE's power:
    an external assistant editing the tree is detected, not prevented."""
    answer = LawFacts(repo).can_write(".intent/rules/x.json").as_dict()
    assert answer["class"] == LAW
    body = answer["answer"]
    assert body["law"] == "forbidden"
    assert [r["rule_id"] for r in body["rules"]] == [_RULE_ID]
    assert "IntentGuard" in body["core_write_path"]
    assert body["external_producer"].startswith("Not prevented by CORE")
    assert "DEGRADED" in body["external_producer"]
    paths = {s["path"] for s in answer["sources"]}
    assert ".intent/rules/architecture/safety.json" in paths
    assert ".intent/enforcement/mappings/architecture/safety.yaml" in paths
    assert any("audit_verdict.yaml" in p for p in paths)
    assert answer["limits"] and "cannot observe" in answer["limits"][0]


def test_can_write_intent_without_a_declaring_rule_says_so(tmp_path: Path) -> None:
    """A floor-only project declares no rule; the answer must not invent one."""
    shutil.copytree(
        _floor(),
        tmp_path / ".intent",
        ignore=shutil.ignore_patterns("__pycache__", "__init__.py"),
    )
    body = LawFacts(tmp_path).can_write(".intent/x.yaml").as_dict()["answer"]
    assert body["law"] == "no rule in this repository's law forbids it"
    assert body["rules"] == []


def test_can_write_elsewhere_does_not_claim_permission(repo: Path) -> None:
    answer = LawFacts(repo).can_write("src/app.py").as_dict()
    assert answer["answer"]["law"] == "no location-based prohibition found"
    assert "verdict" in answer["limits"][0]


@pytest.mark.parametrize("path", ["../outside.txt", "/etc/passwd"])
def test_can_write_outside_the_repository_is_unknown(repo: Path, path: str) -> None:
    answer = LawFacts(repo).can_write(path).as_dict()
    assert answer["class"] == UNKNOWN
    assert answer["sources"] == []


def test_rule_returns_statement_mechanism_and_both_sources(repo: Path) -> None:
    answer = LawFacts(repo).rule(_RULE_ID).as_dict()
    assert answer["class"] == LAW
    assert answer["answer"]["statement"] == ".intent/** MUST be treated as immutable."
    assert answer["answer"]["mechanism"]["enforced_by"].endswith("IntentGuard")
    assert [s["path"] for s in answer["sources"]] == [
        ".intent/rules/architecture/safety.json",
        ".intent/enforcement/mappings/architecture/safety.yaml",
    ]


def test_undeclared_rule_is_unknown_not_invented(repo: Path) -> None:
    answer = LawFacts(repo).rule("no.such.rule").as_dict()
    assert answer["class"] == UNKNOWN
    assert answer["answer"]["declared"] is False


@pytest.mark.parametrize("ref", ["ADR-007", "7", "adr-007"])
def test_adr_by_id(repo: Path, ref: str) -> None:
    answer = LawFacts(repo).adr(ref).as_dict()
    assert answer["class"] == DECISION_HISTORY
    assert answer["answer"]["status"] == "accepted"
    assert answer["answer"]["decisions"] == [
        "D1 — First decision",
        "D2 — Second decision",
    ]
    assert answer["sources"][0]["path"] == ".specs/decisions/ADR-007-example.md"


def test_missing_adr_is_unknown(repo: Path) -> None:
    assert LawFacts(repo).adr("ADR-999").as_dict()["class"] == UNKNOWN


def test_adrs_filter_by_status(repo: Path) -> None:
    body = LawFacts(repo).adrs("accepted").as_dict()["answer"]
    assert [a["id"] for a in body["adrs"]] == ["ADR-007"]
    assert LawFacts(repo).adrs().as_dict()["answer"]["count"] == 2


def test_project_without_specs_has_no_decision_history(tmp_path: Path) -> None:
    shutil.copytree(
        _floor(),
        tmp_path / ".intent",
        ignore=shutil.ignore_patterns("__pycache__", "__init__.py"),
    )
    assert LawFacts(tmp_path).adrs().as_dict()["class"] == UNKNOWN


# ID: ad325300-013f-4ed6-87e9-4383653e01a4
def test_decisions_mentioning_by_path_or_module(repo: Path) -> None:
    (repo / ".specs" / "decisions" / "ADR-009-mentions.md").write_text(
        "---\nkind: adr\nid: ADR-009\ntitle: 'ADR-009 — Mentions'\nstatus: superseded\n---\n\n"
        "Touches `will.autonomy.proposal` and docs/guide.md.\n",
        encoding="utf-8",
    )
    answer = (
        LawFacts(repo)
        .decisions_mentioning(
            ["src/will/autonomy/proposal.py", "docs/guide.md", "src/unrelated.py"]
        )
        .as_dict()
    )

    mentions = answer["answer"]["mentions"]
    assert [m["id"] for m in mentions["src/will/autonomy/proposal.py"]] == ["ADR-009"]
    assert mentions["docs/guide.md"][0]["status"] == "superseded"
    assert mentions["src/unrelated.py"] == []
    assert answer["limits"]
