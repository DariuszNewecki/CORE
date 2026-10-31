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


# ID: 166961b7-e015-4102-8931-8e6bfe09e3c0
def test_ImportViolation():
    violation = ImportViolation(
        file="src/api/v1/schemas.py",
        line=42,
        rule="no-relative-imports",
        message="Relative import 'from .foo import bar' is not allowed.",
    )

    assert violation.file == "src/api/v1/schemas.py"
    assert violation.line == 42
    assert violation.rule == "no-relative-imports"
    assert violation.message == "Relative import 'from .foo import bar' is not allowed."

    dumped = violation.model_dump()
    assert dumped == {
        "file": "src/api/v1/schemas.py",
        "line": 42,
        "rule": "no-relative-imports",
        "message": "Relative import 'from .foo import bar' is not allowed.",
    }


from api.v1.schemas import LintResponse, LintToolResult


# ID: 73ca1438-6f9d-4ab8-9b70-120d96b16760
def test_LintResponse():
    tool_result = LintToolResult(
        ok=True,
        returncode=0,
        stdout="no issues",
        stderr="",
    )
    response = LintResponse(ok=True, tools={"black": tool_result})

    assert response.ok is True
    assert response.tools == {"black": tool_result}
    assert response.error is None

    dumped = response.model_dump()
    assert dumped["ok"] is True
    assert "black" in dumped["tools"]
    assert dumped["error"] is None


from api.v1.schemas import IntegrateResponse


# ID: 3e3d1ffe-f5b2-4c4b-9686-be38b320d035
def test_IntegrateResponse():
    resp = IntegrateResponse(ok=True, message="integration complete", exit_code=0)

    assert resp.ok is True
    assert resp.message == "integration complete"
    assert resp.error is None
    assert resp.exit_code == 0

    dumped = resp.model_dump()
    assert dumped == {
        "ok": True,
        "message": "integration complete",
        "error": None,
        "exit_code": 0,
    }


from api.v1.schemas import IntegrityVerifyResponse


# ID: 3fd727a0-6b6b-4dbd-a262-c002e8505164
def test_IntegrityVerifyResponse():
    response = IntegrityVerifyResponse(
        label="image-abc",
        ok=True,
        errors=[],
        checked_at="2024-01-01T00:00:00Z",
    )

    assert response.label == "image-abc"
    assert response.ok is True
    assert response.errors == []
    assert response.checked_at == "2024-01-01T00:00:00Z"

    defaulted = IntegrityVerifyResponse(
        label="image-xyz", ok=False, errors=["missing digest"]
    )
    assert defaulted.checked_at is None
    assert defaulted.errors == ["missing digest"]


from api.v1.schemas import CensusDiffResponse


# ID: 2424da4a-e49c-4e5b-88c8-98e4f4a8d5a6
def test_CensusDiffResponse():
    diff_payload = {"added": ["a"], "removed": ["b"], "changed": ["c"]}
    response = CensusDiffResponse(
        available=True,
        baseline="2024-01-01",
        diff=diff_payload,
    )

    assert response.available is True
    assert response.error is None
    assert response.baseline == "2024-01-01"
    assert response.diff == diff_payload

    dumped = response.model_dump()
    assert dumped["available"] is True
    assert dumped["baseline"] == "2024-01-01"
    assert dumped["diff"] == diff_payload


# ID: 48c683d8-8f55-40f2-8c05-e4677d9cfc40
def test_CensusBaselineListResponse():
    from api.v1.schemas import CensusBaselineItem, CensusBaselineListResponse

    baseline = CensusBaselineItem.model_construct()
    response = CensusBaselineListResponse(count=1, baselines=[baseline])

    assert response.count == 1
    assert len(response.baselines) == 1
    assert response.baselines[0] is baseline


from api.v1.schemas import CensusBaselineCreateResponse, CensusBaselineItem


# ID: 896fd7dc-a554-438c-9d2a-e5139b2edd01
def test_CensusBaselineCreateResponse():
    item = CensusBaselineItem.model_construct(name="baseline-1")

    response = CensusBaselineCreateResponse(baseline=item)

    assert isinstance(response, CensusBaselineCreateResponse)
    assert response.baseline is item
    assert response.baseline.name == "baseline-1"
