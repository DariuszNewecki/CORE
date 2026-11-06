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


# ID: 2c309898-6127-45f4-ba06-13ffdf62fb52
def test_TestPersistenceService_persist():
    file_handler = MagicMock()
    service = TestPersistenceService(file_handler)

    service._calculate_mirrored_path = MagicMock(
        return_value="tests/shared/utils/test_text__my_symbol.py"
    )

    result = service.persist(
        original_file="src/shared/utils/text.py",
        symbol_name="my_symbol",
        test_code="def test_my_symbol():\n    assert True\n",
    )

    service._calculate_mirrored_path.assert_called_once_with(
        "src/shared/utils/text.py", "my_symbol"
    )
    file_handler.ensure_dir.assert_called_once_with("tests/shared/utils")
    file_handler.write.assert_called_once()

    written_path, written_content = file_handler.write.call_args[0]
    assert written_path == "tests/shared/utils/test_text__my_symbol.py"
    assert "AUTO-GENERATED TEST" in written_content
    assert "- Source: src/shared/utils/text.py" in written_content
    assert "- Symbol: my_symbol" in written_content
    assert "def test_my_symbol():" in written_content

    assert result.ok is True
    assert result.path == "tests/shared/utils/test_text__my_symbol.py"
    assert result.error == ""
    assert result.tests_saved == 1





# ID: 4d0fd0e2-31eb-4821-88b1-e9d87e0c53b8
def test_TestPersistenceService():
    mock_fh = MagicMock()
    service = TestPersistenceService(mock_fh)

    result = service.persist(
        "src/shared/utils/text.py",
        "my_symbol",
        "def test_my_symbol():\n    assert True\n",
    )

    assert result.ok is True
    assert result.tests_saved == 1
    assert result.path == "tests/shared/utils/test_text__my_symbol.py"
    assert result.error == ""

    mock_fh.ensure_dir.assert_called_once_with("tests/shared/utils")
    mock_fh.write.assert_called_once()
    written_path, written_content = mock_fh.write.call_args.args
    assert written_path == "tests/shared/utils/test_text__my_symbol.py"
    assert "AUTO-GENERATED TEST" in written_content
    assert "Source: src/shared/utils/text.py" in written_content
    assert "Symbol: my_symbol" in written_content
    assert "def test_my_symbol():" in written_content
