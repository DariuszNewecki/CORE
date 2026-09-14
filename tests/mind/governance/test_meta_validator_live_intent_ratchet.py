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

Two ways this ratchet can lie, and the guards against them:

* **Scope loss.** ``MetaValidator.validate_all_documents()`` walks only the
  directories listed in ``.intent/META/intent_tree.yaml::validated_directories``.
  Dropping a directory from that list makes its errors *stop being observed*,
  which the set comparison would report as "repaired debt" — and the failure
  message would then instruct the reader to delete the corresponding
  ``KNOWN_ERRORS`` entries, leaving the gate permanently blind to that
  directory while green. ``_run_validator`` therefore pins the validation
  surface (``EXPECTED_VALIDATED_DIRECTORIES`` and a ``documents_checked``
  floor) and fails as a **scope defect before** any set comparison runs.
  A narrowed surface never presents itself as repaired debt.

* **Message-string coupling.** ``KNOWN_ERRORS`` keys on ``jsonschema``'s
  error message text verbatim (e.g. "Additional properties are not allowed
  (... was unexpected)", "'x' is a required property", "'x' is not one of
  [...]"). A ``jsonschema`` release that rewords any of these yields N new
  errors and N repaired ones **in the same run** — visually indistinguishable
  from total constitutional collapse, and it arrives via a dependency bump,
  not a governance change. Before treating a simultaneous
  nine-new / nine-repaired result as real, check the lockfile diff
  (``poetry.lock`` → ``jsonschema``). If the messages merely moved, the
  correct edit is to re-key the affected entries to the new wording in the
  dependency-bump change — not to treat the debt as repaired, and not to
  treat the rewording as new constitutional breakage. The keys are kept
  verbatim on purpose: making them version-independent would blur exactly
  the property/value detail the ratchet exists to pin.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from mind.governance.meta_validator import MetaValidator, ValidationError


REPO_ROOT = Path(__file__).resolve().parents[3]
INTENT_ROOT = REPO_ROOT / ".intent"
INTENT_TREE = INTENT_ROOT / "META" / "intent_tree.yaml"

# ---------------------------------------------------------------------------
# The pinned validation surface. Read from .intent/META/intent_tree.yaml at
# 76c3f204 and checked in here so that the *scope* of the validator is itself
# under review: shrinking it is a scope defect, never repaired debt. Adding a
# directory to .intent/META/intent_tree.yaml::validated_directories (a
# constitutional act — the file's own notes say so) must be mirrored here in
# the same change; that is deliberate friction, not accident.
# ---------------------------------------------------------------------------
EXPECTED_VALIDATED_DIRECTORIES: tuple[str, ...] = (
    "META",
    "artifact_types",
    "flows",
    "phases",
    "rules",
    "workers",
    "workflows/definitions",
    "workflows/stages",
)

# Floor, not exact: 147 documents were checked at 76c3f204. The attack shape
# this guards is *shrinkage* (a dropped directory removes many documents at
# once; a deleted document removes one), which a floor catches at zero
# maintenance cost when documents are legitimately added — new workers, rules
# and flows land in .intent/ routinely and must not each require a test edit.
# Raise this when documents are added if you want the floor to stay tight;
# lower it only in a reviewed change that explains which documents were
# retired. Residual gap: a removal masked by an equal-or-larger addition in the
# same change is not caught by the count alone — the directory pin above and
# test_known_errors_table_is_well_formed (every KNOWN_ERRORS document must
# still exist) narrow that gap; they do not close it completely.
MIN_DOCUMENTS_CHECKED = 147

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


_SCOPE_SHRANK = (
    "VALIDATOR SCOPE SHRANK — this is NOT repaired debt. Do NOT edit "
    "KNOWN_ERRORS in response. The set of .intent/ documents MetaValidator "
    "looks at is narrower than the pinned surface, so errors may have stopped "
    "being *observed* without being *fixed*. Restore "
    ".intent/META/intent_tree.yaml::validated_directories (or, if a directory "
    "was retired deliberately, update EXPECTED_VALIDATED_DIRECTORIES / "
    "MIN_DOCUMENTS_CHECKED in a reviewed change that says so)."
)


def _declared_validated_directories() -> list[str] | None:
    """validated_directories as written in .intent/META/intent_tree.yaml."""
    doc = yaml.safe_load(INTENT_TREE.read_text(encoding="utf-8"))
    dirs = doc.get("validated_directories") if isinstance(doc, dict) else None
    if not isinstance(dirs, list):
        return None
    return sorted(str(d).replace("\\", "/").rstrip("/") for d in dirs)


def _assert_surface_pinned(validator: MetaValidator, documents_checked: int) -> None:
    """Fail as a scope defect if the validation surface is narrower than pinned.

    Runs BEFORE the set comparison on every path that reaches it, so a
    narrowed surface can never be reported to the reader as repaired debt.
    """
    expected = sorted(EXPECTED_VALIDATED_DIRECTORIES)
    declared = _declared_validated_directories()
    assert declared == expected, (
        f"{_SCOPE_SHRANK}\n  declared in intent_tree.yaml: {declared}\n"
        f"  pinned:                      {expected}"
    )
    # What the validator actually resolved (None = fallback: walk everything,
    # i.e. a *widened* surface — also a defect; the pin must be exact).
    resolved = (
        validator._validated_directories
    )  # private by design: the scope under test
    resolved_sorted = sorted(resolved) if resolved is not None else None
    assert resolved_sorted == expected, (
        f"{_SCOPE_SHRANK}\n  MetaValidator resolved: {resolved_sorted}\n"
        f"  pinned:                 {expected}"
    )
    assert documents_checked >= MIN_DOCUMENTS_CHECKED, (
        f"{_SCOPE_SHRANK}\n  documents_checked={documents_checked} < "
        f"MIN_DOCUMENTS_CHECKED={MIN_DOCUMENTS_CHECKED}"
    )


def _run_validator() -> tuple[MetaValidator, set[ErrorKey]]:
    validator = MetaValidator()
    # Guard against validating some other tree (REPO_PATH / MIND env pins):
    # the subject of this ratchet is CORE's own .intent/, nothing else.
    assert validator.intent_root.resolve() == INTENT_ROOT.resolve(), (
        f"MetaValidator resolved {validator.intent_root}, expected {INTENT_ROOT}"
    )
    report = validator.validate_all_documents()
    # Scope pin first: a narrowed surface must fail HERE, before the caller
    # can compute "repaired" vs "new" and mislead the reader.
    _assert_surface_pinned(validator, report.documents_checked)
    return validator, {_key(e) for e in report.errors}


def test_validation_surface_is_pinned() -> None:
    """Named scope guard: the surface the ratchet reasons over is exactly the
    pinned one. Redundant with the check inside _run_validator by design —
    this gives the scope defect its own test name in CI output; the in-path
    check guarantees the ratchet itself can never misreport it."""
    _run_validator()


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
