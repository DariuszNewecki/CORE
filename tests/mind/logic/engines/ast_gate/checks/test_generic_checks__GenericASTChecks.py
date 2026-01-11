"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/mind/logic/engines/ast_gate/checks/generic_checks.py
- Symbol: GenericASTChecks
- Status: 26 tests passed, some failed
- Passing tests: test_is_selected_empty_selector_returns_true, test_is_selected_has_decorator_matching, test_is_selected_has_decorator_call_matching, test_is_selected_has_decorator_no_match, test_is_selected_has_decorator_no_decorator_list, test_is_selected_name_regex_matching, test_is_selected_name_regex_no_match, test_is_selected_name_regex_no_name_attribute, test_is_selected_unknown_selector_returns_true, test_validate_requirement_no_check_type_returns_none, test_validate_requirement_returns_type_matching, test_validate_requirement_returns_type_no_returns, test_validate_requirement_returns_type_mismatch, test_validate_requirement_returns_type_non_function_node, test_validate_requirement_forbidden_calls_no_violation, test_validate_requirement_forbidden_calls_with_violation, test_validate_requirement_required_calls_missing, test_validate_requirement_forbidden_imports_no_violation, test_validate_requirement_forbidden_imports_violation_import, test_validate_requirement_forbidden_imports_violation_import_dotted, test_validate_requirement_forbidden_imports_violation_importfrom, test_validate_requirement_decorator_args_all_present, test_validate_requirement_decorator_args_missing, test_validate_requirement_decorator_args_not_call, test_validate_requirement_decorator_args_wrong_decorator, test_validate_requirement_decorator_args_no_decorator_list
- Generated: 2026-01-11 02:34:37
"""

import pytest
import ast
import re
from mind.logic.engines.ast_gate.checks.generic_checks import GenericASTChecks

class TestGenericASTChecksIsSelected:

    def test_is_selected_empty_selector_returns_true(self):
        """Empty selector should always return True"""
        node = ast.FunctionDef(name='test_func', args=ast.arguments(), body=[], decorator_list=[])
        result = GenericASTChecks.is_selected(node, {})
        assert result == True

    def test_is_selected_has_decorator_matching(self):
        """Should return True when node has matching decorator"""
        decorator = ast.Name(id='decorator', ctx=ast.Load())
        node = ast.FunctionDef(name='test_func', args=ast.arguments(), body=[], decorator_list=[decorator])
        selector = {'has_decorator': 'decorator'}
        result = GenericASTChecks.is_selected(node, selector)
        assert result == True

    def test_is_selected_has_decorator_call_matching(self):
        """Should return True when node has matching decorator call"""
        func = ast.Name(id='decorator', ctx=ast.Load())
        keywords = [ast.keyword(arg='arg', value=ast.Constant(value='value'))]
        decorator_call = ast.Call(func=func, args=[], keywords=keywords)
        node = ast.FunctionDef(name='test_func', args=ast.arguments(), body=[], decorator_list=[decorator_call])
        selector = {'has_decorator': 'decorator'}
        result = GenericASTChecks.is_selected(node, selector)
        assert result == True

    def test_is_selected_has_decorator_no_match(self):
        """Should return False when node doesn't have matching decorator"""
        decorator = ast.Name(id='other_decorator', ctx=ast.Load())
        node = ast.FunctionDef(name='test_func', args=ast.arguments(), body=[], decorator_list=[decorator])
        selector = {'has_decorator': 'decorator'}
        result = GenericASTChecks.is_selected(node, selector)
        assert result == False

    def test_is_selected_has_decorator_no_decorator_list(self):
        """Should return False when node has no decorator_list attribute"""
        node = ast.Expr(value=ast.Constant(value='test'))
        selector = {'has_decorator': 'decorator'}
        result = GenericASTChecks.is_selected(node, selector)
        assert result == False

    def test_is_selected_name_regex_matching(self):
        """Should return True when node name matches regex"""
        node = ast.FunctionDef(name='test_function', args=ast.arguments(), body=[], decorator_list=[])
        selector = {'name_regex': '^test_.*'}
        result = GenericASTChecks.is_selected(node, selector)
        assert result == True

    def test_is_selected_name_regex_no_match(self):
        """Should return False when node name doesn't match regex"""
        node = ast.FunctionDef(name='my_function', args=ast.arguments(), body=[], decorator_list=[])
        selector = {'name_regex': '^test_.*'}
        result = GenericASTChecks.is_selected(node, selector)
        assert result == False

    def test_is_selected_name_regex_no_name_attribute(self):
        """Should return False when node has no name attribute"""
        node = ast.Expr(value=ast.Constant(value='test'))
        selector = {'name_regex': '^test_.*'}
        result = GenericASTChecks.is_selected(node, selector)
        assert result == False

    def test_is_selected_unknown_selector_returns_true(self):
        """Should return True for unknown selector type"""
        node = ast.FunctionDef(name='test_func', args=ast.arguments(), body=[], decorator_list=[])
        selector = {'unknown_key': 'value'}
        result = GenericASTChecks.is_selected(node, selector)
        assert result == True

