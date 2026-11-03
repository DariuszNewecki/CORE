from __future__ import annotations

import json
from unittest.mock import MagicMock

from will.test_generation.artifacts import TestGenArtifactStore


# ID: 25832380-190a-40d0-8ff5-da9e4357a1cc
def test_TestGenArtifactStore_write_summary():
    file_handler = MagicMock()
    store = TestGenArtifactStore(file_handler=file_handler)

    session_dir = "/tmp/session"
    summary = {"total": 3, "passed": 2}

    result = store.write_summary(session_dir, summary)

    assert result == "/tmp/session/SUMMARY.json"
    file_handler.write.assert_called_once()
    called_path, called_content = file_handler.write.call_args[0]
    assert called_path == "/tmp/session/SUMMARY.json"
    assert json.loads(called_content) == summary


from unittest.mock import patch


# ID: 7384cb81-192d-42b0-a891-ae99caed8550
def test_TestGenArtifactStore_write_sandbox():
    file_handler = MagicMock()
    store = TestGenArtifactStore(file_handler)

    with patch("will.test_generation.artifacts.time") as mock_time:
        mock_time.strftime.return_value = "2024-01-01 00:00:00"

        path = store.write_sandbox(
            session_dir="/tmp/session",
            symbol="foo",
            passed=True,
            error="",
        )

    assert path == "/tmp/session/foo_sandbox.json"
    file_handler.write.assert_called_once()

    write_args = file_handler.write.call_args
    assert write_args[0][0] == "/tmp/session/foo_sandbox.json"

    payload = json.loads(write_args[0][1])
    assert payload["symbol"] == "foo"
    assert payload["passed"] is True
    assert payload["error"] == ""
    assert payload["timestamp"] == "2024-01-01 00:00:00"


# ID: 44d8b26f-faa6-47d1-b167-e55378ee3d45
def test_TestGenArtifactStore_write_validation():
    fh = MagicMock()
    store = TestGenArtifactStore(fh)

    path = store.write_validation(
        session_dir="/tmp/session",
        symbol="my_symbol",
        ok=True,
        error="",
        normalization="nfc",
    )

    assert path == "/tmp/session/my_symbol_validation.json"
    fh.write.assert_called_once()
    written_path, written_content = fh.write.call_args[0]
    assert written_path == "/tmp/session/my_symbol_validation.json"
    payload = json.loads(written_content)
    assert payload["symbol"] == "my_symbol"
    assert payload["validation_passed"] is True
    assert payload["error"] == ""
    assert payload["normalization"] == "nfc"
    assert "timestamp" in payload


# ID: f82bbbd3-4f7c-401a-89e6-12ec0ab81aa6
def test_TestGenArtifactStore_write_generated():
    file_handler = MagicMock()
    store = TestGenArtifactStore(file_handler)

    code = "def foo():\n    return 42\n"

    result = store.write_generated("/tmp/session", "foo", code)

    expected_path = "/tmp/session/foo_generated.py"
    assert result == expected_path
    file_handler.write.assert_called_once_with(expected_path, code)


# ID: 67a424e0-5082-4fc9-8929-5b0343914ee7
def test_TestGenArtifactStore_write_normalized():
    file_handler = MagicMock()
    store = TestGenArtifactStore(file_handler)

    session_dir = "/tmp/sessions/abc123"
    symbol = "my_symbol"
    code = "def foo():\n    return 42\n"
    method = "ruff-format"

    result = store.write_normalized(session_dir, symbol, code, method)

    expected_path = f"{session_dir}/{symbol}_normalized.py"
    assert result == expected_path

    file_handler.write.assert_called_once_with(
        expected_path,
        f"# Normalization: {method}\n" + code,
    )


