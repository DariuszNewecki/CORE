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


import json
from pathlib import Path

from will.governance.integrity_runner import create_baseline


# ID: 80b4967d-8961-4d7c-b713-8ee651c42284
def test_create_baseline(tmp_path: Path) -> None:
    repo_root = tmp_path
    label = "v1"
    baseline_path = repo_root / ".integrity" / f"baseline_{label}.json"
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {"files": {"a.py": "hash1", "b.py": "hash2"}}
    baseline_path.write_text(json.dumps(manifest), encoding="utf-8")

    context = MagicMock()
    context.git_service.repo_path = repo_root

    with patch("will.governance.integrity_runner.IntegrityService") as mock_service_cls:
        mock_service = MagicMock()
        mock_service.create_baseline.return_value = baseline_path
        mock_service_cls.return_value = mock_service

        result = create_baseline(context, label)

    mock_service_cls.assert_called_once_with(repo_root)
    mock_service.create_baseline.assert_called_once_with(label)
    assert result == {
        "label": label,
        "path": str(baseline_path.relative_to(repo_root)),
        "files_hashed": 2,
    }
