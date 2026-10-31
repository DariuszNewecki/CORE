from __future__ import annotations

from api.v1.schemas import IntegrityBaselineResponse


# ID: 180af0c5-b5eb-48e5-a33a-300d4676b4e4
def test_IntegrityBaselineResponse():
    response = IntegrityBaselineResponse(
        label="main-baseline",
        path="src/api/v1",
        files_hashed=42,
    )

    assert response.label == "main-baseline"
    assert response.path == "src/api/v1"
    assert response.files_hashed == 42

    dumped = response.model_dump()
    assert dumped == {
        "label": "main-baseline",
        "path": "src/api/v1",
        "files_hashed": 42,
    }
