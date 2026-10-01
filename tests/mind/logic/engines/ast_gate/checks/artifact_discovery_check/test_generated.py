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