class TestGenericASTChecksValidateRequirement:

    def test_validate_requirement_no_check_type_returns_none(self):
        """Should return None when no check_type specified"""
        node = ast.FunctionDef(name='test_func', args=ast.arguments(), body=[], decorator_list=[])
        requirement = {'some_key': 'value'}
        result = GenericASTChecks.validate_requirement(node, requirement)
        assert result == None

    def test_validate_requirement_returns_type_matching(self):
        """Should return None when return type matches expected"""
        returns = ast.Name(id='ActionResult', ctx=ast.Load())
        node = ast.FunctionDef(name='test_func', args=ast.arguments(), body=[], decorator_list=[], returns=returns)
        requirement = {'check_type': 'returns_type', 'expected': 'ActionResult'}
        result = GenericASTChecks.validate_requirement(node, requirement)
        assert result == None

    def test_validate_requirement_returns_type_no_returns(self):
        """Should return None when function has no return annotation (None type)"""
        node = ast.FunctionDef(name='test_func', args=ast.arguments(), body=[], decorator_list=[], returns=None)
        requirement = {'check_type': 'returns_type', 'expected': 'None'}
        result = GenericASTChecks.validate_requirement(node, requirement)
        assert result == None

    def test_validate_requirement_returns_type_mismatch(self):
        """Should return error string when return type doesn't match expected"""
        returns = ast.Name(id='WrongType', ctx=ast.Load())
        node = ast.FunctionDef(name='test_func', args=ast.arguments(), body=[], decorator_list=[], returns=returns)
        requirement = {'check_type': 'returns_type', 'expected': 'ActionResult'}
        result = GenericASTChecks.validate_requirement(node, requirement)
        assert result == "expected '-> ActionResult', found '-> WrongType'"

    def test_validate_requirement_returns_type_non_function_node(self):
        """Should return None when node is not a function definition"""
        node = ast.Expr(value=ast.Constant(value='test'))
        requirement = {'check_type': 'returns_type', 'expected': 'ActionResult'}
        result = GenericASTChecks.validate_requirement(node, requirement)
        assert result == None

    def test_validate_requirement_forbidden_calls_no_violation(self):
        """Should return None when no forbidden calls found"""
        call = ast.Call(func=ast.Name(id='allowed_func', ctx=ast.Load()), args=[], keywords=[])
        body = [ast.Expr(value=call)]
        node = ast.FunctionDef(name='test_func', args=ast.arguments(), body=body, decorator_list=[])
        requirement = {'check_type': 'forbidden_calls', 'calls': ['print', 'input']}
        result = GenericASTChecks.validate_requirement(node, requirement)
        assert result == None

    def test_validate_requirement_forbidden_calls_with_violation(self):
        """Should return error string when forbidden call found"""
        call = ast.Call(func=ast.Name(id='print', ctx=ast.Load()), args=[ast.Constant(value='test')], keywords=[])
        call.lineno = 42
        body = [ast.Expr(value=call)]
        node = ast.FunctionDef(name='test_func', args=ast.arguments(), body=body, decorator_list=[])
        requirement = {'check_type': 'forbidden_calls', 'calls': ['print', 'input']}
        result = GenericASTChecks.validate_requirement(node, requirement)
        assert result == "contains forbidden call 'print()' on line 42"

    def test_validate_requirement_required_calls_missing(self):
        """Should return error string when required calls are missing"""
        call = ast.Call(func=ast.Name(id='other_func', ctx=ast.Load()), args=[], keywords=[])
        body = [ast.Expr(value=call)]
        node = ast.FunctionDef(name='test_func', args=ast.arguments(), body=body, decorator_list=[])
        requirement = {'check_type': 'required_calls', 'calls': ['self.tracer.record', 'required_func']}
        result = GenericASTChecks.validate_requirement(node, requirement)
        assert result == "missing mandatory call(s): ['required_func', 'self.tracer.record']"

    def test_validate_requirement_forbidden_imports_no_violation(self):
        """Should return None when no forbidden imports found"""
        import_node = ast.Import(names=[ast.alias(name='os', asname=None)])
        body = [import_node]
        node = ast.FunctionDef(name='test_func', args=ast.arguments(), body=body, decorator_list=[])
        requirement = {'check_type': 'forbidden_imports', 'imports': ['rich', 'click']}
        result = GenericASTChecks.validate_requirement(node, requirement)
        assert result == None

    def test_validate_requirement_forbidden_imports_violation_import(self):
        """Should return error string when forbidden import found"""
        import_node = ast.Import(names=[ast.alias(name='rich', asname=None)])
        body = [import_node]
        node = ast.FunctionDef(name='test_func', args=ast.arguments(), body=body, decorator_list=[])
        requirement = {'check_type': 'forbidden_imports', 'imports': ['rich', 'click']}
        result = GenericASTChecks.validate_requirement(node, requirement)
        assert result == "contains forbidden import 'rich'"

    def test_validate_requirement_forbidden_imports_violation_import_dotted(self):
        """Should detect forbidden import even with dotted name"""
        import_node = ast.Import(names=[ast.alias(name='rich.panel', asname=None)])
        body = [import_node]
        node = ast.FunctionDef(name='test_func', args=ast.arguments(), body=body, decorator_list=[])
        requirement = {'check_type': 'forbidden_imports', 'imports': ['rich', 'click']}
        result = GenericASTChecks.validate_requirement(node, requirement)
        assert result == "contains forbidden import 'rich.panel'"

    def test_validate_requirement_forbidden_imports_violation_importfrom(self):
        """Should return error string when forbidden import-from found"""
        import_from = ast.ImportFrom(module='click', names=[ast.alias(name='command', asname=None)], level=0)
        body = [import_from]
        node = ast.FunctionDef(name='test_func', args=ast.arguments(), body=body, decorator_list=[])
        requirement = {'check_type': 'forbidden_imports', 'imports': ['rich', 'click']}
        result = GenericASTChecks.validate_requirement(node, requirement)
        assert result == "contains forbidden import-from 'click'"

    def test_validate_requirement_decorator_args_all_present(self):
        """Should return None when decorator has all required arguments"""
        func = ast.Name(id='atomic_action', ctx=ast.Load())
        keywords = [ast.keyword(arg='action_id', value=ast.Constant(value='test')), ast.keyword(arg='other_arg', value=ast.Constant(value='value'))]
        decorator_call = ast.Call(func=func, args=[], keywords=keywords)
        node = ast.FunctionDef(name='test_func', args=ast.arguments(), body=[], decorator_list=[decorator_call])
        requirement = {'check_type': 'decorator_args', 'decorator': 'atomic_action', 'required_kwargs': ['action_id', 'other_arg']}
        result = GenericASTChecks.validate_requirement(node, requirement)
        assert result == None

    def test_validate_requirement_decorator_args_missing(self):
        """Should return error string when decorator missing required arguments"""
        func = ast.Name(id='atomic_action', ctx=ast.Load())
        keywords = [ast.keyword(arg='action_id', value=ast.Constant(value='test'))]
        decorator_call = ast.Call(func=func, args=[], keywords=keywords)
        node = ast.FunctionDef(name='test_func', args=ast.arguments(), body=[], decorator_list=[decorator_call])
        requirement = {'check_type': 'decorator_args', 'decorator': 'atomic_action', 'required_kwargs': ['action_id', 'required_arg']}
        result = GenericASTChecks.validate_requirement(node, requirement)
        assert result == "decorator @atomic_action missing arguments: ['required_arg']"

    def test_validate_requirement_decorator_args_not_call(self):
        """Should return None when decorator is not a call (has no arguments)"""
        decorator = ast.Name(id='atomic_action', ctx=ast.Load())
        node = ast.FunctionDef(name='test_func', args=ast.arguments(), body=[], decorator_list=[decorator])
        requirement = {'check_type': 'decorator_args', 'decorator': 'atomic_action', 'required_kwargs': ['action_id']}
        result = GenericASTChecks.validate_requirement(node, requirement)
        assert result == "decorator @atomic_action missing arguments: ['action_id']"

    def test_validate_requirement_decorator_args_wrong_decorator(self):
        """Should return None when target decorator not found"""
        func = ast.Name(id='other_decorator', ctx=ast.Load())
        decorator_call = ast.Call(func=func, args=[], keywords=[])
        node = ast.FunctionDef(name='test_func', args=ast.arguments(), body=[], decorator_list=[decorator_call])
        requirement = {'check_type': 'decorator_args', 'decorator': 'atomic_action', 'required_kwargs': ['action_id']}
        result = GenericASTChecks.validate_requirement(node, requirement)
        assert result == None

    def test_validate_requirement_decorator_args_no_decorator_list(self):
        """Should return None when node has no decorator_list attribute"""
        node = ast.Expr(value=ast.Constant(value='test'))
        requirement = {'check_type': 'decorator_args', 'decorator': 'atomic_action', 'required_kwargs': ['action_id']}
        result = GenericASTChecks.validate_requirement(node, requirement)
        assert result == None
