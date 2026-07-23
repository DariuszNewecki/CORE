# tests/cli/logic/demo/test_compose_lifecycle.py
"""Integration tests for the isolated consequence-chain demo's disposable
Compose lifecycle (ADR-155 D4), exercised against real Docker per the
Phase1-Map's fixture strategy — isolation/cleanup claims are proven against
a real substrate, not mocked results.

Covers Phase1-Map U07 and E07. Skipped entirely when `docker compose` (v2)
isn't available, so unit CI without Docker still runs the rest of the
Phase 1 suite.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path

import pytest

from cli.logic.demo.isolation import compose_down, compose_up


COMPOSE_FILE = Path(__file__).resolve().parents[4] / "infra" / "demo" / "compose.yaml"


def _compose_env(project_name: str) -> dict[str, str]:
    env = {"RUN_ID": project_name}
    path = os.environ.get("PATH")
    if path:
        env["PATH"] = path
    return env


@pytest.fixture
def project_name() -> str:
    return f"core-demo-test-{uuid.uuid4().hex[:12]}"


async def _docker(args: list[str]) -> str:
    proc = await asyncio.create_subprocess_exec(
        "docker", *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, _ = await proc.communicate()
    return stdout.decode()


async def _names_labeled(project_name: str) -> list[str]:
    output = await _docker(
        [
            "ps",
            "-a",
            "--filter",
            f"label=core.demo.run_id={project_name}",
            "--format",
            "{{.Names}}",
        ]
    )
    return [n for n in output.splitlines() if n]


async def test_u07_compose_up_and_down_label_everything_with_run_id(
    docker_compose_available: bool, project_name: str
) -> None:
    if not docker_compose_available:
        pytest.skip("docker compose v2 not available")

    env = _compose_env(project_name)
    up_result = await compose_up(project_name, COMPOSE_FILE, env)
    try:
        assert up_result.returncode == 0
        names = await _names_labeled(project_name)
        assert len(names) == 2  # postgres + qdrant
        for name in names:
            assert project_name in name
    finally:
        down_result = await compose_down(project_name, COMPOSE_FILE, env)
        assert down_result.returncode == 0

    assert await _names_labeled(project_name) == []


async def test_e07_teardown_after_failure_only_removes_this_runs_resources(
    docker_compose_available: bool, project_name: str
) -> None:
    if not docker_compose_available:
        pytest.skip("docker compose v2 not available")

    other_project = f"core-demo-test-{uuid.uuid4().hex[:12]}"
    env_this = _compose_env(project_name)
    env_other = _compose_env(other_project)

    await compose_up(project_name, COMPOSE_FILE, env_this)
    await compose_up(other_project, COMPOSE_FILE, env_other)
    try:
        # Simulated failure here, after both are up — tear down only project_name.
        down_result = await compose_down(project_name, COMPOSE_FILE, env_this)
        assert down_result.returncode == 0

        assert await _names_labeled(project_name) == []
        assert len(await _names_labeled(other_project)) == 2
    finally:
        await compose_down(other_project, COMPOSE_FILE, env_other)
