# tests/mind/governance/test_meta_validator_live_intent_ratchet.py
"""Constitutional-validation ratchet over the live ``.intent/`` tree.

``core-admin constitution validate`` (``MetaValidator.validate_all_documents``)
has reported errors against CORE's own ``.intent/`` since approximately
2026-07-01 without anyone noticing: the command is not part of
``.github/workflows/core-ci.yml`` and, until this module, no test ran the
validator against the real tree (``test_specs_doc_validator.py`` covers only
``SpecsDocValidator``). The validator itself is correct; the gate was unwired.

This test wires it as a **ratchet**, not a snapshot:

* It asserts the observed error set **equals** ``KNOWN_ERRORS`` exactly —
  set equality, never a count, so one error disappearing while an unrelated
  one appears cannot pass.
* A **new** error fails the test. The fix is the ``.intent/`` document or
  schema, applied by the Governor — never an addition to ``KNOWN_ERRORS``
  without review.
* A **fixed** error also fails the test, until its entry is deliberately
  removed from ``KNOWN_ERRORS`` in the same reviewed change. Every change to
  the known constitutional-error set is therefore explicit and reviewed.
* The terminal state is ``KNOWN_ERRORS == frozenset()``. At that point
  ``core-admin constitution validate`` (which exits 1 on any error) can be
  added to CI as a raw zero-error gate and this module reduces to a plain
  "no errors" assertion.

``KNOWN_ERRORS`` is **known constitutional-validation debt discovered during
the 2026-09-14 reconnaissance**, with a defined removal path — not a permanent
fixture. Two defect classes account for all nine entries:

1. ``META/flow.schema.json`` (last changed 2026-05-25) predates fields that
   ADR-135 D5 and ADR-140 D2/D4/D8/D9 authorise and that ``FlowRegistry`` /
   ``FlowExecutor`` consume today: root ``generation_mode`` and
   ``cognitive_capability``, flow-level ``remediates`` (documentary only),
   step ``kind: cognitive`` and step ``produces``. Resolution: the Governor
   declares those fields in the schema.
2. ``artifact_types/architecture_bridge.yaml`` (#617, 2026-07-07) omits the
   two fields ``META/artifact_type.schema.json`` requires per ADR-090 D2
   (``identity_key``, ``change_record``); the other sixteen artifact-type
   declarations carry them. Resolution: the Governor adds the two fields.

Hermetic and read-only: no network, no database; the validator reads the real
``.intent/`` because the real tree is the subject, and writes nothing.
"""

from __future__ import annotations

from pathlib import Path

from mind.governance.meta_validator import MetaValidator, ValidationError


REPO_ROOT = Path(__file__).resolve().parents[3]
INTENT_ROOT = REPO_ROOT / ".intent"

# Normalised identity of one validator error: (document, field path, message).
ErrorKey = tuple[str, str, str]


def _key(error: ValidationError) -> ErrorKey:
    return (error.document, error.field or "root", error.message)


# ---------------------------------------------------------------------------
# The accepted debt. One entry per validator error, with why it is tolerated.
# Removing an entry is the ONLY sanctioned way for this set to shrink; adding
# one requires a reviewed decision that the new error is accepted debt rather
# than a regression.
# ---------------------------------------------------------------------------

_FLOW_SCHEMA_LAG = (
    "META/flow.schema.json predates the ADR-135 D5 / ADR-140 D2-D4-D8-D9 "
    "manifest fields that FlowRegistry and FlowExecutor consume; awaiting the "
    "Governor's schema declaration."
)
_ARTIFACT_TYPE_MISSING_REQUIRED = (
    "architecture_bridge.yaml (#617) omits the ADR-090 D2 required fields the "
    "other sixteen artifact types carry; awaiting the Governor's document fix."
)

