# tests/body/actions/test_code_actions.py
import textwrap
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import body.actions.code_actions as ca
from shared.models import PlanExecutionError


# ---------------------------------------------------------------------------
# Utility Tests for _get_symbol_start_end_lines and _replace_symbol_in_code
# ---------------------------------------------------------------------------


def test_get_symbol_start_end_lines_found():
    code = """
def foo():
    pass
"""
    tree = ca.ast.parse(code)
    start, end = ca._get_symbol_start_end_lines(tree, "foo")
    assert (start, end) == (2, 3)


def test_get_symbol_start_end_lines_not_found():
    tree = ca.ast.parse("def foo(): pass")
    result = ca._get_symbol_start_end_lines(tree, "bar")
    assert result is None


def test_replace_symbol_in_code_success():
    original = textwrap.dedent(
        """
        def foo():
            pass

        def bar():
            return 42
        """
    ).strip()
    new_code = """def foo():\n    return 'ok'"""
    result = ca._replace_symbol_in_code(original, "foo", new_code)
    assert "return 'ok'" in result
    assert "bar" in result


def test_replace_symbol_in_code_symbol_not_found():
    code = "def foo():\n    pass"
    with pytest.raises(ValueError):
        ca._replace_symbol_in_code(code, "nope", "def nope(): pass")


def test_replace_symbol_in_code_invalid_syntax():
    bad_code = "def foo(:"
    with pytest.raises(ValueError):
        ca._replace_symbol_in_code(bad_code, "foo", "def foo(): pass")


# ---------------------------------------------------------------------------
# Fixtures for handlers
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_context(tmp_path):
    """Create a minimal PlanExecutorContext-like object."""
    ctx = SimpleNamespace()
    ctx.file_handler = MagicMock()
    ctx.git_service = MagicMock()
    ctx.git_service.is_git_repo.return_value = True
    ctx.git_service.add = MagicMock()
    ctx.git_service.commit = MagicMock()
    ctx.auditor_context = MagicMock()
    ctx.file_handler.repo_path = tmp_path
    ctx.file_handler.add_pending_write = MagicMock(return_value="write_op")
    ctx.file_handler.confirm_write = MagicMock()
    return ctx


# ---------------------------------------------------------------------------
# CreateFileHandler tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_file_success(tmp_context, tmp_path, mocker):
    file_path = "file1.py"
    code = "print('hello')"
    params = SimpleNamespace(file_path=file_path, code=code)

    mocker.patch(
        "body.actions.code_actions.validate_code_async",
        AsyncMock(return_value={"status": "clean", "code": code}),
    )

    handler = ca.CreateFileHandler()
    await handler.execute(params, tmp_context)

    tmp_context.file_handler.add_pending_write.assert_called_once()
    tmp_context.git_service.add.assert_called_with(file_path)
    tmp_context.git_service.commit.assert_called()


@pytest.mark.asyncio
async def test_create_file_missing_params_raises(tmp_context):
    handler = ca.CreateFileHandler()
    params = SimpleNamespace(file_path=None, code=None)
    with pytest.raises(PlanExecutionError):
        await handler.execute(params, tmp_context)


@pytest.mark.asyncio
async def test_create_file_exists_raises(tmp_context, tmp_path):
    f = tmp_path / "exists.py"
    f.write_text("x=1")
    tmp_context.file_handler.repo_path = tmp_path
    params = SimpleNamespace(file_path="exists.py", code="print('x')")
    handler = ca.CreateFileHandler()
    with pytest.raises(FileExistsError):
        await handler.execute(params, tmp_context)


@pytest.mark.asyncio
async def test_create_file_validation_fails(tmp_context, mocker):
    params = SimpleNamespace(file_path="a.py", code="code")
    mocker.patch(
        "body.actions.code_actions.validate_code_async",
        AsyncMock(
            return_value={"status": "dirty", "violations": ["E1"], "code": "bad"}
        ),
    )
    handler = ca.CreateFileHandler()
    with pytest.raises(PlanExecutionError):
        await handler.execute(params, tmp_context)


