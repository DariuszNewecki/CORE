# tests/body/sandbox/test_models.py
"""Job validation and the result rules (ADR-132 D10.10)."""

from __future__ import annotations

import pytest

from body.sandbox.models import (
    JobRejected,
    SandboxJob,
    SandboxResult,
    classify_pytest,
)


def _job(**overrides: object) -> SandboxJob:
    data: dict[str, object] = {
        "job_id": "a" * 32,
        "kind": "pytest",
        "targets": ("tests/test_x.py",),
        "timeout_sec": 30,
    }
    data.update(overrides)
    return SandboxJob(**data)  # type: ignore[arg-type]


def test_valid_job_round_trips() -> None:
    job = _job(markers="not slow", exclude_integration=True)
    assert SandboxJob.from_dict(job.to_dict()) == job


@pytest.mark.parametrize(
    "overrides",
    [
        {"job_id": "../etc"},
        {"kind": "make"},
        {"timeout_sec": 0},
        {"timeout_sec": 99999},
        {"targets": ()},
        {"targets": ("-pmyplugin",)},
        {"targets": ("/etc/passwd",)},
        {"targets": ("tests/../../x.py",)},
        {"markers": "-p evil"},
    ],
)
def test_bad_jobs_are_refused(overrides: dict[str, object]) -> None:
    with pytest.raises(JobRejected):
        _job(**overrides).validate()


def test_node_ids_are_allowed_targets() -> None:
    _job(targets=("tests/test_x.py::test_one[a-b]",)).validate()


def test_effective_markers_add_the_integration_exclusion() -> None:
    assert _job().effective_markers() is None
    assert _job(exclude_integration=True).effective_markers() == "not integration"
    assert (
        _job(markers="fast", exclude_integration=True).effective_markers()
        == "(fast) and not integration"
    )


def _report(executed: int, failed: int = 0, excluded: list[str] | None = None) -> dict:
    return {
        "counts": {"executed": executed, "failed": failed},
        "excluded": excluded or [],
        "error": None,
    }


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"exit_code": None, "timed_out": True, "report": None}, ("timeout", "none")),
        ({"exit_code": 0, "timed_out": False, "report": None}, ("error", "none")),
        (
            {
                "exit_code": 0,
                "timed_out": False,
                "report": {"error": "candidate_not_loaded: x"},
            },
            ("error", "none"),
        ),
        # exit 5 (nothing collected/selected) is never success
        (
            {"exit_code": 5, "timed_out": False, "report": _report(0)},
            ("not_run", "none"),
        ),
        (
            {"exit_code": 0, "timed_out": False, "report": _report(0)},
            ("not_run", "none"),
        ),
        (
            {"exit_code": 1, "timed_out": False, "report": _report(3, 1)},
            ("failed", "full"),
        ),
        (
            {"exit_code": 0, "timed_out": False, "report": _report(3)},
            ("passed", "full"),
        ),
        ({"exit_code": 4, "timed_out": False, "report": _report(3)}, ("error", "none")),
    ],
)
def test_classification(kwargs: dict, expected: tuple[str, str]) -> None:
    status, completeness, _ = classify_pytest(exclude_integration=False, **kwargs)
    assert (status, completeness) == expected


def test_integration_only_target_is_not_run_with_exclusions() -> None:
    status, completeness, reason = classify_pytest(
        exit_code=5,
        timed_out=False,
        report=_report(0, excluded=["tests/test_db.py::test_db"]),
        exclude_integration=True,
    )
    assert (status, completeness) == ("not_run", "none")
    assert "excluded" in reason


def test_permitted_subset_is_partial_and_never_ok() -> None:
    status, completeness, _ = classify_pytest(
        exit_code=0,
        timed_out=False,
        report=_report(2, excluded=["tests/test_db.py::test_db"]),
        exclude_integration=True,
    )
    assert (status, completeness) == ("passed", "partial")
    result = SandboxResult(
        status=status, completeness=completeness, isolation="service"
    )
    assert not result.ok


def test_not_run_is_never_ok() -> None:
    assert not SandboxResult.not_run("service", "socket missing").ok
    assert SandboxResult(status="passed", completeness="full", isolation="local").ok


@pytest.mark.parametrize(
    ("exit_code", "status"),
    [(0, "passed"), (2, "failed"), (1, "failed"), (5, "not_run"), (3, "error")],
)
def test_collect_only_jobs_are_classified_by_collection(
    exit_code: int, status: str
) -> None:
    got, _completeness, _reason = classify_pytest(
        exit_code=exit_code,
        timed_out=False,
        report={"counts": {"collected": 4, "executed": 0}},
        exclude_integration=True,
        collect_only=True,
    )
    assert got == status


def test_collect_only_is_a_known_job_kind() -> None:
    from body.sandbox.models import COLLECT_KIND, JOB_KINDS

    assert COLLECT_KIND in JOB_KINDS