KNOWN_ERRORS: dict[ErrorKey, str] = {
    # -- defect class 2: document missing ADR-090 D2 required fields ---------
    (
        "artifact_types/architecture_bridge.yaml",
        "root",
        "'identity_key' is a required property",
    ): _ARTIFACT_TYPE_MISSING_REQUIRED,
    (
        "artifact_types/architecture_bridge.yaml",
        "root",
        "'change_record' is a required property",
    ): _ARTIFACT_TYPE_MISSING_REQUIRED,
    # -- defect class 1: flow.schema.json lags ADR-135 / ADR-140 -------------
    (
        "flows/flow.build_test_for_symbol.yaml",
        "root",
        "Additional properties are not allowed ('cognitive_capability', "
        "'generation_mode' were unexpected)",
    ): _FLOW_SCHEMA_LAG,
    (
        "flows/flow.build_test_for_symbol.yaml",
        "flow",
        "Additional properties are not allowed ('remediates' was unexpected)",
    ): _FLOW_SCHEMA_LAG,
    (
        "flows/flow.build_test_for_symbol.yaml",
        "flow.steps.0",
        "Additional properties are not allowed ('produces' was unexpected)",
    ): _FLOW_SCHEMA_LAG,
    (
        "flows/flow.build_test_for_symbol.yaml",
        "flow.steps.0.kind",
        "'cognitive' is not one of ['action', 'flow']",
    ): _FLOW_SCHEMA_LAG,
    (
        "flows/flow.fix_modularity.yaml",
        "root",
        "Additional properties are not allowed ('cognitive_capability' was unexpected)",
    ): _FLOW_SCHEMA_LAG,
    (
        "flows/flow.fix_modularity.yaml",
        "flow.steps.0",
        "Additional properties are not allowed ('produces' was unexpected)",
    ): _FLOW_SCHEMA_LAG,
    (
        "flows/flow.fix_modularity.yaml",
        "flow.steps.0.kind",
        "'cognitive' is not one of ['action', 'flow']",
    ): _FLOW_SCHEMA_LAG,
}


def _fmt(keys: set[ErrorKey]) -> str:
    return "\n".join(f"  ({d!r}, {f!r}, {m!r})" for d, f, m in sorted(keys))


def _run_validator() -> tuple[MetaValidator, set[ErrorKey]]:
    validator = MetaValidator()
    # Guard against validating some other tree (REPO_PATH / MIND env pins):
    # the subject of this ratchet is CORE's own .intent/, nothing else.
    assert validator.intent_root.resolve() == INTENT_ROOT.resolve(), (
        f"MetaValidator resolved {validator.intent_root}, expected {INTENT_ROOT}"
    )
    report = validator.validate_all_documents()
    assert report.documents_checked > 0, (
        "MetaValidator checked zero documents — the ratchet would pass vacuously"
    )
    return validator, {_key(e) for e in report.errors}


def test_known_errors_table_is_well_formed() -> None:
    """Every accepted entry names a real document and carries a reason."""
    for (document, _field, _message), why in KNOWN_ERRORS.items():
        assert (INTENT_ROOT / document).is_file(), (
            f"KNOWN_ERRORS names {document!r}, which no longer exists under "
            f".intent/ — remove its entries."
        )
        assert why.strip(), f"KNOWN_ERRORS entry for {document!r} has no reason"


def test_live_intent_validation_errors_equal_known_debt_exactly() -> None:
    """The ratchet: observed error set == KNOWN_ERRORS, in both directions."""
    _validator, observed = _run_validator()
    expected = set(KNOWN_ERRORS)

    new_errors = observed - expected
    fixed_errors = expected - observed

    problems: list[str] = []
    if new_errors:
        problems.append(
            f"{len(new_errors)} NEW constitutional-validation error(s) not in the "
            "accepted set. Fix the .intent/ document or schema (Governor-applied); "
            "do not add to KNOWN_ERRORS without a reviewed decision that this is "
            "accepted debt:\n" + _fmt(new_errors)
        )
    if fixed_errors:
        problems.append(
            f"{len(fixed_errors)} accepted error(s) NO LONGER OCCUR — the debt was "
            "repaired. Remove these entries from KNOWN_ERRORS in this same change "
            "so the ratchet tightens:\n" + _fmt(fixed_errors)
        )
    assert not problems, "\n\n".join(problems)


def test_ratchet_terminal_state_reminder() -> None:
    """When KNOWN_ERRORS is empty, promote the raw CLI to a CI gate.

    Not a failure — a signpost: once this set reaches zero, add
    ``core-admin constitution validate`` (exit 1 on any error) to
    core-ci.yml as a zero-error gate and collapse this module to
    ``assert not report.errors``.
    """
    if not KNOWN_ERRORS:
        _validator, observed = _run_validator()
        assert not observed
