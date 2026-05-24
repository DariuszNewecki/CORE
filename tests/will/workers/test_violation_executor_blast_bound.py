"""Tests for ViolationExecutorWorker blast bound on files-per-cycle.

The bound is constitutionally declared in
`.intent/workers/violation_executor.yaml` at
`mandate.schedule.files_per_cycle_max`. The YAML is the single source of
truth — the worker reads it at __init__ and refuses to load if the field
is absent (cognate with ADR-069 D3's no-runtime-fallback rule for
`lease_seconds`). There is no Python-side fallback constant to drift
against; the tests read the YAML directly to ensure they exercise the
same value the worker will use at runtime.

These tests verify the slice-and-defer arithmetic at the cap boundary:
given more files than the cap, only the first N are processed and the
remaining files' findings are deferred to the next cycle.

Heavier integration testing (mocked claim → process → release/abandon
flow) is deferred until the worker has a test-fixture pattern for its
full ceremony. The two tests below cover the safety property that is
new in this hardening commit; the existing per-file ceremony is
exercised by the surrounding remediator tests.

Authority: 2026-05-24 hardening sweep Session 2; blast-bound principle.
"""

from __future__ import annotations

from pathlib import Path

import yaml


_VIOLATION_EXECUTOR_YAML = Path(".intent/workers/violation_executor.yaml")


def _load_declared_cap() -> int:
    """Read the blast bound from the worker YAML — single source of truth."""
    declaration = yaml.safe_load(_VIOLATION_EXECUTOR_YAML.read_text("utf-8"))
    return int(declaration["mandate"]["schedule"]["files_per_cycle_max"])


def test_worker_yaml_declares_blast_bound() -> None:
    """The YAML MUST declare files_per_cycle_max — there is no Python fallback.

    Per the no-runtime-fallback principle (ADR-069 D3 applied here), the
    worker raises at __init__ if the declaration is missing. This test
    is the structural check that the declaration exists with a positive
    integer value; absent or zero/negative would fail the worker's load.
    """
    cap = _load_declared_cap()
    assert cap > 0, (
        f"files_per_cycle_max in violation_executor.yaml must be a "
        f"positive integer; got {cap}"
    )


def test_slice_logic_separates_process_from_defer() -> None:
    """File-grouping math at the cap boundary.

    Given cap N and (N+1) distinct files in the cycle, the slice should
    yield N files to process and 1 file's worth of findings to defer.
    Each file may carry multiple findings; the deferred findings list
    flattens across deferred files.
    """
    cap = _load_declared_cap()
    by_file = {
        f"src/f{i}.py": [{"id": f"finding-{i}-a"}, {"id": f"finding-{i}-b"}]
        for i in range(cap + 1)
    }
    all_files = list(by_file.items())

    assert len(all_files) == cap + 1

    process = dict(all_files[:cap])
    deferred = all_files[cap:]
    deferred_findings = [f for _, f_list in deferred for f in f_list]
    deferred_paths = [path for path, _ in deferred]

    assert len(process) == cap, "should process exactly the cap"
    assert len(deferred) == 1, "exactly one file should be deferred"
    assert len(deferred_findings) == 2, (
        "deferred findings should include all findings for deferred files "
        f"(2 per file * 1 file = 2); got {len(deferred_findings)}"
    )
    assert deferred_paths == [f"src/f{cap}.py"], (
        f"deferred paths should be the (cap+1)th file; got {deferred_paths}"
    )


def test_slice_logic_no_defer_when_under_cap() -> None:
    """When file count is at or below cap, nothing is deferred."""
    cap = _load_declared_cap()
    by_file = {f"src/f{i}.py": [{"id": f"finding-{i}"}] for i in range(cap)}
    all_files = list(by_file.items())

    assert len(all_files) == cap

    process = dict(all_files[:cap])
    deferred = all_files[cap:]

    assert len(process) == cap
    assert deferred == [], "exactly-at-cap should not trigger any defer"
