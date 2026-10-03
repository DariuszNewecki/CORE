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


# ID: 30750ac2-503e-4370-8038-00ba2f4f790e
def test_ImportChecks_check_import_order() -> None:
    obj = ImportChecks()

    source = (
        "from __future__ import annotations\n"
        "import os\n"
        "import sys\n"
        "import requests\n"
        "from mind.logic import foo\n"
    )
    tree = ast.parse(source)
    params = {
        "stdlib_modules": ["os", "sys"],
        "internal_roots": ["mind"],
    }

    findings = obj.check_import_order(tree, params, source)

    assert isinstance(findings, list)
    assert findings == []


from unittest.mock import patch


# ID: 7bece171-c5a8-47aa-a7f6-4f9609d1d783
def test_check_forbidden_imports():
    source = "import os\nfrom sys import path\nimport forbidden.module\n"
    tree = ast.parse(source)

    with patch.object(
        ImportChecks,
        "_find_type_checking_blocks",
        return_value=set(),
    ):
        findings = ImportChecks.check_forbidden_imports(tree, ["forbidden.module"])

    assert isinstance(findings, list)
    assert len(findings) == 1
    assert "forbidden.module" in findings[0]
