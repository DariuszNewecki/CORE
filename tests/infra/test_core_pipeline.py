# tests/infra/test_core_pipeline.py
"""core-pipeline: the post-merge runner (one-path flow, governor ruling 2026-10-12).

The real script runs against a temporary state directory with a scripted Host:
GitHub answers and the sudo calls are simulated and recorded. These tests prove
the rules: only the governor's merges deploy; CI must be green; a failed probe
rolls back and opens an issue; the only privileged commands are core-deploy
and the sandbox check.
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
SHA = "c" * 40
LIVE = "a" * 40
HEAD = "d" * 40


def _load(name: str, path: Path) -> ModuleType:
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    loader.exec_module(module)
    return module


cp = _load("core_pipeline", REPO / "infra" / "core-pipeline")


class FakeHost(cp.Host):
    def __init__(self) -> None:
        super().__init__(token="t")
        self.head = SHA
        self.merger = "DariuszNewecki"
        self.runs = [{"status": "completed", "conclusion": "success"}]
        self.rc: dict[str, int] = {}
        self.calls: list[list[str]] = []
        self.issues: list[dict] = []
        self.same_tree = True
        self.ci_asked: list[str] = []
        self.ls_remote = 0
        self.api_heads = 0
        self.reviews: list[dict] = []
        self.api_calls = 0
        self.at = datetime.datetime(2026, 10, 15, 16, 55, tzinfo=datetime.UTC)
        self.limited_until: datetime.datetime | None = None

    def now(self):
        return self.at

    def run(self, cmd):
        if cmd[:2] == ["git", "ls-remote"]:
            self.ls_remote += 1
            out = f"{self.head}\trefs/heads/main\n".encode() if self.head else b""
            return subprocess.CompletedProcess(cmd, 0, out, b"")
        self.calls.append(list(cmd))
        key = (
            "rollback"
            if "--rollback" in cmd
            else cmd[-1]
            if "sandbox" in cmd[-1]
            else "deploy"
        )
        return subprocess.CompletedProcess(cmd, self.rc.get(key, 0), b"out", b"")

    def http(self, url, payload=None):
        self.api_calls += 1
        if self.limited_until is not None and self.at < self.limited_until:
            headers = email.message.Message()
            headers["X-RateLimit-Remaining"] = "0"
            headers["X-RateLimit-Reset"] = str(int(self.limited_until.timestamp()))
            raise urllib.error.HTTPError(url, 403, "rate limit exceeded", headers, None)
        if payload is not None:
            self.issues.append(payload)
            return {"html_url": "https://github.com/x/issues/1"}
        if url.endswith("/branches/main"):
            self.api_heads += 1
            return {"commit": {"sha": self.head}}
        if url.endswith("/pulls"):
            # As GitHub answers: the per-commit list carries no merged_by.
            return [{"number": 967, "merge_commit_sha": self.head, "merged_by": None}]
        if "/pulls/967/reviews" in url:
            return self.reviews
        if url.endswith("/pulls/967"):
            return {
                "merged_by": {"login": self.merger} if self.merger else None,
                "head": {"sha": HEAD},
            }
        if "/git/commits/" in url:
            sha = url.rsplit("/", 1)[1]
            return {"tree": {"sha": "t" if self.same_tree else f"t-{sha}"}}
        if "check-runs" in url:
            self.ci_asked.append(url.split("/commits/")[1].split("/")[0])
            return {"check_runs": self.runs}
        raise AssertionError(url)


@pytest.fixture
def world(tmp_path: Path):
    (tmp_path / "etc").mkdir()
    conf = tmp_path / "etc" / "pipeline.conf"
    conf.write_text("GITHUB_REPO=DariuszNewecki/CORE\nGOVERNOR_GITHUB=DariuszNewecki\n")
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


def test_a_governor_merge_deploys_then_probes(world) -> None:
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
        "DariuszNewecki",
        "--tested-as",
        HEAD,
    ]
    assert probe == ["sudo", "-n", "-u", "core", cp.SANDBOX_CHECK]
    assert status["last"]["result"] == "live"


def test_a_merge_by_anyone_else_is_skipped_and_logged(world) -> None:
    host, layout = world
    host.merger = "core-claude-bot"
    status = _tick(world)
    assert _privileged(host) == []
    assert status["last"]["result"] == "skipped"
    assert "core-claude-bot" in (layout.logs / f"{SHA[:12]}.log").read_text()


def test_a_direct_push_with_no_pull_request_is_skipped(world) -> None:
    host, _ = world
    host.http = lambda url, payload=None: (  # type: ignore[method-assign]
        [] if url.endswith("/pulls") else FakeHost.http(host, url, payload)
    )
    status = _tick(world)
    assert _privileged(host) == []
    assert status["last"]["result"] == "skipped"


def test_pending_ci_waits_and_retries_next_tick(world) -> None:
    host, _ = world
    host.runs = [{"status": "in_progress", "conclusion": None}]
    assert _tick(world)["state"] == "waiting for CI"
    assert _privileged(host) == []
    host.runs = [{"status": "completed", "conclusion": "success"}]
    assert _tick(world)["last"]["result"] == "live"


def test_red_ci_opens_an_issue_and_never_deploys(world) -> None:
    host, _ = world
    host.runs = [{"status": "completed", "conclusion": "failure"}]
    status = _tick(world)
    assert _privileged(host) == []
    assert status["last"]["result"] == "failed" and len(host.issues) == 1


def _run(run_id: int, name: str, conclusion: str) -> dict:
    return {
        "id": run_id,
        "name": name,
        "app": {"id": 15368},
        "status": "completed",
        "conclusion": conclusion,
    }


def test_a_failed_check_rerun_green_counts_as_green(world) -> None:
    # #1133: editing the PR description re-ran host-change-stated green; the
    # superseded failed run stays on the commit and must not make CI red.
    host, _ = world
    host.runs = [
        _run(2, "host-change-stated", "success"),
        _run(1, "host-change-stated", "failure"),
        _run(3, "tests", "success"),
    ]
    assert _tick(world)["last"]["result"] == "live"


def test_a_check_rerun_red_after_green_is_red(world) -> None:
    host, _ = world
    host.runs = [
        _run(1, "tests", "success"),
        _run(2, "tests", "failure"),
    ]
    status = _tick(world)
    assert _privileged(host) == []
    assert status["last"]["result"] == "failed"


def test_same_check_name_from_another_app_is_not_superseded(world) -> None:
    host, _ = world
    other = {**_run(1, "build", "failure"), "app": {"id": 99}}
    host.runs = [other, _run(2, "build", "success")]
    assert _tick(world)["last"]["result"] == "failed"


def test_failed_probe_rolls_back_and_opens_an_issue(world) -> None:
    host, _ = world
    host.rc[cp.SANDBOX_CHECK] = 1
    status = _tick(world)
    assert _privileged(host)[-1] == ["sudo", "-n", cp.CORE_DEPLOY, "--rollback"]
    assert "rolled back" in status["last"]["what"]
    assert len(host.issues) == 1


def test_refused_deploy_opens_an_issue_without_rolling_back(world) -> None:
    host, _ = world
    host.rc["deploy"] = 1
    _tick(world)
    assert len(_privileged(host)) == 1
    assert "refused" in host.issues[0]["title"]


def test_each_merge_is_handled_once(world) -> None:
    host, _ = world
    _tick(world)
    host.calls.clear()
    _tick(world)
    assert _privileged(host) == []


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


def test_a_merge_skipped_while_github_settles_is_deployed_next_tick(world) -> None:
    """2026-10-12: PR #967's merge was read 6s after merging with no merger
    and skipped for good. A skipped head is now looked at again."""
    host, layout = world
    host.merger = None
    assert _tick(world)["last"]["result"] == "skipped"
    host.merger = "DariuszNewecki"
    assert _tick(world)["last"]["result"] == "live"
    log = (layout.logs / f"{SHA[:12]}.log").read_text()
    assert log.count("skipped") == 1


def test_a_known_other_merger_is_logged_once(world) -> None:
    host, layout = world
    host.merger = "core-claude-bot"
    _tick(world)
    _tick(world)
    assert _privileged(host) == []
    log = (layout.logs / f"{SHA[:12]}.log").read_text()
    assert log.count("skipped") == 1


def test_the_retry_never_deploys_a_head_no_governor_merged(world) -> None:
    """main's 34a314ee was pushed with no pull request. The runner looks at a
    skipped head again on every tick (so a merge read too early is not lost),
    and that retry must never turn into a deploy for anything but a merge by
    the governor."""
    host, layout = world
    host.http = lambda url, payload=None: (  # type: ignore[method-assign]
        [] if url.endswith("/pulls") else FakeHost.http(host, url, payload)
    )
    for _ in range(5):
        status = _tick(world)
        assert status["last"]["result"] == "skipped"
    assert _privileged(host) == []
    host.merger = "core-claude-bot"
    host.http = lambda url, payload=None: FakeHost.http(host, url, payload)  # type: ignore[method-assign]
    for _ in range(3):
        assert _tick(world)["last"]["result"] == "skipped"
    assert _privileged(host) == []
    log = (layout.logs / f"{SHA[:12]}.log").read_text()
    assert log.count("skipped") == 2  # once per distinct reason, not per tick


def test_a_pr_behind_main_waits_for_ci_on_the_merge_commit(world) -> None:
    """'Require branches up to date' is off (governor 2026-10-13): the merge
    then holds code no PR run tested, so the runner waits for CI's run on the
    merge commit itself and deploys without --tested-as."""
    host, _ = world
    host.same_tree = False
    status = _tick(world)
    assert host.ci_asked == [SHA]
    deploy = _privileged(host)[0]
    assert "--tested-as" not in deploy
    assert status["last"]["result"] == "live"


def test_an_up_to_date_pr_is_covered_by_its_own_ci_run(world) -> None:
    host, _ = world
    _tick(world)
    assert host.ci_asked == [HEAD]
    assert _privileged(host)[0][-2:] == ["--tested-as", HEAD]


def test_the_head_check_costs_no_api_call(world) -> None:
    """Every tick reads the branch head; the unauthenticated API allows 60
    calls an hour, and on 2026-10-13 a day of merges ran out of them and
    stalled a deploy. git ls-remote has no such limit."""
    host, _ = world
    host.head = LIVE  # nothing new: an idle tick
    status = _tick(world)
    assert status["state"] == "idle"
    assert host.ls_remote == 1
    assert host.api_heads == 0


def test_the_api_answers_when_git_cannot(world) -> None:
    host, _ = world
    real_run = host.run

    def failing_ls_remote(cmd):
        if cmd[:2] == ["git", "ls-remote"]:
            return subprocess.CompletedProcess(cmd, 128, b"", b"fatal")
        return real_run(cmd)

    host.run = failing_ls_remote  # type: ignore[method-assign]
    host.head = LIVE
    assert _tick(world)["state"] == "idle"
    assert host.api_heads == 1


def _review(login: str, state: str, commit: str = HEAD) -> dict:
    return {"user": {"login": login}, "state": state, "commit_id": commit}


def test_an_auto_merge_after_the_governors_approval_of_the_head_deploys(world) -> None:
    """Governor ruling 2026-10-13: approving the exact last commit is the
    decision; whoever then clicks merge (auto-merge) adds nothing."""
    host, layout = world
    host.merger = "core-claude-bot"
    host.reviews = [_review("DariuszNewecki", "APPROVED")]
    status = _tick(world)
    assert status["last"]["result"] == "live"
    deploy = _privileged(host)[0]
    assert deploy[deploy.index("--merged-by") + 1] == "DariuszNewecki"
    assert "core-claude-bot" in (layout.logs / f"{SHA[:12]}.log").read_text()


@pytest.mark.parametrize(
    "reviews",
    [
        [],
        [_review("someone-with-write-access", "APPROVED")],
        [_review("DariuszNewecki", "APPROVED", commit="e" * 40)],  # older commit
        [
            _review("DariuszNewecki", "APPROVED"),
            _review("DariuszNewecki", "CHANGES_REQUESTED"),
        ],
        [_review("DariuszNewecki", "APPROVED"), _review("DariuszNewecki", "DISMISSED")],
    ],
)
def test_no_governor_approval_of_the_head_never_deploys(world, reviews) -> None:
    host, _ = world
    host.merger = "core-claude-bot"
    host.reviews = reviews
    assert _tick(world)["last"]["result"] == "skipped"
    assert _privileged(host) == []


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
    host.at += datetime.timedelta(minutes=2)
    assert _tick(world)["state"] == "rate limited"
    assert host.api_calls == calls  # waiting spends nothing
    host.at = reset
    assert _tick(world)["last"]["result"] == "live"
    assert len(_privileged(host)) == 2


def test_a_forbidden_call_that_is_not_the_rate_limit_stays_an_error(world) -> None:
    host, _ = world

    def forbidden(url, payload=None):
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
        assert _tick(world)["state"] == "waiting for CI"
        assert host.api_calls - before == 1


def test_a_head_merged_by_someone_else_is_read_once(world) -> None:
    """An auto-merge without the governor's approval was read again on every
    tick: three calls each two minutes, more than the hourly limit."""
    host, _ = world
    host.merger = "core-claude-bot"
    _tick(world)
    before = host.api_calls
    for _ in range(3):
        assert _tick(world)["last"]["result"] == "skipped"
    assert host.api_calls == before


def test_a_head_no_pull_request_explains_is_dropped_after_the_settle_window(
    world,
) -> None:
    host, _ = world
    host.http = lambda url, payload=None: (  # type: ignore[method-assign]
        [] if url.endswith("/pulls") else FakeHost.http(host, url, payload)
    )
    calls = 0
    real_http = host.http

    def counting(url, payload=None):
        nonlocal calls
        calls += 1
        return real_http(url, payload)

    host.http = counting  # type: ignore[method-assign]
    _tick(world)
    host.at += datetime.timedelta(minutes=10)
    _tick(world)
    assert calls == 2  # still settling: looked at again
    host.at += cp.SETTLE
    for _ in range(3):
        assert _tick(world)["last"]["result"] == "skipped"
    assert calls == 2
    assert _privileged(host) == []
