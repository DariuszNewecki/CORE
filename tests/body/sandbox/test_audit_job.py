# tests/body/sandbox/test_audit_job.py
"""The sandbox's audit job (external review F1).

assisted.validate_diff judges a patch with the patched tree's own engine,
which runs candidate code. That now happens only as a sandbox job: these
tests run the real bootstrap on a tiny snapshot whose "engine" is candidate
code, through the runner and the service handler, and check that
repo_audit never starts it outside the sandbox service and never reads a
result from elsewhere as evidence.
"""

from __future__ import annotations

import getpass
import socket
import threading
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from body.sandbox import repo_audit
from body.sandbox.models import JobRejected, SandboxJob, SandboxResult, classify_audit
from body.sandbox.protocol import encode, recv_message
from body.sandbox.runner import run_job
from body.sandbox.server import handle_connection


# A candidate "engine": the per-rule audit the bootstrap imports from the
# snapshot's own src/.
_ENGINE = {
    "mind/__init__.py": "",
    "mind/governance/__init__.py": "",
    "mind/governance/audit_context.py": (
        "class AuditorContext:\n"
        "    def __init__(self, root, stateless=False):\n"
        "        self.root, self.stateless = root, stateless\n"
    ),
    "mind/governance/filtered_audit.py": (
        "async def run_filtered_audit(actx, rule_ids, files):\n"
        "    assert actx.stateless\n"
        "    return [{'check_id': r, 'file_path': 'src/x.py'} for r in rule_ids], 0, 0\n"
    ),
}


def _snapshot(root: Path, src: dict[str, str]) -> Path:
    for rel, body in src.items():
        path = root / "src" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return root


def _audit_job(rules: tuple[str, ...] = (), **kw: object) -> SandboxJob:
    return SandboxJob(
        job_id="a" * 32,
        kind="audit",
        targets=(),
        timeout_sec=60,
        audit_rules=rules,
        **kw,  # type: ignore[arg-type]
    )


# --- the job ---------------------------------------------------------------


# ID: 7ce037b2-08bd-477d-894d-709a05d4edef
def test_audit_job_validation() -> None:
    _audit_job(("modularity.needs_split",)).validate()
    _audit_job().validate()  # the full audit names no rule
    with pytest.raises(JobRejected):
        _audit_job(("not a rule; rm -rf /",)).validate()
    with pytest.raises(JobRejected):
        _audit_job(markers="slow").validate()
    with pytest.raises(JobRejected):
        SandboxJob(
            job_id="a" * 32,
            kind="pytest",
            targets=("tests",),
            timeout_sec=60,
            audit_rules=("x.y",),
        ).validate()
    job = _audit_job(("a.b",))
    assert SandboxJob.from_dict(job.to_dict()) == job


# ID: 87ea0d5a-48a0-438e-aa43-fabe983d8642
def test_classify_audit() -> None:
    ok = {"audit": {"findings": []}, "error": None}
    assert classify_audit(exit_code=0, timed_out=False, report=ok)[:2] == (
        "passed",
        "full",
    )
    assert classify_audit(exit_code=0, timed_out=True, report=ok)[0] == "timeout"
    assert classify_audit(exit_code=0, timed_out=False, report=None)[0] == "error"
    assert (
        classify_audit(exit_code=1, timed_out=False, report={"audit": None})[0]
        == "error"
    )
    bad = {"audit": {}, "error": "candidate_not_loaded: mind came from /elsewhere"}
    assert classify_audit(exit_code=0, timed_out=False, report=bad)[0] == "error"


# --- the real bootstrap, through the runner and the service ------------------


# ID: 4b098eb4-260e-40e8-a833-3e9e07ba02f3
def test_audit_job_runs_the_snapshots_own_engine(scratch: Path) -> None:
    snap = _snapshot(scratch / "snap", _ENGINE)
    (scratch / "work").mkdir()
    result = run_job(
        _audit_job(("rule.a", "rule.b")),
        snapshot_dir=snap,
        work_dir=scratch / "work",
        isolation="local",
    )
    assert (result.status, result.completeness) == ("passed", "full"), result.stderr
    assert [f["check_id"] for f in result.audit["findings"]] == ["rule.a", "rule.b"]


