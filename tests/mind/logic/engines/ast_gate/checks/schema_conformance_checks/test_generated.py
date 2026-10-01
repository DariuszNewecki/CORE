from __future__ import annotations

import json
from pathlib import Path

from mind.logic.engines.ast_gate.checks.schema_conformance_checks import (
    SchemaConformanceChecks,
)


# ID: c0eb0125-0499-4f66-a304-3c46e937dc65
def test_SchemaConformanceChecks_extract_governed_classes(tmp_path: Path) -> None:
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(
        json.dumps({"governed_classes": ["Foo", "Bar", "Baz"]}),
        encoding="utf-8",
    )

    result = SchemaConformanceChecks.extract_governed_classes(contract_path)

    assert result == ["Foo", "Bar", "Baz"]
