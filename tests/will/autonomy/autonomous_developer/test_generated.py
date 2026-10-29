from __future__ import annotations

from will.autonomy.autonomous_developer import infer_workflow_type


# ID: b3e2f32a-5e64-4755-bc01-cb2f84ec4c97
def test_infer_workflow_type():
    assert (
        infer_workflow_type("Refactor the auth module into smaller pieces")
        == "refactor_modularity"
    )
    assert (
        infer_workflow_type("Extract helper methods from the service")
        == "refactor_modularity"
    )
    assert (
        infer_workflow_type("Split the large class into modules")
        == "refactor_modularity"
    )
    assert (
        infer_workflow_type("Generate tests for the parser") == "coverage_remediation"
    )
    assert (
        infer_workflow_type("Improve test coverage of the utils")
        == "coverage_remediation"
    )
    assert infer_workflow_type("Do something completely vague") == "refactor_modularity"
