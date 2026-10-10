"""check_class_coverage: a CCC run whose check classes were skipped says so.

Run dfa4950d (2026-10-10) skipped SAMECONCERN and R1_SCOPED (collection not
seeded) while `coherence check` printed "0 skipped" — it counted input items,
never the check classes the manifest records (#624).
"""

from __future__ import annotations

from cli.logic.coherence_coverage import check_class_coverage, coverage_lines


def _manifest(check_status: dict) -> list[dict]:
    return [
        {"domain": "adr", "path": ".specs/decisions/ADR-001.md", "status": "checked"},
        {
            "domain": "_meta",
            "path": None,
            "type": "check_classes_run",
            "check_status": check_status,
        },
    ]


_SEED_GAP = "governance_claims collection not seeded"


# ID: d461addf-74fc-441c-ad2f-ef77a2464c5a
def test_skipped_check_classes_make_the_run_partial() -> None:
    coverage = check_class_coverage(
        _manifest(
            {
                "PATH_REF": {"status": "ok", "emitted": 134},
                "SAMECONCERN": {"status": "skipped", "reason": _SEED_GAP, "emitted": 0},
                "R1_SCOPED": {"status": "skipped", "reason": _SEED_GAP, "emitted": 0},
            }
        )
    )

    assert coverage.ran == ["PATH_REF"]
    assert [name for name, _ in coverage.skipped] == ["R1_SCOPED", "SAMECONCERN"]
    assert coverage.partial is True
    text = "\n".join(coverage_lines(coverage))
    assert "1 ran, 2 skipped, 0 failed" in text
    assert "SKIPPED SAMECONCERN" in text and _SEED_GAP in text
    assert "PARTIAL RUN" in text


# ID: b043c4af-50fa-4fbf-919b-b5803e39e5c7
def test_failed_check_class_is_named() -> None:
    coverage = check_class_coverage(
        _manifest({"VOCABULARY": {"status": "error", "error": "boom", "emitted": 0}})
    )

    assert coverage.failed == [("VOCABULARY", "boom")]
    assert coverage.partial is True
    assert "  FAILED  VOCABULARY: boom" in coverage_lines(coverage)


# ID: 731738de-1d7f-403f-969e-64588e7b126e
def test_all_check_classes_ran_is_not_partial() -> None:
    coverage = check_class_coverage(
        _manifest({"PATH_REF": {"status": "ok", "emitted": 0}})
    )

    assert coverage.partial is False
    assert coverage_lines(coverage) == ["Check classes: 1 ran, 0 skipped, 0 failed"]


# ID: b2e7fddc-0277-4bfb-971a-adc6d4c53850
def test_a_run_without_a_check_class_record_is_partial() -> None:
    """Pre-#624 runs carry no record: unknown is never shown as complete."""
    coverage = check_class_coverage(
        [{"domain": "adr", "path": "x.md", "status": "checked"}]
    )

    assert coverage.recorded is False
    assert coverage.partial is True
    assert "unknown" in coverage_lines(coverage)[0]
