# tests/body/atomic/test_build_test_for_symbol_action.py
"""Tests for build.test_for_symbol write-only action (ADR-133 D3, ADR-140 D7).

The action now receives pre-generated code from the cognitive step. Tests verify
the write path, the defensive IntentGuard pass, and the path resolution behaviour.
Pure utility functions moved to shared/utils/test_gen_utils.py — tested there.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from shared.governance_token import authorize_execution
from shared.utils.test_gen_utils import (
    derive_module_path,
    extract_from_fences,
    extract_symbol_code,
)


# ── Pure helpers (now in shared.utils.test_gen_utils) ────────────────────────


def test_derive_module_path_strips_src_and_py():
    assert derive_module_path("src/will/workers/foo.py") == "will.workers.foo"


def test_derive_module_path_nested():
    assert derive_module_path("src/body/atomic/bar.py") == "body.atomic.bar"


def test_extract_from_fences_python_fence():
    raw = "```python\ndef test_foo():\n    assert True\n```"
    result = extract_from_fences(raw)
    assert result == "def test_foo():\n    assert True"


def test_extract_from_fences_generic_fence():
    raw = "```\ndef test_foo(): pass\n```"
    result = extract_from_fences(raw)
    assert result == "def test_foo(): pass"


def test_extract_from_fences_no_fence_returns_none():
    assert extract_from_fences("just plain text") is None


def test_extract_from_fences_unclosed_returns_none():
    assert extract_from_fences("```python\ndef foo(): pass") is None


def test_extract_symbol_code_finds_function(tmp_path):
    src = tmp_path / "foo.py"
    src.write_text("def my_fn(x, y):\n    return x + y\n\ndef other(): pass\n")
    result = extract_symbol_code(src, "my_fn")
    assert result is not None
    assert "my_fn" in result
    assert "other" not in result


def test_extract_symbol_code_finds_class(tmp_path):
    src = tmp_path / "bar.py"
    src.write_text("class Foo:\n    pass\n\nclass Bar:\n    pass\n")
    result = extract_symbol_code(src, "Foo")
    assert result is not None
    assert "Foo" in result
    assert "Bar" not in result


def test_extract_symbol_code_missing_symbol_returns_none(tmp_path):
    src = tmp_path / "empty.py"
    src.write_text("def alpha(): pass\n")
    assert extract_symbol_code(src, "nonexistent") is None


def test_extract_symbol_code_missing_file_returns_none(tmp_path):
    assert extract_symbol_code(tmp_path / "ghost.py", "foo") is None


# ── Write-only action: receives generated_code, writes it ───────────────────

_GOOD_CODE = "from __future__ import annotations\n\n\ndef test_do_work():\n    assert do_work(2) == 4\n"


@pytest.fixture
def mock_core_context(tmp_path):
    ctx = MagicMock()
    ctx.git_service.repo_path = tmp_path
    ctx.file_handler = MagicMock()
    ctx.file_handler.write = MagicMock()
    return ctx


@pytest.fixture
def source_setup(tmp_path):
    src_dir = tmp_path / "src" / "mypkg"
    src_dir.mkdir(parents=True)
    (src_dir / "service.py").write_text("def do_work(x):\n    return x * 2\n")
    return "src/mypkg/service.py"


@pytest.mark.asyncio
async def test_action_dry_run_returns_ok_no_write(mock_core_context, source_setup):
    from body.atomic.build_test_for_symbol_action import action_build_test_for_symbol

    mock_validation = MagicMock()
    mock_validation.is_valid = True
    mock_validation.violations = []
    mock_intent_guard = MagicMock()
    mock_intent_guard.validate_generated_code = MagicMock(return_value=mock_validation)

    with (
        patch(
            "body.atomic.build_test_for_symbol_action.get_intent_guard",
            return_value=mock_intent_guard,
        ),
        patch(
            "body.atomic.build_test_for_symbol_action.source_to_test_path",
            return_value="tests/mypkg/service/test_generated.py",
        ),
        authorize_execution("build.test_for_symbol"),
    ):
        result = await action_build_test_for_symbol(
            source_file=source_setup,
            symbol_name="do_work",
            symbol_kind="function",
            generated_code=_GOOD_CODE,
            core_context=mock_core_context,
            write=False,
        )

    assert result.ok
    assert result.data["symbol_name"] == "do_work"
    assert result.data["files_produced"] == []
    mock_core_context.file_handler.write.assert_not_called()


@pytest.mark.asyncio
async def test_action_write_true_calls_file_handler(mock_core_context, source_setup):
    from body.atomic.build_test_for_symbol_action import action_build_test_for_symbol

    mock_validation = MagicMock()
    mock_validation.is_valid = True
    mock_validation.violations = []
    mock_intent_guard = MagicMock()
    mock_intent_guard.validate_generated_code = MagicMock(return_value=mock_validation)

    with (
        patch(
            "body.atomic.build_test_for_symbol_action.get_intent_guard",
            return_value=mock_intent_guard,
        ),
        patch(
            "body.atomic.build_test_for_symbol_action.source_to_test_path",
            return_value="tests/mypkg/service/test_generated.py",
        ),
        authorize_execution("build.test_for_symbol"),
    ):
        result = await action_build_test_for_symbol(
            source_file=source_setup,
            symbol_name="do_work",
            symbol_kind="function",
            generated_code=_GOOD_CODE,
            core_context=mock_core_context,
            write=True,
        )

    assert result.ok
    assert result.data["files_produced"] == ["tests/mypkg/service/test_generated.py"]
    calls = mock_core_context.file_handler.write.call_args_list
    assert calls[0][0][0] == "tests/mypkg/service/test_generated.py"
    init_paths = [c[0][0] for c in calls[1:]]
    assert all(p.endswith("__init__.py") for p in init_paths)


@pytest.mark.asyncio
async def test_action_returns_not_ok_on_intent_guard_violation(
    mock_core_context, source_setup
):
    from body.atomic.build_test_for_symbol_action import action_build_test_for_symbol

    violation = MagicMock()
    violation.rule_name = "code.tests.no_placeholder_test_body"
    violation.message = "No assertion"
    violation.severity = "error"

    mock_validation = MagicMock()
    mock_validation.is_valid = False
    mock_validation.violations = [violation]
    mock_intent_guard = MagicMock()
    mock_intent_guard.validate_generated_code = MagicMock(return_value=mock_validation)

    with (
        patch(
            "body.atomic.build_test_for_symbol_action.get_intent_guard",
            return_value=mock_intent_guard,
        ),
        patch(
            "body.atomic.build_test_for_symbol_action.source_to_test_path",
            return_value="tests/mypkg/service/test_generated.py",
        ),
        authorize_execution("build.test_for_symbol"),
    ):
        result = await action_build_test_for_symbol(
            source_file=source_setup,
            symbol_name="do_work",
            symbol_kind="function",
            generated_code=_GOOD_CODE,
            core_context=mock_core_context,
            write=False,
        )

    assert not result.ok
    assert result.data["error"] == "intent_guard_violations"
    assert len(result.data["violations"]) == 1
