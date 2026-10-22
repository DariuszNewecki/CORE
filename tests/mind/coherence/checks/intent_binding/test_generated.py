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


import asyncio


# ID: 7e9562bb-9bdb-4689-9240-967682878866
def test_IntentBindingCheck(tmp_path: Path) -> None:
    # Build a real fake source tree so _resolve_module / _symbol_in_file work
    src_dir = tmp_path / "src" / "pkg"
    src_dir.mkdir(parents=True)
    module_file = src_dir / "mod.py"
    module_file.write_text("class Thing:\n    pass\n", encoding="utf-8")

    check = IntentBindingCheck(repo_root=tmp_path)

    bindings = [
        (tmp_path / ".intent" / "phases" / "p.yaml", "implementation", "pkg.mod.Thing"),
        (
            tmp_path / ".intent" / "phases" / "p.yaml",
            "implementation",
            "pkg.mod.Missing",
        ),
    ]

    with (
        patch.object(check, "_collect_bindings", return_value=bindings),
        patch(
            "mind.coherence.checks.intent_binding.law_relpath",
            side_effect=lambda root, p: str(Path(p).relative_to(root)),
        ),
        patch(
            "mind.coherence.checks.intent_binding._symbol_in_file",
            side_effect=lambda src, sym: sym == "Thing",
        ),
    ):
        candidates = asyncio.run(check.run())

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.relation == "INTENT_BINDING"
    assert candidate.documents == [".intent/phases/p.yaml"]
    assert "pkg.mod.Missing" in candidate.claim
