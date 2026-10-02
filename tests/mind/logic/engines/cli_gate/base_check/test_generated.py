from __future__ import annotations

from typing import Any

import pytest

from mind.logic.engines.cli_gate.base_check import CliCheck


# ID: 26d38f5c-6c53-4df6-b303-e7de79b7f677
def test_CliCheck_verify() -> None:
    class _Concrete(CliCheck):
        # ID: ba5c9847-d521-4733-ac8f-8b6f9f1142d1
        def verify(self, commands: list[dict[str, Any]], params: dict[str, Any]):
            return [{"rule": "demo", "message": "ok"}]

    concrete = _Concrete.__new__(_Concrete)

    findings = concrete.verify(
        [{"name": "run", "callback": lambda: None}],
        {"_scope_excludes": []},
    )

    assert isinstance(findings, list)
    assert len(findings) == 1
    assert findings[0]["message"] == "ok"

    with pytest.raises(NotImplementedError):
        CliCheck.verify(concrete, [], {})
