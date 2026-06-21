# tests/shared/infrastructure/intent/test_document_corpus_cross_validation.py
"""ADR-121 — IntentRepository cross-validation for document_corpus type.

Test 7 from the ADR-121 verification matrix:
  Fully symmetric declaration (document_corpus ↔ document_corpus_sensor) passes
  _validate_sensor_cross_references without raising GovernanceError.

Uses the same mocked surface as test_sensor_cross_validation.py (ADR-120 D3):
no disk access; worker declarations and artifact types injected inline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

from shared.infrastructure.intent.intent_repository import (
    ArtifactTypeRef,
    IntentRepository,
)


# ── Helpers (mirrors test_sensor_cross_validation pattern) ────────────────────


# ID: c6b97b91-a567-4cbf-84f9-cc5b6c14b09b
def _make_type_ref(type_id: str, supported_sensors: list[str]) -> ArtifactTypeRef:
    return ArtifactTypeRef(
        id=type_id,
        path=Path(f".intent/artifact_types/{type_id}.yaml"),
        content={"id": type_id, "supported_sensors": supported_sensors},
    )


# ID: 54d388ac-8581-4847-96c7-e46fb318d5f1
def _sensing_worker_decl(type_ids: list[str]) -> dict[str, Any]:
    """Sensing worker declaration using identity.class (ADR-121 bug fix verified)."""
    return {
        "identity": {"class": "sensing"},
        "mandate": {"scope": {"artifact_type": type_ids}},
    }


# ID: 07d3d12b-f514-4030-9935-29050172a491
def _run_cross_validation(
    artifact_type_index: dict[str, ArtifactTypeRef],
    worker_decls: dict[str, dict[str, Any]],
) -> None:
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


# ── Test 7 ────────────────────────────────────────────────────────────────────


def test_document_corpus_cross_validation_symmetric() -> None:
    """Test 7 (ADR-121): document_corpus type + document_corpus_sensor worker
    form a fully symmetric pair — no GovernanceError raised."""
    index = {
        "document_corpus": _make_type_ref(
            "document_corpus", ["document_corpus_sensor"]
        ),
    }
    workers = {
        "document_corpus_sensor": _sensing_worker_decl(["document_corpus"]),
    }
    _run_cross_validation(index, workers)  # must not raise
