import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from typing import Any

from src.will.autonomy.proposal_execution_pipeline import (
    _files_produced_by,
    capture_git_sha,
    commit_proposal_changes,
    compute_changed_files,
    record_consequence,
    resolve_deferred_findings,
    rollback_proposal,
)


class TestFilesProducedBy:
    """Tests for _files_produced_by."""

    def test_returns_empty_set_for_empty_input(self) -> None:
        assert _files_produced_by({}) == set()

    def test_returns_empty_set_when_no_files_produced(self) -> None:
        action_results = {"action1": {"data": {}}}
        assert _files_produced_by(action_results) == set()

    def test_collects_single_file(self) -> None:
        action_results = {
            "action1": {"data": {"files_produced": ["/path/to/file.py"]}}
        }
        expected = {"/path/to/file.py"}
        assert _files_produced_by(action_results) == expected

    def test_collects_multiple_files_from_single_action(self) -> None:
        action_results = {
            "action1": {"data": {"files_produced": ["/path/a.py", "/path/b.py"]}}
        }
        expected = {"/path/a.py", "/path/b.py"}
        assert _files_produced_by(action_results) == expected

    def test_collects_files_from_multiple_actions(self) -> None:
        action_results = {
            "action1": {"data": {"files_produced": ["/path/a.py"]}},
            "action2": {"data": {"files_produced": ["/path/b.py"]}},
        }
        expected = {"/path/a.py", "/path/b.py"}
        assert _files_produced_by(action_results) == expected

    def test_deduplicates_duplicate_paths(self) -> None:
        action_results = {
            "action1": {"data": {"files_produced": ["/path/a.py"]}},
            "action2": {"data": {"files_produced": ["/path/a.py"]}},
        }
        expected = {"/path/a.py"}
        assert _files_produced_by(action_results) == expected

    def test_filters_out_non_string_entries(self) -> None:
        action_results = {
            "action1": {"data": {"files_produced": ["/path/a.py", 123, None, []]}}
        }
        expected = {"/path/a.py"}
        assert _files_produced_by(action_results) == expected

    def test_filters_out_empty_string_entries(self) -> None:
        action_results = {
            "action1": {"data": {"files_produced": ["/path/a.py", ""]}}
        }
        expected = {"/path/a.py"}
        assert _files_produced_by(action_results) == expected

    def test_handles_missing_data_key(self) -> None:
        action_results = {"action1": {}}
        assert _files_produced_by(action_results) == set()

    def test_handles_none_data(self) -> None:
        action_results = {"action1": {"data": None}}
        assert _files_produced_by(action_results) == set()

    def test_handles_missing_files_produced_key(self) -> None:
        action_results = {"action1": {"data": {"other": "value"}}}
        assert _files_produced_by(action_results) == set()

    def test_handles_none_files_produced(self) -> None:
        action_results = {"action1": {"data": {"files_produced": None}}}
        assert _files_produced_by(action_results) == set()


class TestCaptureGitSha:
    """Tests for capture_git_sha."""

    def test_returns_sha_when_git_service_provided_and_phase_pre(self) -> None:
        mock_git = MagicMock()
        mock_git.get_current_commit.return_value = "abc123def456"
        result = capture_git_sha(mock_git, "pre", "proposal-1")
        assert result == "abc123def456"

    def test_returns_sha_when_git_service_provided_and_phase_post(self) -> None:
        mock_git = MagicMock()
        mock_git.get_current_commit.return_value = "abc123def456"
        result = capture_git_sha(mock_git, "post", "proposal-1")
        assert result == "abc123def456"

    def test_returns_none_when_git_service_is_none(self) -> None:
        result = capture_git_sha(None, "pre", "proposal-1")
        assert result is None

    def test_returns_none_when_git_service_raises_exception(self) -> None:
        mock_git = MagicMock()
        mock_git.get_curr
