# tests/infra/test_core_pipeline.py
"""core-pipeline: deploys the promotion the governor approved (ADR-171).

The real script runs against a temporary state directory with a scripted Host:
GitHub answers and the sudo calls are simulated and recorded. These tests prove
the rules: a merge to main deploys nothing; only a promotion into ``live``
whose exact head the governor approved deploys, and exactly that head; it must
be a fast-forward of ``live`` with green CI; a failed probe rolls back and
opens an issue; ``live`` is fast-forwarded after the deploy; the only
privileged commands are core-deploy and the sandbox check.
"""

from __future__ import annotations

import datetime
import email.message
import importlib.machinery
import importlib.util
import json
import subprocess
import sys
import urllib.error
from pathlib import Path
from types import ModuleType

import pytest


REPO = Path(__file__).resolve().parents[2]
SHA = "c" * 40  # the promoted main commit
LIVE = "a" * 40  # the live commit
MAIN = "e" * 40  # main's head
GOVERNOR = "DariuszNewecki"


def _load(name: str, path: Path) -> ModuleType:
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    loader.exec_module(module)
    return module


cp = _load("core_pipeline", REPO / "infra" / "core-pipeline")


def _approval(commit: str = SHA, login: str = GOVERNOR, state: str = "APPROVED"):
    return {"user": {"login": login}, "state": state, "commit_id": commit}


class FakeHost(cp.Host):
    def __init__(self, token: str | None = "t") -> None:
        super().__init__(token=token)
        self.main = MAIN
        self.live_branch: str | None = LIVE
        self.promote: dict[str, str] = {"promote/2026-10-19": SHA}
        self.pulls = [
            {
                "number": 1200,
                "base": {"ref": "live"},
                "head": {"ref": "promote/2026-10-19", "sha": SHA},
            }
        ]
        self.reviews = [_approval()]
        self.compare = "ahead"
        self.runs = [{"status": "completed", "conclusion": "success"}]
        self.rc: dict[str, int] = {}
        self.calls: list[list[str]] = []
        self.issues: list[dict] = []
        self.ref_writes: list[tuple[str | None, str, dict]] = []
        self.ref_write_error: int | None = None
        self.ls_remote_fails = False
        self.api_calls = 0
        self.at = datetime.datetime(2026, 10, 19, 9, 0, tzinfo=datetime.UTC)
        self.limited_until: datetime.datetime | None = None

    def now(self):
        return self.at

    def run(self, cmd):
        if cmd[:2] == ["git", "ls-remote"]:
            if self.ls_remote_fails:
                return subprocess.CompletedProcess(cmd, 128, b"", b"no")
            refs = {"main": self.main, **self.promote}
            if self.live_branch:
                refs["live"] = self.live_branch
            out = "".join(f"{s}\trefs/heads/{n}\n" for n, s in refs.items())
            return subprocess.CompletedProcess(cmd, 0, out.encode(), b"")
        self.calls.append(list(cmd))
        key = (
            "rollback"
            if "--rollback" in cmd
            else cmd[-1]
            if "sandbox" in cmd[-1]
            else "deploy"
        )
        return subprocess.CompletedProcess(cmd, self.rc.get(key, 0), b"out", b"")

    def http(self, url, payload=None, method=None):
        self.api_calls += 1
        if self.limited_until is not None and self.at < self.limited_until:
            headers = email.message.Message()
            headers["X-RateLimit-Remaining"] = "0"
            headers["X-RateLimit-Reset"] = str(int(self.limited_until.timestamp()))
            raise urllib.error.HTTPError(url, 403, "rate limit exceeded", headers, None)
        if "/git/refs" in url:
            if self.ref_write_error:
                raise urllib.error.HTTPError(
                    url, self.ref_write_error, "no", email.message.Message(), None
                )
            self.ref_writes.append((method, url, payload))
            return {"object": {"sha": payload["sha"]}}
        if url.endswith("/issues"):
            self.issues.append(payload)
            return {"html_url": "https://github.com/x/issues/1"}
        if url.endswith("/branches/main"):
            return {"commit": {"sha": self.main}}
        if "/pulls?state=open&base=live" in url:
            return self.pulls
        if "/pulls/1200/reviews" in url:
            return self.reviews
        if "/compare/" in url:
            return {"status": self.compare}
        if "check-runs" in url:
            assert f"/commits/{SHA}/" in url  # CI is read on the promoted commit
            return {"check_runs": self.runs}
        raise AssertionError(url)


