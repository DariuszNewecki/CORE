from __future__ import annotations

import sys
import types


# The module under test imports `RuleEnforcementCheck` from a package that does
# not exist in this sandbox (`mind.governance.checks`). Stub the missing
# dependency before importing the symbol so collection succeeds.
if "mind.governance.checks" not in sys.modules:
    _governance = types.ModuleType("mind.governance.checks")
    _rule_mod = types.ModuleType("mind.governance.checks.rule_enforcement_check")

    class _RuleEnforcementCheck:
        def __init__(self, *args, **kwargs) -> None:
            pass

    _rule_mod.RuleEnforcementCheck = _RuleEnforcementCheck
    _governance.rule_enforcement_check = _rule_mod
    sys.modules["mind.governance.checks"] = _governance
    sys.modules["mind.governance.checks.rule_enforcement_check"] = _rule_mod

from mind.logic.engines.ast_gate.checks.purity_enforcement_check import (
    PurityEnforcementCheck,
)


# ID: 66adbb3d-5e02-46fd-bbab-b6f8f7970fef
def test_PurityEnforcementCheck() -> None:
    check = PurityEnforcementCheck()

    assert check._is_concrete_check is True

    assert check.policy_rule_ids == [
        "purity.stable_id_anchor",
        "purity.forbidden_decorators",
        "purity.forbidden_primitives",
    ]

    assert check.enforcement_methods == []
