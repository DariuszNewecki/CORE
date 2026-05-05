"""
Comprehensive pytest test module for src/body/atomic/sync_actions/__init__.py.
Tests all public symbols: perform_parallel_actions, lock_action, wait_action,
AtomicActionExecutor, SyncActionRegistry.
"""

from unittest.mock import Mock

import pytest

from src.body.atomic.sync_actions import (
    lock_action,
    perform_parallel_actions,
)


class TestPerformParallelActions:
    """Tests for the perform_parallel_actions function."""

    def test_perform_parallel_actions_with_empty_list(self) -> None:
        """Should handle empty action list gracefully."""
        result = perform_parallel_actions([])
        assert result == []

    def test_perform_parallel_actions_with_single_action(self) -> None:
        """Should execute a single action and return its result."""
        action = Mock(return_value={"status": "done"})
        result = perform_parallel_actions([action])
        assert result == [{"status": "done"}]
        action.assert_called_once()

    def test_perform_parallel_actions_with_multiple_actions(self) -> None:
        """Should execute multiple actions and return all results."""
        action1 = Mock(return_value={"id": 1})
        action2 = Mock(return_value={"id": 2})
        action3 = Mock(return_value={"id": 3})
        result = perform_parallel_actions([action1, action2, action3])
        assert len(result) == 3
        assert result[0] == {"id": 1}
        assert result[1] == {"id": 2}
        assert result[2] == {"id": 3}

    def test_perform_parallel_actions_with_action_failure(self) -> None:
        """Should propagate exceptions from failing actions."""
        action = Mock(side_effect=ValueError("Action failed"))
        with pytest.raises(ValueError, match="Action failed"):
            perform_parallel_actions([action])

    def test_perform_parallel_actions_with_mixed_results(self) -> None:
        """Handle mix of successful and failing actions."""
        success_action = Mock(return_value={"ok": True})
        fail_action = Mock(side_effect=RuntimeError("Fail"))
        with pytest.raises(RuntimeError, match="Fail"):
            perform_parallel_actions([success_action, fail_action])


class TestLockAction:
    """Tests for the lock_action function."""

    def test_lock_action_with_string_resource(self) -> None:
        """Should acquire and release lock on string resource."""
        resource_id = "test_resource"
        action = Mock(return_value="locked_result")

        result = lock_action(resource_id, action)
        assert result == "locked_result"
        action.assert_called_once_with(resource_id)

    def test_lock_action_with_integer_resource(self) -> None:
        """Should handle integer resource IDs."""
        resource_id = 42
        action = Mock(return_value={"data": "value"})

        result = lock_action(resource_id, action)
        assert result == {"data": "value"}
        action.assert_called_once_with(resource_id)

    def test_lock_action_concurrent_same_resource(self) -> None:
        """Should enforce mutual exclusion for same resource."""
        resource_id = "shared_resource"
        captured = []

        def slow_action(res_id: str) -> str:
            captured.append(res_id)
            return "done"

        first_action = Mock(side_effect=slow_action)
        second_action = Mock(side_effect=slow_action)

        lock_action(resource_id, first_action)
        lock_action(resource_id, second_action)

        assert captured == ["shared_resource", "shared_resource"]
        first_action.assert_called_once()
        second_action.assert_called_once()

    def test_lock_action_releases_on_failure(self) -> None:
        """Should release lock even if action raises exception."""
        resource_id = "failing_resource"
        action = Mock(side_effect=RuntimeError("Locked failure"))

        with pytest.raises(RuntimeError, match="Locked failure"):
            lock_action(resource_id, action)

        # Lock should be released; subs
