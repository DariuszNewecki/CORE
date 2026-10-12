# tests/shared/infrastructure/test_repo_code.py
"""The seam Mind uses to have repository code collected in the sandbox."""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.infrastructure import repo_code
from shared.infrastructure.repo_code import CollectOutcome


# ID: 10a90040-5180-459b-90b8-3252f7dafa44
def test_register_and_get(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(repo_code, "_collector", None)
    assert repo_code.get_test_collector() is None

    async def collector(tree: Path, timeout_sec: int) -> CollectOutcome:
        return CollectOutcome("passed")

    repo_code.register_test_collector(collector)
    assert repo_code.get_test_collector() is collector


# ID: b2c29cc2-50a7-4d33-8ba3-c2686181b298
def test_loading_the_service_registry_installs_the_sandbox_collector() -> None:
    # Every service process loads the service registry; that is what makes
    # pytest_check reachable for the auditor.
    import body.services.service_registry  # noqa: F401
    from body.sandbox.repo_tests import collect_tests

    assert repo_code.get_test_collector() is collect_tests