# ID: ab18f1ca-2bbf-4af0-b0e3-8c4033fcf1ea
def test_TestGenArtifactStore_write_response():
    file_handler = MagicMock()
    store = TestGenArtifactStore(file_handler)

    result = store.write_response("/tmp/session", "my_symbol", "the response body")

    assert result == "/tmp/session/my_symbol_response.txt"
    file_handler.write.assert_called_once_with(
        "/tmp/session/my_symbol_response.txt", "the response body"
    )


# ID: d3d14d58-727a-4a9f-acea-c7345ec25fe3
def test_TestGenArtifactStore_write_prompt():
    mock_fh = MagicMock()
    store = TestGenArtifactStore(mock_fh)

    result = store.write_prompt("/sessions/s1", "sym", "hello prompt")

    expected_path = "/sessions/s1/sym_prompt.txt"
    assert result == expected_path
    mock_fh.write.assert_called_once_with(expected_path, "hello prompt")


# ID: 8af01bab-d6a6-465b-87fa-0a9af95334d5
def test_TestGenArtifactStore_start_session():
    from will.test_generation.artifacts import TestGenArtifactStore

    mock_fh = MagicMock()
    store = TestGenArtifactStore(file_handler=mock_fh)

    with patch("will.test_generation.artifacts.time.time", return_value=1234567890):
        result = store.start_session()

    mock_fh.ensure_dir.assert_called_once_with("work/test_generation/1234567890")
    assert result.session_dir == "work/test_generation/1234567890"





# ID: 01c452d9-f67e-40df-9561-803c638fdf77
def test_TestGenArtifactStore():
    file_handler = MagicMock()
    store = TestGenArtifactStore(file_handler)

    with patch("will.test_generation.artifacts.time.time", return_value=1700000000):
        paths = store.start_session()
    assert paths.session_dir == "work/test_generation/1700000000"
    file_handler.ensure_dir.assert_called_once_with("work/test_generation/1700000000")

    session_dir = paths.session_dir

    prompt_path = store.write_prompt(session_dir, "Foo", "hello")
    assert prompt_path == f"{session_dir}/Foo_prompt.txt"
    file_handler.write.assert_called_with(prompt_path, "hello")

    response_path = store.write_response(session_dir, "Foo", "bar")
    assert response_path == f"{session_dir}/Foo_response.txt"
    file_handler.write.assert_called_with(response_path, "bar")

    normalized_path = store.write_normalized(session_dir, "Foo", "code()", "ruff")
    assert normalized_path == f"{session_dir}/Foo_normalized.py"
    file_handler.write.assert_called_with(
        normalized_path, "# Normalization: ruff\ncode()"
    )

    generated_path = store.write_generated(session_dir, "Foo", "def foo(): pass")
    assert generated_path == f"{session_dir}/Foo_generated.py"
    file_handler.write.assert_called_with(generated_path, "def foo(): pass")

    with patch(
        "will.test_generation.artifacts.time.strftime",
        return_value="2024-01-01 00:00:00",
    ):
        validation_path = store.write_validation(session_dir, "Foo", True, "", "ruff")
    assert validation_path == f"{session_dir}/Foo_validation.json"
    validation_args = file_handler.write.call_args[0]
    assert validation_args[0] == validation_path
    assert '"symbol": "Foo"' in validation_args[1]
    assert '"validation_passed": true' in validation_args[1]

    with patch(
        "will.test_generation.artifacts.time.strftime",
        return_value="2024-01-01 00:00:00",
    ):
        sandbox_path = store.write_sandbox(session_dir, "Foo", True, "")
    assert sandbox_path == f"{session_dir}/Foo_sandbox.json"
    sandbox_args = file_handler.write.call_args[0]
    assert sandbox_args[0] == sandbox_path
    assert '"passed": true' in sandbox_args[1]

    summary_path = store.write_summary(session_dir, {"total": 1})
    assert summary_path == f"{session_dir}/SUMMARY.json"
    summary_args = file_handler.write.call_args[0]
    assert summary_args[0] == summary_path
    assert '"total": 1' in summary_args[1]
