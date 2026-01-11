"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/mind/governance/policy_loader.py
- Symbol: load_available_actions
- Status: 4 tests passed, some failed
- Passing tests: test_load_available_actions_returns_non_empty_list_when_planner_actions_present, test_load_available_actions_falls_back_to_actions_key, test_load_available_actions_returns_empty_list_when_no_actions_found, test_load_available_actions_returns_empty_list_when_planner_actions_is_empty
- Generated: 2026-01-11 01:23:21
"""

from mind.governance.policy_loader import load_available_actions


def test_load_available_actions_returns_non_empty_list_when_planner_actions_present(
    monkeypatch,
):
    mock_policy = {"planner_actions": ["action1", "action2", "action3"]}

    def mock_load(*args, **kwargs):
        return mock_policy

    monkeypatch.setattr("mind.governance.policy_loader._load_policy_yaml", mock_load)
    result = load_available_actions()
    assert result == {"actions": ["action1", "action2", "action3"]}


def test_load_available_actions_falls_back_to_actions_key(monkeypatch):
    mock_policy = {"actions": ["fallback_action1", "fallback_action2"]}

    def mock_load(*args, **kwargs):
        return mock_policy

    monkeypatch.setattr("mind.governance.policy_loader._load_policy_yaml", mock_load)
    result = load_available_actions()
    assert result == {"actions": ["fallback_action1", "fallback_action2"]}


def test_load_available_actions_returns_empty_list_when_no_actions_found(monkeypatch):
    mock_policy = {}

    def mock_load(*args, **kwargs):
        return mock_policy

    monkeypatch.setattr("mind.governance.policy_loader._load_policy_yaml", mock_load)
    result = load_available_actions()
    assert result == {"actions": []}


def test_load_available_actions_returns_empty_list_when_planner_actions_is_empty(
    monkeypatch,
):
    mock_policy = {"planner_actions": []}

    def mock_load(*args, **kwargs):
        return mock_policy

    monkeypatch.setattr("mind.governance.policy_loader._load_policy_yaml", mock_load)
    result = load_available_actions()
    assert result == {"actions": []}
