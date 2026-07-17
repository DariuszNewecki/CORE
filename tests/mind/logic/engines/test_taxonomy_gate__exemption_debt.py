"""Unit tests for ``TaxonomyGateEngine``'s ``exemption_debt_declared`` check
(ADR-152 D4).

These tests pin:

  - context-level dispatch is True for the check_type;
  - clean tree (no governed_exclusions anywhere) -> no findings;
  - a malformed entry (missing a required field) -> one malformed_entry
    finding, distinct check_id;
  - a structurally valid closure_type='condition' entry -> one
    acknowledged_debt finding, always (no deadline concept);
  - a closure_type='deadline' entry with a future deadline ->
    acknowledged_debt;
  - a closure_type='deadline' entry with a past deadline and an
    unaccepted closure ADR -> warning;
  - a closure_type='deadline' entry more than 30 days past deadline with
    an unaccepted closure ADR -> lapsed;
  - a closure_type='deadline' entry past deadline but with an *accepted*
    closure ADR -> acknowledged_debt (not warning/lapsed) — an accepted
    closure lands the debt, it doesn't escalate it;
  - unknown check_type still returns the shared ok=False marker.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

from mind.logic.engines.taxonomy_gate import TaxonomyGateEngine
from shared.path_resolver import PathResolver


_EXEMPTION_DEBT_CHECK = "exemption_debt_declared"

# Minimal governed_exclusions.items sub-schema — only the shape D4 actually
# reads (schema[properties][governed_exclusions][items]), not a full copy
# of enforcement_mapping.schema.json.
_MINIMAL_SCHEMA = """
{
  "properties": {
    "governed_exclusions": {
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["file", "rationale", "closure_type"],
        "properties": {
          "file": {"type": "string", "minLength": 1},
          "closure_type": {"type": "string", "enum": ["condition", "deadline"]},
          "class": {"type": "string", "minLength": 1},
          "category": {"type": "string", "enum": ["facade", "algorithm", "catalog"]},
          "rationale": {"type": "string", "minLength": 1},
          "removal_condition": {"type": "string", "minLength": 1},
          "deadline": {"type": "string", "format": "date"},
          "closure_adr": {"type": "string", "pattern": "^ADR-[0-9]+$"},
          "tracking_issue": {"type": "string", "pattern": "^#[0-9]+$"}
        },
        "allOf": [
          {
            "if": {"properties": {"closure_type": {"const": "condition"}}, "required": ["closure_type"]},
            "then": {"required": ["class", "category", "removal_condition"]}
          },
          {
            "if": {"properties": {"closure_type": {"const": "deadline"}}, "required": ["closure_type"]},
            "then": {"required": ["deadline", "closure_adr", "tracking_issue"]}
          }
        ]
      }
    }
  }
}
"""


def _fake_context(repo_root: Path) -> SimpleNamespace:
    return SimpleNamespace(repo_path=repo_root)


def _engine(repo: Path) -> TaxonomyGateEngine:
    return TaxonomyGateEngine(path_resolver=PathResolver(repo_root=repo))


def _write_schema(repo: Path) -> None:
    schema_path = repo / ".intent" / "META" / "enforcement_mapping.schema.json"
    schema_path.parent.mkdir(parents=True, exist_ok=True)
    schema_path.write_text(_MINIMAL_SCHEMA, encoding="utf-8")


def _write_mapping(repo: Path, rel_path: str, content: str) -> None:
    path = repo / ".intent" / "enforcement" / "mappings" / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_adr(repo: Path, adr_id: str, status: str) -> None:
    path = repo / ".specs" / "decisions" / f"{adr_id}-fixture.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\nkind: adr\nid: {adr_id}\ntitle: Fixture\nstatus: {status}\n---\n\nBody.\n",
        encoding="utf-8",
    )


def test_is_context_level_true_for_exemption_debt_check_type() -> None:
    assert TaxonomyGateEngine.is_context_level_for(_EXEMPTION_DEBT_CHECK) is True


async def test_clean_tree_yields_no_findings(tmp_path: Path) -> None:
    _write_schema(tmp_path)
    _write_mapping(
        tmp_path,
        "architecture/example.yaml",
        "mappings:\n  architecture.example.rule:\n    engine: ast_gate\n"
        "    params: {}\n    scope: {applies_to: [\"src/**\"]}\n",
    )

    findings = await _engine(tmp_path).verify_context(
        _fake_context(tmp_path), {"check_type": _EXEMPTION_DEBT_CHECK}
    )
    assert findings == []


async def test_malformed_entry_missing_required_field(tmp_path: Path) -> None:
    _write_schema(tmp_path)
    _write_mapping(
        tmp_path,
        "architecture/example.yaml",
        "mappings:\n"
        "  architecture.example.rule:\n"
        "    engine: ast_gate\n"
        "    params: {}\n"
        "    scope: {applies_to: [\"src/**\"]}\n"
        "    governed_exclusions:\n"
        "      - file: src/x.py\n"
        "        rationale: missing closure_type entirely\n",
    )

    findings = await _engine(tmp_path).verify_context(
        _fake_context(tmp_path), {"check_type": _EXEMPTION_DEBT_CHECK}
    )
    assert len(findings) == 1
    assert findings[0].check_id == "governance.exemption_debt.malformed_entry"
    assert findings[0].context["stage"] == "malformed"


async def test_condition_closed_entry_is_always_acknowledged_debt(
    tmp_path: Path,
) -> None:
    _write_schema(tmp_path)
    _write_mapping(
        tmp_path,
        "code/modularity.yaml",
        "mappings:\n"
        "  code.modularity.class_too_large:\n"
        "    engine: ast_gate\n"
        "    params: {}\n"
        "    scope: {applies_to: [\"src/**\"]}\n"
        "    governed_exclusions:\n"
        "      - file: src/facade.py\n"
        "        closure_type: condition\n"
        "        class: BigFacade\n"
        "        category: facade\n"
        "        rationale: gateway whose size reflects surface breadth\n"
        "        removal_condition: gains a second responsibility\n",
    )

    findings = await _engine(tmp_path).verify_context(
        _fake_context(tmp_path), {"check_type": _EXEMPTION_DEBT_CHECK}
    )
    assert len(findings) == 1
    f = findings[0]
    assert f.check_id == "governance.exemption_debt.declared"
    assert f.context["stage"] == "acknowledged_debt"
    assert f.context["closure_type"] == "condition"


async def test_deadline_closed_future_deadline_is_acknowledged_debt(
    tmp_path: Path,
) -> None:
    _write_schema(tmp_path)
    _write_adr(tmp_path, "ADR-900", "proposed")
    _write_mapping(
        tmp_path,
        "architecture/example.yaml",
        "mappings:\n"
        "  architecture.example.rule:\n"
        "    engine: ast_gate\n"
        "    params: {}\n"
        "    scope: {applies_to: [\"src/**\"]}\n"
        "    governed_exclusions:\n"
        "      - file: src/y.py\n"
        "        closure_type: deadline\n"
        "        rationale: temporary bypass pending refactor\n"
        "        deadline: \"2999-01-01\"\n"
        "        closure_adr: ADR-900\n"
        "        tracking_issue: \"#1\"\n",
    )

    findings = await _engine(tmp_path).verify_context(
        _fake_context(tmp_path), {"check_type": _EXEMPTION_DEBT_CHECK}
    )
    assert len(findings) == 1
    assert findings[0].context["stage"] == "acknowledged_debt"


async def test_deadline_closed_past_deadline_unaccepted_adr_is_warning(
    tmp_path: Path,
) -> None:
    _write_schema(tmp_path)
    _write_adr(tmp_path, "ADR-901", "proposed")
    ten_days_ago = (date.today() - timedelta(days=10)).isoformat()
    _write_mapping(
        tmp_path,
        "architecture/example.yaml",
        "mappings:\n"
        "  architecture.example.rule:\n"
        "    engine: ast_gate\n"
        "    params: {}\n"
        "    scope: {applies_to: [\"src/**\"]}\n"
        "    governed_exclusions:\n"
        "      - file: src/y.py\n"
        "        closure_type: deadline\n"
        "        rationale: temporary bypass pending refactor\n"
        f"        deadline: \"{ten_days_ago}\"\n"
        "        closure_adr: ADR-901\n"
        "        tracking_issue: \"#1\"\n",
    )

    findings = await _engine(tmp_path).verify_context(
        _fake_context(tmp_path), {"check_type": _EXEMPTION_DEBT_CHECK}
    )
    assert len(findings) == 1
    assert findings[0].context["stage"] == "warning"
    assert findings[0].context["closure_adr_accepted"] is False


async def test_deadline_closed_lapsed_far_past_deadline_unaccepted_adr(
    tmp_path: Path,
) -> None:
    _write_schema(tmp_path)
    _write_adr(tmp_path, "ADR-902", "proposed")
    forty_days_ago = (date.today() - timedelta(days=40)).isoformat()
    _write_mapping(
        tmp_path,
        "architecture/example.yaml",
        "mappings:\n"
        "  architecture.example.rule:\n"
        "    engine: ast_gate\n"
        "    params: {}\n"
        "    scope: {applies_to: [\"src/**\"]}\n"
        "    governed_exclusions:\n"
        "      - file: src/y.py\n"
        "        closure_type: deadline\n"
        "        rationale: temporary bypass pending refactor\n"
        f"        deadline: \"{forty_days_ago}\"\n"
        "        closure_adr: ADR-902\n"
        "        tracking_issue: \"#1\"\n",
    )

    findings = await _engine(tmp_path).verify_context(
        _fake_context(tmp_path), {"check_type": _EXEMPTION_DEBT_CHECK}
    )
    assert len(findings) == 1
    assert findings[0].context["stage"] == "lapsed"


async def test_deadline_closed_past_deadline_accepted_adr_is_not_escalated(
    tmp_path: Path,
) -> None:
    """An accepted closure ADR lands the debt — it must not still read as
    warning/lapsed just because the calendar date has passed."""
    _write_schema(tmp_path)
    _write_adr(tmp_path, "ADR-903", "accepted")
    forty_days_ago = (date.today() - timedelta(days=40)).isoformat()
    _write_mapping(
        tmp_path,
        "architecture/example.yaml",
        "mappings:\n"
        "  architecture.example.rule:\n"
        "    engine: ast_gate\n"
        "    params: {}\n"
        "    scope: {applies_to: [\"src/**\"]}\n"
        "    governed_exclusions:\n"
        "      - file: src/y.py\n"
        "        closure_type: deadline\n"
        "        rationale: temporary bypass pending refactor\n"
        f"        deadline: \"{forty_days_ago}\"\n"
        "        closure_adr: ADR-903\n"
        "        tracking_issue: \"#1\"\n",
    )

    findings = await _engine(tmp_path).verify_context(
        _fake_context(tmp_path), {"check_type": _EXEMPTION_DEBT_CHECK}
    )
    assert len(findings) == 1
    assert findings[0].context["stage"] == "acknowledged_debt"
    assert findings[0].context["closure_adr_accepted"] is True


async def test_unknown_check_type_in_verify_context_returns_block(
    tmp_path: Path,
) -> None:
    findings = await _engine(tmp_path).verify_context(
        _fake_context(tmp_path), {"check_type": "something_else"}
    )
    assert len(findings) == 1
    assert findings[0].check_id == "taxonomy_gate.unknown_check_type"
    assert _EXEMPTION_DEBT_CHECK in findings[0].message
