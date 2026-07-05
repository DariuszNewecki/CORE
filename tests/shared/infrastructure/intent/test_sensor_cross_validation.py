# tests/shared/infrastructure/intent/test_sensor_cross_validation.py
"""
ADR-120 D3 — IntentRepository._validate_sensor_cross_references enforces
the four cross-validation predicates fail-closed in strict mode.

Tests use a real IntentRepository instance (strict=True) with a mocked
worker-loading surface so we can inject controlled asymmetries without
touching disk.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from shared.infrastructure.intent.intent_repository import (
    ArtifactTypeRef,
    GovernanceError,
    IntentRepository,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


# ID: d2a9f0b6-e9e2-4b5b-b394-0938bf019e77
def _make_type_ref(type_id: str, supported_sensors: list[str]) -> ArtifactTypeRef:
    return ArtifactTypeRef(
        id=type_id,
        path=Path(f".intent/artifact_types/{type_id}.yaml"),
        content={"id": type_id, "supported_sensors": supported_sensors},
    )


# ID: 771bb41d-7cad-4b7d-86e8-c03e54080845
def _sensing_worker(type_ids: list[str]) -> dict[str, Any]:
    # identity.class mirrors real worker YAML structure (ADR-121 bug fix)
    return {
        "identity": {"class": "sensing"},
        "mandate": {"scope": {"artifact_type": type_ids}},
    }


# ID: a7b12440-5b69-40f7-8167-7e52c6b501ee
def _non_sensing_worker() -> dict[str, Any]:
    return {"identity": {"class": "execution"}, "mandate": {}}


# ID: 8e01fc57-ba4f-4fdf-9f31-b2e19a939f0e
def _repo_with_validation(
    artifact_type_index: dict[str, ArtifactTypeRef],
    worker_decls: dict[str, dict[str, Any]],
) -> None:
    """Call _validate_sensor_cross_references directly on a stub repo instance."""
    repo = IntentRepository.__new__(IntentRepository)
    repo._strict = True

    list_ids = [f"workers/{name}" for name in worker_decls]

    with (
        patch.object(repo, "list_workers", return_value=list_ids),
        patch.object(
            repo,
            "load_worker",
            side_effect=lambda wid: worker_decls[wid.split("/")[-1]],
        ),
    ):
        repo._validate_sensor_cross_references(artifact_type_index)


# ── Happy-path ────────────────────────────────────────────────────────────────


# ID: e76e3d0e-b0c6-4b6a-bb9e-20a2bc8d5134
def test_valid_symmetric_declarations_pass() -> None:
    """Fully symmetric declarations produce no error."""
    index = {
        "python": _make_type_ref("python", ["sensor_a"]),
    }
    workers = {
        "sensor_a": _sensing_worker(["python"]),
    }
    _repo_with_validation(index, workers)  # must not raise


def test_non_sensing_worker_is_ignored() -> None:
    """Workers with class != sensing are excluded from P3/P4 checks."""
    index = {
        "python": _make_type_ref("python", ["sensor_a"]),
    }
    workers = {
        "sensor_a": _sensing_worker(["python"]),
        "executor_w": _non_sensing_worker(),
    }
    _repo_with_validation(index, workers)  # must not raise


# ── P1: sensor listed in type but declaration absent ──────────────────────────


# ID: 1cc5aa00-4cde-41aa-b9b6-62e50de5ea2f
def test_p1_missing_sensor_declaration_raises() -> None:
    """P1: sensor in supported_sensors but no worker declaration → GovernanceError."""
    index = {
        "python": _make_type_ref("python", ["ghost_sensor"]),
    }
    workers: dict[str, dict[str, Any]] = {}

    with pytest.raises(GovernanceError, match=r"\[P1\].*ghost_sensor"):
        _repo_with_validation(index, workers)


# ── P2: sensor declaration doesn't claim the listing type ────────────────────


# ID: 90ae779d-8d60-4831-9d06-ebd7aa752d6e
def test_p2_sensor_does_not_claim_type_raises() -> None:
    """P2: sensor declaration lacks the type that lists it → GovernanceError."""
    index = {
        "python": _make_type_ref("python", ["sensor_x"]),
    }
    workers = {
        "sensor_x": _sensing_worker(["test"]),  # claims 'test', not 'python'
    }

    with pytest.raises(GovernanceError, match=r"\[P2\].*sensor_x"):
        _repo_with_validation(index, workers)


# ── P3: sensor claims unregistered artifact_type ─────────────────────────────


# ID: 8c403ddd-8879-4081-8a82-35a9a7d70744
def test_p3_sensor_claims_unregistered_type_raises() -> None:
    """P3: sensing worker claims a type not in the F-41 index → GovernanceError."""
    index: dict[str, ArtifactTypeRef] = {}  # empty — no types registered
    workers = {
        "sensor_y": _sensing_worker(["python"]),
    }

    with pytest.raises(GovernanceError, match=r"\[P3\].*sensor_y.*python"):
        _repo_with_validation(index, workers)


# ── P4: sensing worker not in the type's supported_sensors ───────────────────


# ID: d2a9f0b6-e9e2-4b5b-b394-0938b19e77
def test_p4_sensor_not_listed_in_type_raises() -> None:
    """P4: sensing worker claims a type but type doesn't list it → GovernanceError."""
    index = {
        "python": _make_type_ref("python", []),  # empty supported_sensors
    }
    workers = {
        "sensor_z": _sensing_worker(["python"]),
    }

    with pytest.raises(GovernanceError, match=r"\[P4\].*sensor_z.*python"):
        _repo_with_validation(index, workers)


# ── Lenient mode: logs instead of raises ─────────────────────────────────────


# ID: 771bb41d-7cad-4b7d-86e8-c03e54080845
def test_lenient_mode_logs_instead_of_raising(caplog: pytest.LogCaptureFixture) -> None:
    """In lenient mode (strict=False) errors are logged, not raised."""
    import logging

    index = {
        "python": _make_type_ref("python", ["ghost_sensor"]),
    }
    workers: dict[str, dict[str, Any]] = {}

    repo = IntentRepository.__new__(IntentRepository)
    repo._strict = False

    list_ids: list[str] = []

    with (
        caplog.at_level(logging.WARNING),
        patch.object(repo, "list_workers", return_value=list_ids),
        patch.object(repo, "load_worker", side_effect=lambda wid: {}),
    ):
        repo._validate_sensor_cross_references(index)  # must not raise

    assert "P1" in caplog.text
    assert "ghost_sensor" in caplog.text
