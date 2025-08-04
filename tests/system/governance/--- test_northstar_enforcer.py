# tests/system/governance/test_northstar_enforcer.py

import pytest
from pathlib import Path
# --- FIX: Changed import from 'system.governance.northstar_enforcer' to 'system.governance.northstar_enforcer'
from system.governance.northstar_enforcer import NorthStarEnforcer

@pytest.fixture
def mock_repo_root(tmp_path):
    """Prepare a mock .intent/mission/northstar.yaml structure"""
    mission_dir = tmp_path / ".intent" / "mission"
    mission_dir.mkdir(parents=True)

    content = """
northstar: Drive safe, traceable AI evolution.
purpose:
  - Ensure all generated code serves a traceable, justifiable goal.
  - Empower AI with operational clarity.
values:
  - Traceability
  - Alignment
  - Constitution-first thinking
"""

    path = mission_dir / "northstar.yaml"
    path.write_text(content)
    return tmp_path

def test_explain_policy_outputs_without_error(mock_repo_root, capsys):
    enforcer = NorthStarEnforcer(repo_root=mock_repo_root)
    enforcer.explain_policy()
    output = capsys.readouterr().out
    assert "CORE's NorthStar" in output
    assert "Traceability" in output
    assert "Drive safe" in output

def test_justified_purpose_match(mock_repo_root):
    enforcer = NorthStarEnforcer(repo_root=mock_repo_root)
    assert enforcer.is_justified("traceability") is True
    assert enforcer.is_justified("empower AI with operational clarity") is True

def test_unjustified_purpose(mock_repo_root):
    enforcer = NorthStarEnforcer(repo_root=mock_repo_root)
    assert enforcer.is_justified("random marketing fluff") is False

def test_validate_intent(mock_repo_root):
    enforcer = NorthStarEnforcer(repo_root=mock_repo_root)

    aligned_intent = {"justification": "empower AI with operational clarity"}
    misaligned_intent = {"justification": "make code trendy and fun"}

    assert enforcer.validate_intent(aligned_intent) is True
    assert enforcer.validate_intent(misaligned_intent) is False

def test_missing_file_raises_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        NorthStarEnforcer(repo_root=tmp_path)