# ---------------------------------------------------------------------------
# EditFileHandler tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_edit_file_success(tmp_context, tmp_path, mocker):
    f = tmp_path / "editme.py"
    f.write_text("print('old')")
    params = SimpleNamespace(file_path="editme.py", code="print('new')")
    mocker.patch(
        "body.actions.code_actions.validate_code_async",
        AsyncMock(return_value={"status": "clean", "code": "print('new')"}),
    )
    handler = ca.EditFileHandler()
    await handler.execute(params, tmp_context)
    tmp_context.file_handler.add_pending_write.assert_called()
    tmp_context.git_service.commit.assert_called()


@pytest.mark.asyncio
async def test_edit_file_missing_params(tmp_context):
    handler = ca.EditFileHandler()
    params = SimpleNamespace(file_path=None, code=None)
    with pytest.raises(PlanExecutionError):
        await handler.execute(params, tmp_context)


@pytest.mark.asyncio
async def test_edit_file_not_exists(tmp_context):
    handler = ca.EditFileHandler()
    params = SimpleNamespace(file_path="nofile.py", code="x=1")
    with pytest.raises(PlanExecutionError):
        await handler.execute(params, tmp_context)


@pytest.mark.asyncio
async def test_edit_file_validation_dirty(tmp_context, tmp_path, mocker):
    f = tmp_path / "x.py"
    f.write_text("a=1")
    params = SimpleNamespace(file_path="x.py", code="broken")
    mocker.patch(
        "body.actions.code_actions.validate_code_async",
        AsyncMock(return_value={"status": "dirty", "violations": ["E"], "code": "bad"}),
    )
    handler = ca.EditFileHandler()
    with pytest.raises(PlanExecutionError):
        await handler.execute(params, tmp_context)


# ---------------------------------------------------------------------------
# EditFunctionHandler tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_edit_function_success(tmp_context, tmp_path, mocker):
    f = tmp_path / "func.py"
    f.write_text("def foo():\n    return 1\n")
    new_func = "def foo():\n    return 2"
    params = SimpleNamespace(file_path="func.py", symbol_name="foo", code=new_func)

    mocker.patch(
        "body.actions.code_actions.validate_code_async",
        AsyncMock(return_value={"status": "clean", "code": new_func}),
    )

    handler = ca.EditFunctionHandler()
    await handler.execute(params, tmp_context)

    tmp_context.file_handler.add_pending_write.assert_called()
    tmp_context.git_service.commit.assert_called()


@pytest.mark.asyncio
async def test_edit_function_missing_params(tmp_context):
    handler = ca.EditFunctionHandler()
    params = SimpleNamespace(file_path=None, symbol_name=None, code=None)
    with pytest.raises(PlanExecutionError):
        await handler.execute(params, tmp_context)


@pytest.mark.asyncio
async def test_edit_function_file_not_found(tmp_context):
    handler = ca.EditFunctionHandler()
    params = SimpleNamespace(
        file_path="nofile.py", symbol_name="foo", code="def foo(): pass"
    )
    with pytest.raises(FileNotFoundError):
        await handler.execute(params, tmp_context)


@pytest.mark.asyncio
async def test_edit_function_validation_dirty(tmp_context, tmp_path, mocker):
    f = tmp_path / "f.py"
    f.write_text("def f():\n    pass\n")
    mocker.patch(
        "body.actions.code_actions.validate_code_async",
        AsyncMock(return_value={"status": "dirty", "violations": ["E"], "code": "bad"}),
    )
    params = SimpleNamespace(file_path="f.py", symbol_name="f", code="def f(): pass")
    handler = ca.EditFunctionHandler()
    with pytest.raises(PlanExecutionError):
        await handler.execute(params, tmp_context)


@pytest.mark.asyncio
async def test_edit_function_symbol_not_found(tmp_context, tmp_path, mocker):
    f = tmp_path / "g.py"
    f.write_text("def g():\n    pass\n")
    mocker.patch(
        "body.actions.code_actions.validate_code_async",
        AsyncMock(return_value={"status": "clean", "code": "def nope(): pass"}),
    )
    params = SimpleNamespace(
        file_path="g.py", symbol_name="not_there", code="def nope(): pass"
    )
    handler = ca.EditFunctionHandler()
    with pytest.raises(PlanExecutionError):
        await handler.execute(params, tmp_context)
