"""A DELEGATE entry with no action stays in the RemediationMap.

Proposal 0006 left purity.no_dead_code as DELEGATE with no action (its only
remover was removed). The loader used to skip any entry without an action or
flow, which made those findings "unmapped": released back to open instead of
delegated, and eligible for ViolationExecutorWorker's LLM ceremony.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from body.autonomy.audit_analyzer import _load_remediation_map


def _resolver(tmp_path: Path, body: str) -> MagicMock:
    path = tmp_path / "auto_remediation.yaml"
    path.write_text(body)
    (tmp_path / "governance_paths.yaml").write_text(
        "remediation:\n  min_confidence: 0.80\n"
    )
    resolver = MagicMock()
    resolver.remediation_map_path = path
    resolver.governance_config_path = tmp_path / "governance_paths.yaml"
    return resolver


# ID: 778a6e92-30f4-4818-a838-98c9fdb304d3
def test_delegate_entry_without_action_is_kept(tmp_path: Path) -> None:
    resolver = _resolver(
        tmp_path,
        "mappings:\n"
        "  purity.no_dead_code:\n"
        "    confidence: 0.40\n"
        "    status: DELEGATE\n",
    )
    entry = _load_remediation_map(resolver)["purity.no_dead_code"]
    assert entry["status"] == "DELEGATE"
    assert entry["ref_id"] is None and entry["action"] is None


# ID: 8cd069ce-83c1-46a5-b6b3-5108c7e52b1e
def test_non_delegate_entry_without_action_is_still_skipped(tmp_path: Path) -> None:
    """Only DELEGATE is exempt: an ACTIVE entry with nothing to run is malformed."""
    resolver = _resolver(
        tmp_path,
        "mappings:\n  some.rule:\n    confidence: 0.95\n    status: ACTIVE\n",
    )
    assert "some.rule" not in _load_remediation_map(resolver)
