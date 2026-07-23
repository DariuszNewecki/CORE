# tests/cli/logic/demo/test_consequence_chain_e2e.py
"""End-to-end reproduction of the ADR-155 isolated consequence chain (E01).

Exercises the real production chain, unmodified: AuditViolationSensor ->
persisted finding -> ViolationRemediatorWorker -> governed proposal ->
recorded auto-approval authority -> sandboxed fix.ids execution via the
real FastAPI /execute route (in-process ASGI) -> committed source change
-> durable consequence via the real /chain route -> re-audit -> resolved
finding. Against a disposable Postgres+Qdrant clone-of-this-repo; never
the shared LAN test database.

Marked `integration`; skipped entirely when `docker compose` (v2) isn't
available. This is the single, expensive, real-infrastructure test — the
D10 assertion *logic* itself has fast, infra-free coverage in
test_consequence_chain_assertions.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cli.logic.demo.consequence_chain import run_consequence_chain
from shared.infrastructure.git_service import GitService


pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[4]


async def test_e01_full_chain_end_to_end(
    docker_compose_available: bool, tmp_path: Path
) -> None:
    """The full, genuine consequence chain must pass every D10 assertion."""
    if not docker_compose_available:
        pytest.skip("docker compose v2 not available")

    source = GitService(REPO_ROOT)
    result = await run_consequence_chain(source, tmp_path / "demo_state")

    failed = [a.name for a in result.assertions if not a.passed]
    assert result.ok, f"chain scenario failed: {failed}"
    assert len(result.assertions) == 16  # D7 seed proof + the 15 D10 assertions
