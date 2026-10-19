"""The daily promotion proposal (ADR-171): main's newest green merge since
live, high-risk changes first, one rolling branch promote/next into live."""

from __future__ import annotations

import json

import httpx
import pytest

from body.services.promotion import (
    PROMOTE_BRANCH,
    build_proposal,
    live_commit,
    publish,
    risk_class,
)
from body.services.thesis.github import GitHub


LIVE = "a" * 40
M1, M2, M3 = "1" * 40, "2" * 40, "3" * 40
FEATURE = "f" * 40


def _merge(sha: str, number: int) -> dict:
    return {
        "sha": sha,
        "commit": {"message": f"Merge pull request #{number} from o/branch\n\nx"},
    }


class _GitHub:
    def __init__(self) -> None:
        self.status = "ahead"
        # Chronological, as GitHub lists them: a feature commit, then merges.
        self.commits = [
            {"sha": FEATURE, "commit": {"message": "fix: a thing"}},
            _merge(M1, 11),
            _merge(M2, 12),
            _merge(M3, 13),
        ]
        self.ci = {M1: "success", M2: "success", M3: "success"}
        self.files = {
            11: ["infra/core-deploy", "tests/infra/test_core_deploy.py"],
            12: ["src/api/dependencies.py", ".intent/rules/a.json"],
            13: ["infra/scripts/migrations/20261019_x.sql", "README.md"],
        }
        self.branch: str | None = None
        self.live_ref: str | None = None
        self.open_pulls: list[dict] = []
        self.calls: list[tuple[str, str, dict | None]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/repos/o/r/")
        if request.url.query:
            path += "?" + request.url.query.decode()
        body = json.loads(request.content) if request.content else None
        self.calls.append((request.method, path, body))
        if path == f"compare/{LIVE}...main":
            return httpx.Response(
                200, json={"status": self.status, "commits": self.commits}
            )
        if path.startswith("commits/") and "check-runs" in path:
            sha = path.split("/")[1]
            conclusion = self.ci[sha]
            status = "in_progress" if conclusion is None else "completed"
            run = {"id": 1, "name": "ci", "status": status, "conclusion": conclusion}
            return httpx.Response(200, json={"check_runs": [run]})
        if path.startswith("pulls/") and path.endswith("/files?per_page=100"):
            number = int(path.split("/")[1])
            return httpx.Response(
                200, json=[{"filename": f} for f in self.files[number]]
            )
        if path.startswith("pulls/") and request.method == "GET" and path[6:].isdigit():
            return httpx.Response(200, json={"title": f"PR {path[6:]}"})
        if path == "git/ref/heads/live":
            if self.live_ref is None:
                return httpx.Response(404)
            return httpx.Response(200, json={"object": {"sha": self.live_ref}})
        if path == f"git/ref/heads/{PROMOTE_BRANCH}":
            if self.branch is None:
                return httpx.Response(404)
            return httpx.Response(200, json={"object": {"sha": self.branch}})
        if path.startswith("pulls?state=open"):
            return httpx.Response(200, json=self.open_pulls)
        if request.method in ("POST", "PATCH"):
            return httpx.Response(
                201, json={"html_url": "https://github.com/o/r/pull/99"}
            )
        return httpx.Response(500, json={})

    def writes(self) -> list[tuple[str, str, dict | None]]:
        return [c for c in self.calls if c[0] in ("POST", "PATCH")]


async def _build(fake: _GitHub, **kwargs):
    async with httpx.AsyncClient(transport=httpx.MockTransport(fake.handler)) as c:
        return await build_proposal(GitHub("o/r", "t", c), LIVE, **kwargs)


async def _publish(fake: _GitHub, proposal) -> str:
    async with httpx.AsyncClient(transport=httpx.MockTransport(fake.handler)) as c:
        return await publish(GitHub("o/r", "t", c), proposal)


@pytest.mark.parametrize(
    "path, kind",
    [
        ("infra/core-pipeline", "host"),
        ("infra/systemd/core-api.service", "host"),
        (".intent/rules/x.json", "law"),
        ("infra/scripts/migrations/2026.sql", "migration"),
        ("src/shared/_migrations/infra/migrations/manifest.yaml", "migration"),
        ("src/api/dependencies.py", "security"),
        ("src/body/sandbox/runner.py", "security"),
        ("src/body/governance/law_custody/writer.py", "security"),
        ("src/mind/logic/engines/ast_gate/checks/modularity_checks.py", "gates"),
        ("src/mind/governance/auditor.py", "gates"),
        (".github/workflows/core-ci.yml", "gates"),
        ("src/mind/logic/engines/ast_gate/base.py", None),
        ("src/cli/resources/law/apply.py", None),
        ("tests/body/sandbox/test_x.py", None),
        ("README.md", None),
    ],
)
def test_risk_classes(path: str, kind: str | None) -> None:
    assert risk_class(path) == kind


async def test_the_newest_green_merge_is_proposed_with_every_change() -> None:
    proposal = await _build(_GitHub())
    assert proposal.candidate == M3
    assert [c.number for c in proposal.changes] == [11, 12, 13]


async def test_a_newer_merge_without_green_ci_is_skipped_and_named() -> None:
    fake = _GitHub()
    fake.ci[M3] = None  # still running
    fake.ci[M2] = "failure"
    proposal = await _build(fake)
    assert proposal.candidate == M1
    assert [c.number for c in proposal.changes] == [11]
    assert proposal.skipped == [M3, M2]
    assert f"`{M3[:12]}`" in proposal.body()


async def test_nothing_new_or_nothing_green_proposes_nothing() -> None:
    fake = _GitHub()
    fake.status = "identical"
    assert await _build(fake) is None
    fake = _GitHub()
    fake.ci = {M1: "failure", M2: None, M3: "cancelled"}
    assert await _build(fake) is None


async def test_the_body_lists_high_risk_changes_first_in_the_adr_order() -> None:
    body = (await _build(_GitHub())).body()
    order = [
        body.index("**Host and infra changes"),
        body.index("**Law (.intent/)**"),
        body.index("**Database migrations**"),
        body.index("**Login, permissions and security**"),
        body.index("## Checks"),
        body.index("## All changes"),
        body.index("## Your decision"),
    ]
    assert order == sorted(order)
    assert "`infra/core-deploy` — #11 PR 11" in body
    assert "tests/infra" not in body.split("## Checks")[0]  # tests are not high risk


async def test_a_change_to_a_check_the_governance_engine_or_ci_is_high_risk() -> None:
    fake = _GitHub()
    fake.files[13] = [
        "src/mind/logic/engines/ast_gate/checks/purity_checks.py",
        "src/mind/governance/auditor.py",
        ".github/workflows/core-ci.yml",
    ]
    high_risk = (await _build(fake)).body().split("## Checks")[0]
    assert "**Checks and gates" in high_risk
    for path in fake.files[13]:
        assert f"`{path}` — #13 PR 13" in high_risk


async def test_the_sandbox_line_reports_the_last_post_deploy_check() -> None:
    passed = {"last": {"result": "live", "sha": LIVE}}
    body = (await _build(_GitHub(), pipeline=passed)).body()
    assert f"Last deploy (`{LIVE[:12]}`): passed" in body
    failed = {"last": {"result": "failed", "sha": LIVE, "what": "probes failed"}}
    assert "probes failed" in (await _build(_GitHub(), pipeline=failed)).body()


async def test_urgent_is_named_in_the_title() -> None:
    assert (await _build(_GitHub(), urgent=True)).title().startswith("Urgent promotion")


async def test_publish_creates_the_branch_and_opens_the_pull_request_into_live() -> (
    None
):
    fake = _GitHub()
    proposal = await _build(fake)
    fake.calls.clear()
    assert await _publish(fake, proposal) == "https://github.com/o/r/pull/99"
    (ref, pull) = fake.writes()
    assert ref == (
        "POST",
        "git/refs",
        {"ref": f"refs/heads/{PROMOTE_BRANCH}", "sha": M3},
    )
    assert pull[:2] == ("POST", "pulls")
    assert pull[2]["head"] == PROMOTE_BRANCH and pull[2]["base"] == "live"


async def test_publish_moves_the_branch_and_updates_the_open_pull_request() -> None:
    fake = _GitHub()
    fake.branch = M1
    fake.open_pulls = [{"number": 98}]
    proposal = await _build(fake)
    fake.calls.clear()
    await _publish(fake, proposal)
    (ref, pull) = fake.writes()
    assert ref == (
        "PATCH",
        f"git/refs/heads/{PROMOTE_BRANCH}",
        {"sha": M3, "force": True},
    )
    assert pull[:2] == ("PATCH", "pulls/98")
    assert set(pull[2]) == {"title", "body"}


async def test_publish_with_the_branch_already_there_only_updates_the_text() -> None:
    fake = _GitHub()
    fake.branch = M3
    fake.open_pulls = [{"number": 98}]
    proposal = await _build(fake)
    fake.calls.clear()
    await _publish(fake, proposal)
    assert [c[:2] for c in fake.writes()] == [("PATCH", "pulls/98")]


async def _live(fake: _GitHub, pipeline):
    async with httpx.AsyncClient(transport=httpx.MockTransport(fake.handler)) as c:
        return await live_commit(GitHub("o/r", "t", c), pipeline)


async def test_the_proposal_starts_from_the_deployed_commit_not_the_branch() -> None:
    # The live branch does not move without the runner's token: it lags.
    fake = _GitHub()
    fake.live_ref = "b" * 40
    assert await _live(fake, {"live": LIVE}) == (LIVE, None)
    assert not [c for c in fake.calls if "git/ref/heads/live" in c[1]]


async def test_without_the_status_the_branch_is_used_and_the_summary_says_so() -> None:
    fake = _GitHub()
    fake.live_ref = LIVE
    live, note = await _live(fake, None)
    assert live == LIVE and "could not be read" in note
    proposal = await _build(fake, note=note)
    assert "**Note:** core-pipeline's status could not be read" in proposal.body()


async def test_no_status_and_no_branch_knows_no_live_commit() -> None:
    assert await _live(_GitHub(), None) == (None, None)
