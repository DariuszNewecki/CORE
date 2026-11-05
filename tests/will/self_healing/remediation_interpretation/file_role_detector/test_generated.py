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
