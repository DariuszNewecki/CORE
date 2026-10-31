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


from api.v1.schemas import ImportViolation, QualityImportsResponse


# ID: 007037f8-a3fa-47ad-8f5f-1c51de3fdedb
def test_QualityImportsResponse() -> None:

    violation_fields = set(ImportViolation.model_fields.keys())

    violation_kwargs: dict = {}
    for field_name, field_info in ImportViolation.model_fields.items():
        annotation = field_info.annotation
        if annotation is str or annotation == str:
            violation_kwargs[field_name] = "value"
        elif annotation is int or annotation == int:
            violation_kwargs[field_name] = 42
        else:
            violation_kwargs[field_name] = "value"

    violation_kwargs["file"] = "src/api/v1/schemas.py"
    if "line" in violation_fields:
        violation_kwargs["line"] = 42
    if "message" in violation_fields:
        violation_kwargs["message"] = "relative import detected"
    if "rule" in violation_fields:
        violation_kwargs["rule"] = "no-relative-imports"

    response = QualityImportsResponse(
        status="ok",
        violations=[violation_kwargs],
    )

    assert response.status == "ok"
    assert len(response.violations) == 1
    assert isinstance(response.violations[0], ImportViolation)
    assert response.model_dump()["status"] == "ok"