@pytest.fixture
def world(tmp_path: Path):
    (tmp_path / "etc").mkdir()
    conf = tmp_path / "etc" / "pipeline.conf"
    conf.write_text(f"GITHUB_REPO=DariuszNewecki/CORE\nGOVERNOR_GITHUB={GOVERNOR}\n")
    (tmp_path / "releases" / LIVE).mkdir(parents=True)
    current = tmp_path / "current"
    current.symlink_to(Path("releases") / LIVE)
    layout = cp.Layout(state_dir=tmp_path / "state", conf=conf, current=current)
    return FakeHost(), layout


def _tick(world) -> dict:
    host, layout = world
    assert cp.main([], host=host, layout=layout) == 0
    return json.loads(layout.status.read_text())


def _privileged(host: FakeHost) -> list[list[str]]:
    return [c for c in host.calls if c[0] == "sudo"]


def _later(host: FakeHost, minutes: int = 6) -> None:
    host.at += datetime.timedelta(minutes=minutes)


# -- what deploys ---------------------------------------------------------------


def test_an_approved_promotion_deploys_exactly_its_head_then_probes(world) -> None:
    host, _ = world
    status = _tick(world)
    deploy, probe = _privileged(host)
    assert deploy == [
        "sudo",
        "-n",
        cp.CORE_DEPLOY,
        SHA,
        "--migrate",
        "--merged-by",
        GOVERNOR,
    ]
    assert probe == ["sudo", "-n", "-u", "core", cp.SANDBOX_CHECK]
    assert status["last"]["result"] == "live"
    assert status["last"]["promotion"] == 1200


def test_a_merge_to_main_deploys_nothing(world) -> None:
    host, _ = world
    host.promote = {}
    host.pulls = []
    status = _tick(world)
    assert _privileged(host) == []
    assert status["state"] == "idle" and status["main_head"] == MAIN
    assert host.api_calls == 0  # an idle tick spends no API call


def test_a_promotion_without_the_governors_approval_waits(world) -> None:
    host, _ = world
    host.reviews = []
    status = _tick(world)
    assert _privileged(host) == []
    assert status["state"] == "waiting for approval"
    assert status["waiting_on"] == [SHA]


@pytest.mark.parametrize(
    "reviews",
    [
        [_approval(login="core-claude-bot")],
        [_approval(commit="f" * 40)],
        [_approval(), _approval(state="CHANGES_REQUESTED")],
        [_approval(), _approval(state="DISMISSED")],
    ],
    ids=["other-account", "older-commit", "changes-requested", "dismissed"],
)
def test_only_the_governors_standing_approval_of_the_exact_head_counts(
    world, reviews
) -> None:
    host, _ = world
    host.reviews = reviews
    _tick(world)
    assert _privileged(host) == []


def test_a_pull_request_not_from_a_promote_branch_never_deploys(world) -> None:
    host, _ = world
    host.pulls[0]["head"]["ref"] = "feature"
    _tick(world)
    assert _privileged(host) == []


def test_a_pull_request_into_another_base_never_deploys(world) -> None:
    host, _ = world
    host.pulls[0]["base"]["ref"] = "main"
    _tick(world)
    assert _privileged(host) == []


def test_an_approval_arriving_later_is_found_on_the_next_poll(world) -> None:
    host, _ = world
    host.reviews = []
    _tick(world)
    host.reviews = [_approval()]
    _later(host, 1)
    assert _tick(world)["state"] == "waiting for approval"  # within the poll
    assert _privileged(host) == []
    _later(host)
    assert _tick(world)["last"]["result"] == "live"


