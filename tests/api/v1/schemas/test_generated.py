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
