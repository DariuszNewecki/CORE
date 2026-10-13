# src/body/sandbox/models.py
"""
Sandbox job and result models (ADR-132 D10.10, closes R4).

A job names a snapshot (an inbox directory the client filled) and what to
run in it; a result says what happened, in two separate fields:

- ``status``: passed | failed | error | timeout | not_run
- ``completeness``: full | partial | none

Classification order (design, consolidated draft): errors and timeouts
first, then per job kind. For a test-execution job, zero executed tests is
``not_run`` whatever pytest's exit code says (exit 5 is never success), and a
run whose integration tests the sandbox excluded is ``partial``, which never
satisfies a gate that requires those tests.

CONSTITUTIONAL ALIGNMENT:
- Pure data and pure functions. No I/O.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from shared.utils.dataclass_dict import DataclassDict


JobKind = Literal["pytest"]
Status = Literal["passed", "failed", "error", "timeout", "not_run"]
Completeness = Literal["full", "partial", "none"]
Isolation = Literal["service", "local"]

# "pytest-collect" only collects (pytest --collect-only): collection imports
# every test module, which is running repository code all the same.
JOB_KINDS: tuple[str, ...] = ("pytest", "pytest-collect")
COLLECT_KIND = "pytest-collect"
MAX_TIMEOUT_SEC = 3600
INTEGRATION_MARKER = "integration"

_JOB_ID = re.compile(r"^[0-9a-f]{32}$")


# ID: ce96595c-e8bd-4e87-8e4d-f1ca59055f19
class JobRejected(ValueError):
    """A job failed validation; it is refused before anything runs."""


@dataclass(frozen=True)
# ID: d9a61f15-4b95-4f22-a7c3-d1fdc6a962c1
class SandboxJob:
    """One unit of repository code to run, against one snapshot."""

    job_id: str
    kind: str
    targets: tuple[str, ...]
    timeout_sec: int
    markers: str | None = None
    exclude_integration: bool = False
    # Measure coverage of src/ (coverage.py); the result carries it.
    coverage: bool = False

    # ID: 01ff4d11-916d-477c-8c06-61ad55280b2e
    def validate(self) -> None:
        """Refuse anything the server should not be asked to run."""
        if not _JOB_ID.match(self.job_id):
            raise JobRejected("job_id must be 32 lowercase hex characters")
        if self.kind not in JOB_KINDS:
            raise JobRejected(f"unknown job kind: {self.kind!r}")
        if not isinstance(self.timeout_sec, int) or not (
            1 <= self.timeout_sec <= MAX_TIMEOUT_SEC
        ):
            raise JobRejected(f"timeout_sec must be 1..{MAX_TIMEOUT_SEC}")
        if not self.targets:
            raise JobRejected("a pytest job names at least one target")
        for target in self.targets:
            validate_target(target)
        if self.markers is not None and (
            not self.markers.strip() or self.markers.startswith("-")
        ):
            raise JobRejected("markers must be a non-empty expression")

    # ID: adf4f8e0-252a-435b-b0ab-6504c80c5f8b
    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["targets"] = list(self.targets)
        return data

    @classmethod
    # ID: 36552ff2-362d-4801-b72e-804532ef5888
    def from_dict(cls, data: dict[str, Any]) -> SandboxJob:
        try:
            job = cls(
                job_id=str(data["job_id"]),
                kind=str(data["kind"]),
                targets=tuple(str(t) for t in data["targets"]),
                timeout_sec=data["timeout_sec"],
                markers=data.get("markers"),
                exclude_integration=bool(data.get("exclude_integration", False)),
                coverage=bool(data.get("coverage", False)),
            )
        except (KeyError, TypeError) as exc:
            raise JobRejected(f"malformed job: {exc}") from exc
        job.validate()
        return job

    # ID: 334f0482-987a-41b2-b53c-b4867b6d830e
    def effective_markers(self) -> str | None:
        """The marker expression pytest runs with, the sandbox's exclusion included."""
        if not self.exclude_integration:
            return self.markers
        excluded = f"not {INTEGRATION_MARKER}"
        return f"({self.markers}) and {excluded}" if self.markers else excluded