def test_waiting_for_approval_spends_at_most_two_calls_per_poll(world) -> None:
    host, _ = world
    host.reviews = []
    _tick(world)
    before = host.api_calls
    for _ in range(4):
        _later(host, 1)
        _tick(world)
    assert host.api_calls == before
    _later(host, 2)
    _tick(world)
    assert host.api_calls - before == 2  # open promotions, their reviews


def test_a_head_that_is_not_a_fast_forward_of_live_is_refused_once(world) -> None:
    host, _ = world
    host.compare = "diverged"
    status = _tick(world)
    assert _privileged(host) == []
    assert status["last"]["result"] == "failed"
    assert "fast-forward" in status["last"]["what"] and len(host.issues) == 1
    _later(host)
    _tick(world)
    assert len(host.issues) == 1


# -- CI -------------------------------------------------------------------------


def test_pending_ci_waits_and_retries_next_tick(world) -> None:
    host, _ = world
    host.runs = [{"status": "in_progress", "conclusion": None}]
    assert _tick(world)["state"] == "waiting for CI"
    assert _privileged(host) == []
    host.runs = [{"status": "completed", "conclusion": "success"}]
    _later(host)
    assert _tick(world)["last"]["result"] == "live"


def test_red_ci_opens_an_issue_and_never_deploys(world) -> None:
    host, _ = world
    host.runs = [{"status": "completed", "conclusion": "failure"}]
    status = _tick(world)
    assert _privileged(host) == []
    assert status["last"]["result"] == "failed" and len(host.issues) == 1


def test_a_cancelled_run_is_not_green(world) -> None:
    host, _ = world
    host.runs = [{"status": "completed", "conclusion": "cancelled"}]
    _tick(world)
    assert _privileged(host) == []


def _run(run_id: int, name: str, conclusion: str) -> dict:
    return {
        "id": run_id,
        "name": name,
        "app": {"id": 15368},
        "status": "completed",
        "conclusion": conclusion,
    }


def test_a_failed_check_rerun_green_counts_as_green(world) -> None:
    # #1133: a re-run supersedes the failed run before it.
    host, _ = world
    host.runs = [
        _run(2, "host-change-stated", "success"),
        _run(1, "host-change-stated", "failure"),
        _run(3, "tests", "success"),
    ]
    assert _tick(world)["last"]["result"] == "live"


def test_a_check_rerun_red_after_green_is_red(world) -> None:
    host, _ = world
    host.runs = [_run(1, "tests", "success"), _run(2, "tests", "failure")]
    assert _tick(world)["last"]["result"] == "failed"
    assert _privileged(host) == []


def test_same_check_name_from_another_app_is_not_superseded(world) -> None:
    host, _ = world
    other = {**_run(1, "build", "failure"), "app": {"id": 99}}
    host.runs = [other, _run(2, "build", "success")]
    assert _tick(world)["last"]["result"] == "failed"


# -- after the deploy -------------------------------------------------------------


def test_live_is_fast_forwarded_to_the_deployed_head(world) -> None:
    host, _ = world
    status = _tick(world)
    assert host.ref_writes == [
        (
            "PATCH",
            "https://api.github.com/repos/DariuszNewecki/CORE/git/refs/heads/live",
            {"sha": SHA, "force": False},
        )
    ]
    assert status["live_branch"] == SHA


def test_a_missing_live_branch_is_created_at_the_live_commit(world) -> None:
    host, _ = world
    host.live_branch = None
    host.promote = {}
    _tick(world)
    assert host.ref_writes == [
        (
            None,
            "https://api.github.com/repos/DariuszNewecki/CORE/git/refs",
            {"ref": "refs/heads/live", "sha": LIVE},
        )
    ]


def test_a_refused_ref_write_is_tried_again_only_after_the_poll(world) -> None:
    host, _ = world
    host.live_branch = None
    host.promote = {}
    host.ref_write_error = 403
    _tick(world)
    before = host.api_calls
    _later(host, 1)
    _tick(world)
    assert host.api_calls == before


