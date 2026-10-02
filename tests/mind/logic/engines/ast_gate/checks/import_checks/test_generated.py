from __future__ import annotations

import ast

from mind.logic.engines.ast_gate.checks.import_checks import ImportChecks


# ID: 0679393f-1dc2-460d-941f-b624d43ad5e7
def test_ImportChecks() -> None:
    source = "import os\nimport mind\n"
    tree = ast.parse(source)

    forbidden_findings = ImportChecks.check_forbidden_imports(tree, ["mind"])
    assert forbidden_findings == ["Line 2: Forbidden import 'mind'"]

    order_findings = ImportChecks.check_import_order(tree, {})
    assert isinstance(order_findings, list)
