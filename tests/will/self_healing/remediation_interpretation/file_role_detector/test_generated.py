from __future__ import annotations

from unittest.mock import MagicMock, patch


# ID: ff20c0a4-4f53-4d9d-868d-149fd2dc610c
def test_FileRoleDetector_detect():
    from will.self_healing.remediation_interpretation.file_role_detector import (
        FileRoleDetector,
    )

    detector = FileRoleDetector()

    with (
        patch.object(
            detector, "_detect_layer", return_value=("core", ["layer-ev"], 0.9)
        ),
        patch.object(detector, "_parse_ast", return_value=MagicMock()),
        patch.object(
            detector,
            "_detect_role_from_path",
            return_value=("service", 0.8, ["path-ev"]),
        ),
        patch.object(
            detector,
            "_detect_role_from_ast",
            return_value=("service", 0.7, ["ast-ev"]),
        ),
        patch.object(
            detector,
            "_detect_role_from_findings",
            return_value=(None, 0.0, []),
        ),
        patch.object(
            detector,
            "_merge_role_signals",
            return_value=("service", 0.75, ["merge-ev"]),
        ),
        patch.object(detector, "_combine_confidence", return_value=0.85),
        patch.object(detector, "_dedupe_preserve_order", side_effect=lambda x: x),
    ):
        result = detector.detect(
            file_path="src/app/service.py",
            source_code="class Foo: pass\n",
            findings=None,
        )

    assert result.role_id == "service"
    assert result.layer == "core"
    assert result.confidence == 0.85
    assert "layer-ev" in result.evidence
    assert "merge-ev" in result.evidence


from will.self_healing.remediation_interpretation.file_role_detector import (
    FileRoleDetector,
)


# ID: addd4613-a8e2-42ba-b0af-b99f5c16d3c9
def test_FileRoleDetector():
    detector = FileRoleDetector()

    source_code = '''
# ID: 8ccd375d-256d-4034-97d0-3431306070ca
class MyWorker(Worker):
    """A sensing worker that posts findings."""
'''
    file_path = "src/will/workers/my_worker.py"

    result = detector.detect(file_path=file_path, source_code=source_code)

    assert result is not None
    assert result.layer == "will"
    assert result.role_id in {"worker.sensor", "worker", "worker.actor"}
    assert result.role_id == "worker.sensor"
    assert isinstance(result.confidence, float)
    assert 0.0 <= result.confidence <= 1.0
    assert isinstance(result.evidence, list)
    assert len(result.evidence) >= 1

    # Path-only inference for a plain service file.
    service_result = detector.detect(
        file_path="src/body/services/user_service.py",
        source_code="",
    )
    assert service_result.layer == "body"
    assert service_result.role_id == "service"
    assert 0.0 <= service_result.confidence <= 1.0
