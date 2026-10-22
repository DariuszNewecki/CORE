from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from mind.coherence.checks.intent_binding import IntentBindingCheck


# ID: 9970f852-bbbf-487a-9e97-09e454ed889b
async def test_IntentBindingCheck_run():
    repo_root = Path("/fake/repo")
    check = IntentBindingCheck(repo_root)

    stale_value = "some.module.MissingSymbol"
    good_value = "some.module.ExistingSymbol"

    check._collect_bindings = MagicMock(
        return_value=[
            (Path("/fake/repo/.intent/a.md"), "enforces", stale_value),
            (Path("/fake/repo/.intent/b.md"), "enforces", good_value),
        ]
    )

    def _fake_check_binding(value):
        if value == stale_value:
            return "it does not resolve to a real symbol"
        return None

    check._check_binding = MagicMock(side_effect=_fake_check_binding)

    with patch(
        "mind.coherence.checks.intent_binding.law_relpath",
        return_value=".intent/a.md",
    ):
        candidates = await check.run()

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.relation == check.relation
    assert candidate.documents == [".intent/a.md"]
    assert ".intent/a.md" in candidate.claim
    assert stale_value in candidate.claim

    check._collect_bindings.assert_called_once()
    assert check._check_binding.call_count == 2
