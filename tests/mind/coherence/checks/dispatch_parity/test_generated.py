from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

from mind.coherence.checks.dispatch_parity import DispatchParityCheck


# ID: e0f7ae01-89a2-4546-9208-39e3463cd915
def test_DispatchParityCheck_run() -> None:
    check = DispatchParityCheck(repo_root=Path("/tmp"), intent_repo=MagicMock())

    check._load_rule_ids = MagicMock(return_value={"R-001"})
    check._load_mappings = MagicMock(return_value=({"R-001"}, {"R-001": "file_gate"}))
    check._load_substrate_taxonomy = MagicMock(return_value=set())
    check._derive_file_backed_engines = MagicMock(return_value={"file_gate"})

    result = asyncio.run(check.run())

    assert result == []


from unittest.mock import patch


# ID: 2b8104ad-b4e5-4a7c-9502-759457f444fe
async def test_DispatchParityCheck(tmp_path: Path) -> None:
    intent_repo = MagicMock()
    intent_repo.known_rule_ids.return_value = {"RULE_A", "RULE_B"}

    rule_ref = MagicMock()
    rule_ref.content = "some rule content"
    intent_repo.get_rule.return_value = rule_ref

    mapping_path = Path(".intent/enforcement/mappings/some_mapping.yaml")
    intent_repo.iter_documents.return_value = [
        (mapping_path, {"mappings": {"RULE_A": {"engine": "ast_gate"}}}),
    ]

    check = DispatchParityCheck(repo_root=tmp_path, intent_repo=intent_repo)

    with (
        patch(
            "mind.coherence.checks.dispatch_parity.rule_requires_enforcement_mapping",
            return_value=True,
        ),
        patch.object(
            DispatchParityCheck,
            "_load_substrate_taxonomy",
            return_value={"ast_gate"},
        ),
        patch.object(
            DispatchParityCheck,
            "_derive_file_backed_engines",
            return_value={"ast_gate"},
        ),
    ):
        candidates = await check.run()

    assert isinstance(candidates, list)
    # RULE_B is unmapped -> UNMAPPED candidate
    unmapped = [c for c in candidates if c.claim.startswith("UNMAPPED")]
    assert any("RULE_B" in c.claim for c in unmapped)
    # RULE_A maps to a known engine -> no UNKNOWN_ENGINE finding
    assert not any(c.claim.startswith("UNKNOWN_ENGINE") for c in candidates)
    for candidate in candidates:
        assert candidate.relation == DispatchParityCheck.relation