# ID: a69bfd6f-0882-47d7-9d48-06651ff1b724
def test_an_audit_that_raises_is_an_error_never_a_result(scratch: Path) -> None:
    broken = dict(_ENGINE)
    broken["mind/governance/filtered_audit.py"] = (
        "async def run_filtered_audit(actx, rule_ids, files):\n"
        "    raise RuntimeError('engine broke')\n"
    )
    snap = _snapshot(scratch / "snap", broken)
    (scratch / "work").mkdir()
    result = run_job(
        _audit_job(("rule.a",)),
        snapshot_dir=snap,
        work_dir=scratch / "work",
        isolation="local",
    )
    assert result.status == "error" and not result.ok
    assert "engine broke" in result.reason
    assert result.audit == {}


def test_the_service_runs_an_audit_job(scratch: Path) -> None:
    inbox = scratch / "inbox"
    _snapshot(inbox / ("a" * 32), _ENGINE)
    (scratch / "work").mkdir()
    server_sock, client_sock = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    env = {
        "CORE_SANDBOX_INBOX_ROOT": str(inbox),
        "CORE_SANDBOX_WORK_ROOT": str(scratch / "work"),
        "CORE_SANDBOX_CLIENT_USER": getpass.getuser(),
    }
    thread = threading.Thread(target=handle_connection, args=(server_sock, env))
    thread.start()
    client_sock.sendall(encode({"job": _audit_job(("rule.a",)).to_dict()}))
    try:
        reply = recv_message(client_sock, 8 * 1024 * 1024)["result"]
    finally:
        thread.join(timeout=120)
        client_sock.close()
        server_sock.close()
    assert (reply["status"], reply["isolation"]) == ("passed", "service")
    assert reply["audit"]["findings"][0]["check_id"] == "rule.a"


# --- repo_audit: only the sandbox service's result is evidence --------------


async def test_outside_service_mode_the_audit_never_starts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CORE_SANDBOX_MODE", "local")
    with patch.object(repo_audit, "run_repo_code") as run_repo_code:
        result = await repo_audit.run_audit_in_sandbox(tmp_path, rule_ids=["a.b"])
    run_repo_code.assert_not_called()
    assert result.status == "not_run" and result.isolation == "local"
    audit, error = repo_audit.isolated_audit(result)
    assert audit is None and "isolation 'local'" in (error or "")


async def test_service_mode_sends_an_audit_job(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CORE_SANDBOX_MODE", "service")
    done = SandboxResult(status="passed", completeness="full", isolation="service")
    with (
        patch(
            "shared.infrastructure.bootstrap_registry.BootstrapRegistry.get_repo_path",
            return_value=tmp_path,
        ),
        patch.object(
            repo_audit, "run_repo_code", AsyncMock(return_value=done)
        ) as run_repo_code,
    ):
        await repo_audit.run_audit_in_sandbox(
            tmp_path, rule_ids=["a.b"], check_files=["tests/test_x.py"]
        )
    request = run_repo_code.await_args.args[0]
    assert request.audit is True
    assert request.audit_rules == ("a.b",)
    assert request.targets == ("tests/test_x.py",)
    assert run_repo_code.await_args.kwargs["mode"] == "service"


@pytest.mark.parametrize(
    ("result", "evidence"),
    [
        (
            SandboxResult(
                status="passed",
                completeness="full",
                isolation="service",
                audit={"verdict": "PASS"},
            ),
            True,
        ),
        (
            SandboxResult(
                status="passed",
                completeness="full",
                isolation="local",
                audit={"verdict": "PASS"},
            ),
            False,
        ),
        (SandboxResult.not_run("service", "sandbox service unavailable"), False),
        (
            SandboxResult(status="error", completeness="none", isolation="service"),
            False,
        ),
    ],
    ids=["service-pass", "local-pass", "service-unavailable", "service-error"],
)
def test_only_a_finished_service_audit_is_evidence(
    result: SandboxResult, evidence: bool
) -> None:
    audit, error = repo_audit.isolated_audit(result)
    assert (audit is not None) is evidence
    assert (error is None) is evidence
