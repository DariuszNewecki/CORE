"""#957: an adopter project that does not declare the substrate-enforcement
taxonomy uses the built-in PASSIVE_ALIASES quietly; a declared but unreadable
taxonomy still warns."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mind.logic.engines import registry as registry_module
from mind.logic.engines.registry import EngineRegistry


def _run_with(repo: MagicMock) -> None:
    with (
        patch.object(EngineRegistry, "_path_resolver", MagicMock()),
        patch(
            "shared.infrastructure.intent.intent_repository.get_intent_repository",
            return_value=repo,
        ),
        patch.object(
            registry_module, "PASSIVE_ALIASES", set(registry_module.PASSIVE_ALIASES)
        ),
    ):
        EngineRegistry._load_passive_aliases_from_taxonomy()


# ID: 7bf9228a-c189-4aec-b3fd-cf9bdb0cb795
def test_absent_taxonomy_is_quiet(caplog: pytest.LogCaptureFixture) -> None:
    repo = MagicMock()
    repo.has_policy.return_value = False
    with caplog.at_level("DEBUG"):
        _run_with(repo)
    repo.load_policy.assert_not_called()
    assert not [r for r in caplog.records if r.levelno >= 30]


# ID: a2670854-72a3-4a3b-9607-543db76ba9b5
def test_declared_but_unreadable_taxonomy_still_warns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    repo = MagicMock()
    repo.has_policy.return_value = True
    repo.load_policy.side_effect = RuntimeError("bad yaml")
    with caplog.at_level("DEBUG"):
        _run_with(repo)
    assert any(
        r.levelno == 30 and "substrate_enforcement" in r.getMessage()
        for r in caplog.records
    )
