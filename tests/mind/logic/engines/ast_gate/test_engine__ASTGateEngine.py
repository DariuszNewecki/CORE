"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/mind/logic/engines/ast_gate/engine.py
- Symbol: ASTGateEngine
- Status: 14 tests passed, some failed
- Passing tests: test_verify_unknown_check_type, test_verify_empty_check_type, test_verify_parse_error, test_verify_no_print_statements_compliant, test_verify_no_print_statements_violation, test_verify_forbidden_assignments, test_verify_write_defaults_false_violation, test_verify_write_defaults_false_compliant, test_verify_max_file_lines_violation, test_verify_decorator_args, test_verify_stable_id_anchor, test_verify_import_boundary, test_supported_check_types, test_verify_all_supported_check_types_exist
- Generated: 2026-01-11 02:26:12
"""

import pytest
from pathlib import Path
from mind.logic.engines.ast_gate.engine import ASTGateEngine

@pytest.mark.asyncio
async def test_verify_unknown_check_type():
    """Test that unknown check_type returns error result."""
    engine = ASTGateEngine()
    file_path = Path('/tmp/test.py')
    file_path.write_text("print('test')")
    result = await engine.verify(file_path, {'check_type': 'unknown_check'})
    assert result.ok == False
    assert "Logic Error: Unknown check_type 'unknown_check'" in result.message
    assert result.violations == []
    assert result.engine_id == 'ast_gate'

@pytest.mark.asyncio
async def test_verify_empty_check_type():
    """Test that empty check_type returns error result."""
    engine = ASTGateEngine()
    file_path = Path('/tmp/test.py')
    file_path.write_text("print('test')")
    result = await engine.verify(file_path, {'check_type': ''})
    assert result.ok == False
    assert "Logic Error: Unknown check_type ''" in result.message
    assert result.violations == []
    assert result.engine_id == 'ast_gate'

@pytest.mark.asyncio
async def test_verify_parse_error():
    """Test that invalid Python syntax returns parse error."""
    engine = ASTGateEngine()
    file_path = Path('/tmp/test.py')
    file_path.write_text('def invalid syntax')
    result = await engine.verify(file_path, {'check_type': 'no_print_statements'})
    assert result.ok == False
    assert 'Parse Error:' in result.message
    assert result.violations == []
    assert result.engine_id == 'ast_gate'

@pytest.mark.asyncio
async def test_verify_no_print_statements_compliant():
    """Test no_print_statements check with compliant code."""
    engine = ASTGateEngine()
    file_path = Path('/tmp/test.py')
    file_path.write_text('def foo():\n    pass')
    result = await engine.verify(file_path, {'check_type': 'no_print_statements'})
    assert result.ok == True
    assert result.message == 'AST Gate: Compliant'
    assert result.violations == []
    assert result.engine_id == 'ast_gate'

@pytest.mark.asyncio
async def test_verify_no_print_statements_violation():
    """Test no_print_statements check with print statement."""
    engine = ASTGateEngine()
    file_path = Path('/tmp/test.py')
    file_path.write_text("print('hello')")
    result = await engine.verify(file_path, {'check_type': 'no_print_statements'})
    assert result.ok == False
    assert result.message == 'AST Gate: Violations found'
    assert len(result.violations) > 0
    assert 'print' in result.violations[0]
    assert result.engine_id == 'ast_gate'

@pytest.mark.asyncio
async def test_verify_forbidden_assignments():
    """Test forbidden_assignments check."""
    engine = ASTGateEngine()
    file_path = Path('/tmp/test.py')
    file_path.write_text("SECRET_KEY = 'abc123'")
    result = await engine.verify(file_path, {'check_type': 'forbidden_assignments', 'targets': ['SECRET_KEY', 'API_KEY']})
    assert result.ok == False
    assert result.message == 'AST Gate: Violations found'
    assert len(result.violations) > 0
    assert 'SECRET_KEY' in result.violations[0]
    assert result.engine_id == 'ast_gate'

@pytest.mark.asyncio
async def test_verify_write_defaults_false_violation():
    """Test write_defaults_false check with violation."""
    engine = ASTGateEngine()
    file_path = Path('/tmp/test.py')
    file_path.write_text('def foo(write=True):\n    pass')
    result = await engine.verify(file_path, {'check_type': 'write_defaults_false'})
    assert result.ok == False
    assert result.message == 'AST Gate: Violations found'
    assert len(result.violations) > 0
    assert 'write' in result.violations[0]
    assert 'must default to False' in result.violations[0]
    assert result.engine_id == 'ast_gate'

@pytest.mark.asyncio
async def test_verify_write_defaults_false_compliant():
    """Test write_defaults_false check with compliant code."""
    engine = ASTGateEngine()
    file_path = Path('/tmp/test.py')
    file_path.write_text('def foo(write=False):\n    pass')
    result = await engine.verify(file_path, {'check_type': 'write_defaults_false'})
    assert result.ok == True
    assert result.message == 'AST Gate: Compliant'
    assert result.violations == []
    assert result.engine_id == 'ast_gate'

@pytest.mark.asyncio
async def test_verify_max_file_lines_violation():
    """Test max_file_lines check with violation."""
    engine = ASTGateEngine()
    file_path = Path('/tmp/test.py')
    lines = [f'line_{i} = {i}' for i in range(500)]
    file_path.write_text('\n'.join(lines))
    result = await engine.verify(file_path, {'check_type': 'max_file_lines', 'limit': 400})
    assert result.ok == False
    assert result.message == 'AST Gate: Violations found'
    assert len(result.violations) > 0
    assert result.engine_id == 'ast_gate'

@pytest.mark.asyncio
async def test_verify_decorator_args():
    """Test decorator_args check."""
    engine = ASTGateEngine()
    file_path = Path('/tmp/test.py')
    file_path.write_text('@my_decorator\ndef foo():\n    pass')
    result = await engine.verify(file_path, {'check_type': 'decorator_args', 'decorator': 'my_decorator', 'required_args': ['arg1', 'arg2']})
    assert result.ok == False
    assert result.message == 'AST Gate: Violations found'
    assert result.engine_id == 'ast_gate'

@pytest.mark.asyncio
async def test_verify_stable_id_anchor():
    """Test stable_id_anchor check."""
    engine = ASTGateEngine()
    file_path = Path('/tmp/test.py')
    file_path.write_text("id = 'unstable'")
    result = await engine.verify(file_path, {'check_type': 'stable_id_anchor'})
    assert result.engine_id == 'ast_gate'

@pytest.mark.asyncio
async def test_verify_import_boundary():
    """Test import_boundary check."""
    engine = ASTGateEngine()
    file_path = Path('/tmp/test.py')
    file_path.write_text('import forbidden_module')
    result = await engine.verify(file_path, {'check_type': 'import_boundary', 'forbidden': ['forbidden_module']})
    assert result.ok == False
    assert result.message == 'AST Gate: Violations found'
    assert result.engine_id == 'ast_gate'

@pytest.mark.asyncio
async def test_supported_check_types():
    """Test supported_check_types class method."""
    supported = ASTGateEngine.supported_check_types()
    assert isinstance(supported, set)
    assert 'no_print_statements' in supported
    assert 'import_boundary' in supported
    assert 'max_file_lines' in supported
    assert len(supported) > 0

@pytest.mark.asyncio
async def test_verify_all_supported_check_types_exist():
    """Verify all check types in _SUPPORTED_CHECK_TYPES can be referenced."""
    engine = ASTGateEngine()
    file_path = Path('/tmp/test.py')
    file_path.write_text('pass')
    for check_type in ASTGateEngine._SUPPORTED_CHECK_TYPES:
        result = await engine.verify(file_path, {'check_type': check_type})
        assert result.engine_id == 'ast_gate'
        assert 'Logic Error: Unknown check_type' not in result.message
