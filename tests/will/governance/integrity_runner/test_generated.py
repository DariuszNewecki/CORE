from __future__ import annotations

from unittest.mock import MagicMock, patch


# ID: 9ef3c823-d455-459a-81be-4669887f6e5e
def test_verify_integrity():
    from will.governance.integrity_runner import verify_integrity

    context = MagicMock()
    context.git_service.repo_path = "/some/repo/path"

    verify_result = MagicMock()
    verify_result.ok = True
    verify_result.errors = []
    verify_result.metadata = {"checked_at": "2024-01-01T00:00:00Z"}

    with patch("will.governance.integrity_runner.IntegrityService") as mock_service_cls:
        mock_service = MagicMock()
        mock_service.verify_integrity.return_value = verify_result
        mock_service_cls.return_value = mock_service

        result = verify_integrity(context, "baseline-label")

    mock_service_cls.assert_called_once_with("/some/repo/path")
    mock_service.verify_integrity.assert_called_once_with("baseline-label")

    assert result == {
        "label": "baseline-label",
        "ok": True,
        "errors": [],
        "checked_at": "2024-01-01T00:00:00Z",
    }
