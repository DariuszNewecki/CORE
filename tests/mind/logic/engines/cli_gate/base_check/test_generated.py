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


# ID: b64d0bbc-c20c-45a6-b0af-9062ea10a3e2
def test_CliCheck():
    class _ConcreteCheck(CliCheck):
        check_type = "demo"

        # ID: 9f1efb09-31b8-4708-8404-e899168f1e43
        def verify(
            self, commands: list[dict[str, Any]], params: dict[str, Any]
        ) -> list[Any]:
            results = []
            for command in commands:
                results.append({"command": command.get("name"), "params": params})
            return results

    check = _ConcreteCheck()
    assert isinstance(check, CliCheck)
    assert check.check_type == "demo"

    commands = [{"name": "alpha"}, {"name": "beta"}]
    params = {"check_type": "demo", "_scope_excludes": []}

    findings = check.verify(commands, params)
    assert findings == [
        {"command": "alpha", "params": params},
        {"command": "beta", "params": params},
    ]

    with pytest.raises(TypeError):
        CliCheck()
