# tests/mind/governance/test_specs_doc_validator.py
"""Sample tests for the .specs/ document-header structural validator (ADR-105 D6).

Covers frontmatter parsing and schema validation, including the load-bearing
cross-tree case: the .specs/META schemas $ref the enum vocabulary in
.intent/META/enums.json, and that reference must resolve for an invalid enum
value to be caught.
"""

from __future__ import annotations

import json
from pathlib import Path

from mind.governance.specs_doc_validator import SpecsDocValidator, parse_frontmatter


REPO_ROOT = Path(__file__).resolve().parents[3]


def _adr_schema() -> dict:
    return json.loads(
        (REPO_ROOT / ".specs/META/adr.header.schema.json").read_text(encoding="utf-8")
    )


def _paper_schema() -> dict:
    return json.loads(
        (REPO_ROOT / ".specs/META/paper.header.schema.json").read_text(encoding="utf-8")
    )


# ---- frontmatter parsing ----


def test_parse_frontmatter_basic() -> None:
    text = "---\nkind: adr\nstatus: accepted\n---\n# Title\nbody\n"
    assert parse_frontmatter(text) == {"kind": "adr", "status": "accepted"}


def test_parse_frontmatter_after_html_comment() -> None:
    text = "<!-- path: .specs/papers/x.md -->\n---\nkind: paper\n---\n# T\n"
    assert parse_frontmatter(text) == {"kind": "paper"}


def test_parse_frontmatter_absent_returns_none() -> None:
    assert parse_frontmatter("# Just a title\n\nno header here\n") is None


# ---- schema validation ----


# ---- ADR-105 D6 Stage 2b completion gates ----


def test_all_modeled_specs_docs_valid() -> None:
    """Regression gate: every modeled .specs/ doc must have a valid frontmatter header.

    If this fails, a document was added or edited without a conformant YAML header.
    Fix by adding or correcting the --- ... --- block per the per-class schema in
    .specs/META/<kind>.header.schema.json.
    """
    report = SpecsDocValidator(repo_root=REPO_ROOT).validate_all_documents()
    assert report.documents_invalid == 0, (
        f"{report.documents_invalid} invalid .specs/ doc(s):\n"
        + "\n".join(
            f"  {e.document}: {e.error_type} — {e.message}" for e in report.errors
        )
    )


def test_specs_doc_validator_wired_into_constitution_validate() -> None:
    """Wire check: SpecsDocValidator must be present in the constitution validate module.

    The ADR-105 D6 hook 1 validator is wired at the CLI layer (cli/resources/constitution/
    validate.py) rather than shared/infrastructure because shared cannot import mind/.
    """
    from cli.resources.constitution import validate as validate_module

    assert hasattr(validate_module, "SpecsDocValidator"), (
        "SpecsDocValidator not imported in cli/resources/constitution/validate.py — "
        "ADR-105 D6 stage 2b wiring missing"
    )
