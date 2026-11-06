from __future__ import annotations

from unittest.mock import MagicMock, patch

from will.test_generation.persistence import TestPersistenceService


# ID: 189fc980-2ad7-47dd-8308-ca3e177658b0
def test_persist_quarantined():
    file_handler = MagicMock()
    service = TestPersistenceService(file_handler=file_handler)

    expected_result = MagicMock()

    with patch.object(
        TestPersistenceService, "persist", return_value=expected_result
    ) as mock_persist:
        result = service.persist_quarantined(
            original_file="src/will/foo.py",
            symbol_name="foo",
            test_code="def test_foo():\n    assert True\n",
            sandbox_passed=True,
        )

    mock_persist.assert_called_once_with(
        "src/will/foo.py",
        "foo",
        "def test_foo():\n    assert True\n",
    )
    assert result is expected_result
