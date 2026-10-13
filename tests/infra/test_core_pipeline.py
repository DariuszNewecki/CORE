# tests/infra/test_core_pipeline.py
"""core-pipeline: the post-merge runner (one-path flow, governor ruling 2026-10-12).

The real script runs against a temporary state directory with a scripted Host:
GitHub answers and the sudo calls are simulated and recorded. These tests prove
the rules: only the governor's merges deploy; CI must be green; a failed probe
rolls back and opens an issue; the only privileged commands are core-deploy
and the sandbox check.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import subprocess
import sys
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

    def run(self, cmd):
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
        if payload is not None:
            self.issues.append(payload)
            return {"html_url": "https://github.com/x/issues/1"}
        if url.endswith("/branches/main"):
            return {"commit": {"sha": self.head}}
        if url.endswith("/pulls"):
            # As GitHub answers: the per-commit list carries no merged_by.
            return [{"number": 967, "merge_commit_sha": self.head, "merged_by": None}]
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
