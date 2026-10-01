from __future__ import annotations

import ast
from pathlib import Path

from mind.logic.engines.ast_gate.checks.artifact_discovery_check import (
    ArtifactDiscoveryCheck,
)


# ID: bf2f90d0-f1f9-4d64-b087-a2716fa4c7ac
def test_ArtifactDiscoveryCheck() -> None:
    source = "from pathlib import Path\ndef discover(p):\n    return p.rglob('*.py')\n"
    tree = ast.parse(source)
    file_path = Path("src/will/workers/some_worker.py")

    findings = ArtifactDiscoveryCheck.check_artifact_discovery_through_registry(
        tree, file_path
    )

    assert isinstance(findings, list)
    assert len(findings) == 1
    assert "rglob" in findings[0]
    assert "*.py" in findings[0]


from unittest.mock import patch


# ID: 3fa1f645-ea9f-41c1-a1c5-3c3d16ce2043
def test_ArtifactDiscoveryCheck_check_artifact_discovery_through_registry():
    cls = ArtifactDiscoveryCheck
    tree = ast.parse("x = rglob('*')")

    # Build a path that satisfies the location gate (PIPELINE_PREFIXES) and
    # avoids the carve-out gates, using the class's own constants.
    pipeline_prefix = cls._PIPELINE_PREFIXES[0]
    file_path = Path(f"{pipeline_prefix}/some_module.py")

    with (
        patch.object(
            cls, "_file_consults_registry", return_value=False
        ) as mock_consults,
        patch.object(
            cls, "_inspect_call", return_value="violation: rglob bypass"
        ) as mock_inspect,
    ):
        findings = cls.check_artifact_discovery_through_registry(tree, file_path)

    assert findings == ["violation: rglob bypass"]
    assert mock_consults.call_count == 1
    assert mock_inspect.call_count == 1