# ID: 62bd8e68-8d86-45de-940b-919c149dc1c7
def validate_target(target: str) -> None:
    """A pytest target is a relative path inside the snapshot, never an option."""
    path_part = target.split("::", 1)[0]
    if (
        not target
        or target.startswith("-")
        or path_part.startswith("/")
        or "\x00" in target
        or any(part == ".." for part in path_part.split("/"))
    ):
        raise JobRejected(f"target must be a relative path inside the tree: {target!r}")


@dataclass
# ID: 9becc29b-d8f6-4d09-beaf-1c183c53d723
class SandboxResult(DataclassDict):
    """What a job did. ``status`` and ``completeness`` are separate facts."""

    status: str
    completeness: str
    isolation: str
    reason: str = ""
    exit_code: int | None = None
    counts: dict[str, int] = field(default_factory=dict)
    excluded: list[str] = field(default_factory=list)
    # Node ids of the tests that passed / failed (setup failures included).
    passed_ids: list[str] = field(default_factory=list)
    failed_ids: list[str] = field(default_factory=list)
    # A coverage job: {"total": %, "files": {path: %}, "text": table} or {"error": ...}.
    coverage: dict[str, Any] = field(default_factory=dict)
    stdout: str = ""
    stderr: str = ""
    output_truncated: bool = False
    duration_sec: float = 0.0
    snapshot_sha256: str = ""

    @property
    # ID: 4fa3c5d8-c004-423e-9e99-44dfea19785f
    def ok(self) -> bool:
        """True only for a full pass. ``partial`` and ``not_run`` are never ok."""
        return self.status == "passed" and self.completeness == "full"

    @classmethod
    # ID: c5557f66-88e8-49fe-bd30-7824007816c9
    def from_dict(cls, data: dict[str, Any]) -> SandboxResult:
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})

    @classmethod
    # ID: f3e1a26b-4b09-4a4f-87f2-68330f2ad077
    def not_run(cls, isolation: str, reason: str) -> SandboxResult:
        """The job did not run. Never read as a pass (lessons register L1)."""
        return cls(
            status="not_run", completeness="none", isolation=isolation, reason=reason
        )


# ID: c606e0b0-bc71-415e-94ef-02ead953f95b
def classify_pytest(
    *,
    exit_code: int | None,
    timed_out: bool,
    report: dict[str, Any] | None,
    exclude_integration: bool,
    collect_only: bool = False,
) -> tuple[str, str, str]:
    """(status, completeness, reason) for a pytest job, in the design's order."""
    if timed_out:
        return "timeout", "none", "the job outlived its timeout"
    if report is None:
        return "error", "none", "the bootstrap produced no report"
    if collect_only:
        return _classify_collection(exit_code, report)
    if report.get("error"):
        return "error", "none", str(report["error"])
    counts = report.get("counts", {})
    executed = int(counts.get("executed", 0))
    if executed == 0:
        if report.get("excluded"):
            return "not_run", "none", "every selected test was excluded by the sandbox"
        return "not_run", "none", "no test was executed"
    if exit_code not in (0, 1):
        return "error", "none", f"pytest exited {exit_code}"
    if int(counts.get("failed", 0)) > 0 or exit_code == 1:
        status = "failed"
    else:
        status = "passed"
    partial = exclude_integration and bool(report.get("excluded"))
    return status, ("partial" if partial else "full"), ""


def _classify_collection(
    exit_code: int | None, report: dict[str, Any]
) -> tuple[str, str, str]:
    """A collect-only job: collected cleanly, failed to collect, or nothing."""
    if report.get("error"):
        return "error", "none", str(report["error"])
    collected = int(report.get("counts", {}).get("collected", 0))
    if exit_code == 0:
        return "passed", "full", f"{collected} tests collected"
    if exit_code == 5:
        return "not_run", "none", "no tests were collected"
    if exit_code in (1, 2):
        return "failed", "full", "collection errors"
    return "error", "none", f"pytest exited {exit_code}"
