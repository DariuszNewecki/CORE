from __future__ import annotations

from unittest.mock import MagicMock, patch

from will.phases.canary.test_discovery import TestDiscoveryService


# ID: 8d829c42-7414-4a42-b00f-a07c6dc2b1bf
def test_TestDiscoveryService_find_related_tests(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()

    path_resolver = MagicMock()
    path_resolver.repo_root = tmp_path

    service = TestDiscoveryService(path_resolver, tests_dir=tests_dir)

    expected = [str(tests_dir / "foo" / "test_bar.py")]

    with patch.object(
        service,
        "_discover_tests_for_file",
        return_value=expected,
    ) as mock_discover:
        result = service.find_related_tests(["src/foo/bar.py"])

    mock_discover.assert_called_once_with("src/foo/bar.py")
    assert result == expected


from pathlib import Path


# ID: 3d9ff0ca-b044-4487-9228-943716cfcf3e
def test_TestDiscoveryService(tmp_path: Path) -> None:
    repo_root = tmp_path
    tests_dir = repo_root / "tests" / "foo"
    tests_dir.mkdir(parents=True)

    expected_test = tests_dir / "test_bar.py"
    expected_test.write_text("# test\n")

    path_resolver = MagicMock()
    path_resolver.repo_root = repo_root

    service = TestDiscoveryService(
        path_resolver=path_resolver, tests_dir=repo_root / "tests"
    )

    result = service.find_related_tests(["src/foo/bar.py"])

    assert result == ["tests/foo/test_bar.py"]