def test_without_a_token_it_deploys_and_says_live_was_not_moved(
    world, tmp_path: Path
) -> None:
    _, layout = world
    host = FakeHost(token=None)
    assert cp.main([], host=host, layout=layout) == 0
    status = json.loads(layout.status.read_text())
    assert status["last"]["result"] == "live"
    assert "not moved" in status["last"]["what"]
    assert host.ref_writes == []


def test_failed_probe_rolls_back_and_opens_an_issue(world) -> None:
    host, _ = world
    host.rc[cp.SANDBOX_CHECK] = 1
    status = _tick(world)
    assert _privileged(host)[-1] == ["sudo", "-n", cp.CORE_DEPLOY, "--rollback"]
    assert "rolled back" in status["last"]["what"]
    assert len(host.issues) == 1 and host.ref_writes == []


def test_refused_deploy_opens_an_issue_and_leaves_live_alone(world) -> None:
    host, _ = world
    host.rc["deploy"] = 1
    _tick(world)
    assert len(_privileged(host)) == 1
    assert "refused" in host.issues[0]["title"] and host.ref_writes == []


def test_each_promotion_is_handled_once(world) -> None:
    host, _ = world
    host.rc["deploy"] = 1
    _tick(world)
    host.calls.clear()
    _later(host)
    _tick(world)
    assert _privileged(host) == []


# -- the runner itself --------------------------------------------------------------


def test_only_two_privileged_commands_exist() -> None:
    source = (REPO / "infra" / "core-pipeline").read_text()
    assert source.count('"sudo"') == 3  # deploy, probe, rollback
    assert cp.CORE_DEPLOY == "/usr/local/sbin/core-deploy"
    assert cp.SANDBOX_CHECK == "/usr/local/sbin/core-sandbox-check"


def test_refuses_without_the_governor_named(tmp_path: Path) -> None:
    conf = tmp_path / "pipeline.conf"
    conf.write_text("GITHUB_REPO=DariuszNewecki/CORE\n")
    layout = cp.Layout(state_dir=tmp_path / "s", conf=conf, current=tmp_path / "c")
    assert cp.main([], host=FakeHost(), layout=layout) == 1


def test_main_is_read_from_the_api_when_git_cannot_answer(world) -> None:
    host, _ = world
    host.ls_remote_fails = True
    assert _tick(world)["main_head"] == MAIN


def test_a_rate_limit_waits_for_its_reset_and_says_so(world) -> None:
    """#1065, 2026-10-15: the unauthenticated limit ran out; every tick then
    failed with HTTP 403 and the deploy stalled with state 'error'."""
    host, _ = world
    reset = host.at + datetime.timedelta(minutes=14)
    host.limited_until = reset
    status = _tick(world)
    assert status["state"] == "rate limited"
    assert status["until"] == reset.isoformat()
    calls = host.api_calls
    _later(host, 2)
    assert _tick(world)["state"] == "rate limited"
    assert host.api_calls == calls  # waiting spends nothing
    host.at = reset
    assert _tick(world)["last"]["result"] == "live"
    assert len(_privileged(host)) == 2


def test_a_forbidden_call_that_is_not_the_rate_limit_stays_an_error(world) -> None:
    host, _ = world

    def forbidden(url, payload=None, method=None):
        raise urllib.error.HTTPError(
            url, 403, "Forbidden", email.message.Message(), None
        )

    host.http = forbidden  # type: ignore[method-assign]
    assert _tick(world)["state"] == "error"


def test_waiting_for_ci_costs_one_api_call_a_tick(world) -> None:
    host, _ = world
    host.runs = [{"status": "in_progress", "conclusion": None}]
    _tick(world)
    for _ in range(3):
        before = host.api_calls
        _later(host, 1)
        assert _tick(world)["state"] == "waiting for CI"
        assert host.api_calls - before == 1
