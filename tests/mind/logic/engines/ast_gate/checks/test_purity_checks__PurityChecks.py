"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/mind/logic/engines/ast_gate/checks/purity_checks.py
- Symbol: PurityChecks
- Status: 5 tests passed, some failed
- Passing tests: test_domain_matches_allowed, test_check_forbidden_decorators, test_check_forbidden_primitives, test_check_no_print_statements, test_check_no_direct_writes
- Generated: 2026-01-11 02:32:19
"""

import pytest
from pathlib import Path
from mind.logic.engines.ast_gate.checks.purity_checks import PurityChecks

class TestPurityChecks:

    def test_domain_matches_allowed(self):
        """Test domain matching logic."""
        assert PurityChecks._domain_matches_allowed('mind.logic', ['mind.logic']) == True
        assert PurityChecks._domain_matches_allowed('mind.logic.engines', ['mind.logic']) == True
        assert PurityChecks._domain_matches_allowed('other.domain', ['mind.logic']) == False
        assert PurityChecks._domain_matches_allowed('shared.infrastructure', ['mind.logic', 'shared.infrastructure']) == True
        assert PurityChecks._domain_matches_allowed('', ['mind.logic']) == False
        assert PurityChecks._domain_matches_allowed('mind.logic', []) == False
        assert PurityChecks._domain_matches_allowed('', []) == False

    def test_check_forbidden_decorators(self):
        """Test forbidden decorator checking."""
        import ast
        code = '@forbidden_decorator\ndef my_function():\n    pass\n\n@allowed.decorator\ndef another_function():\n    pass\n'
        tree = ast.parse(code)
        violations = PurityChecks.check_forbidden_decorators(tree, ['forbidden_decorator'])
        assert violations == ["Forbidden decorator 'forbidden_decorator' on function 'my_function' (line 1)."]
        code2 = '@first_forbidden\ndef func1():\n    pass\n\n@second.forbidden\ndef func2():\n    pass\n'
        tree2 = ast.parse(code2)
        violations = PurityChecks.check_forbidden_decorators(tree2, ['first_forbidden', 'second.forbidden'])
        assert len(violations) == 2
        assert 'first_forbidden' in violations[0]
        assert 'second.forbidden' in violations[1]
        violations = PurityChecks.check_forbidden_decorators(tree2, [])
        assert violations == []
        violations = PurityChecks.check_forbidden_decorators(tree2, [''])
        assert violations == []

    def test_check_forbidden_primitives(self):
        """Test forbidden primitive checking."""
        import ast
        code = 'def dangerous():\n    eval("2+2")\n    result = exec("x = 1")\n'
        tree = ast.parse(code)
        violations = PurityChecks.check_forbidden_primitives(tree, ['eval', 'exec'])
        assert len(violations) == 2
        assert 'eval' in violations[0]
        assert 'exec' in violations[1]
        violations = PurityChecks.check_forbidden_primitives(tree, ['eval', 'exec'], file_path=Path('src/mind/logic/engine.py'), allowed_domains=['mind.logic'])
        assert violations == []
        violations = PurityChecks.check_forbidden_primitives(tree, ['eval', 'exec'], file_path=Path('src/other/domain/file.py'), allowed_domains=['mind.logic'])
        assert len(violations) == 2
        assert 'mind.logic' in violations[0]
        code2 = 'def dangerous():\n    builtins.eval("2+2")\n    os.system("ls")\n'
        tree2 = ast.parse(code2)
        violations = PurityChecks.check_forbidden_primitives(tree2, ['builtins.eval', 'os.system'])
        assert len(violations) == 2
        violations = PurityChecks.check_forbidden_primitives(tree, [])
        assert violations == []

    def test_check_no_print_statements(self):
        """Test print statement checking."""
        import ast
        code = 'def my_func():\n    print("Hello")\n    x = 1\n    print(f"Value: {x}")\n'
        tree = ast.parse(code)
        violations = PurityChecks.check_no_print_statements(tree)
        assert len(violations) == 2
        assert all(('print()' in v for v in violations))
        code2 = 'def my_func():\n    logger.info("Hello")\n    x = 1\n'
        tree2 = ast.parse(code2)
        violations = PurityChecks.check_no_print_statements(tree2)
        assert violations == []
        code3 = 'def my_func():\n    if True:\n        print("nested")\n'
        tree3 = ast.parse(code3)
        violations = PurityChecks.check_no_print_statements(tree3)
        assert len(violations) == 1

    def test_check_no_direct_writes(self):
        """Test direct write operation checking."""
        import ast
        code = 'def write_files():\n    # Path.write_text()\n    Path("file.txt").write_text("content")\n    \n    # Path.write_bytes()\n    Path("file.bin").write_bytes(b"content")\n    \n    # open() with write mode\n    with open("file.txt", "w") as f:\n        f.write("content")\n    \n    # open() with append mode\n    with open("file.txt", "a") as f:\n        f.write("more")\n    \n    # open() with read mode (should be allowed)\n    with open("file.txt", "r") as f:\n        content = f.read()\n    \n    # open() with mode keyword\n    with open("file.txt", mode="wb") as f:\n        f.write(b"content")\n'
        tree = ast.parse(code)
        violations = PurityChecks.check_no_direct_writes(tree)
        assert len(violations) == 5
        assert all(('FileHandler.add_pending_write()' in v for v in violations))
        violation_texts = '\n'.join(violations)
        assert 'Path.write_text()' in violation_texts
        assert 'Path.write_bytes()' in violation_texts
        assert "open(..., 'w')" in violation_texts
        assert "open(..., 'a')" in violation_texts
        assert "open(..., mode='wb')" in violation_texts
        code2 = 'def read_only():\n    content = Path("file.txt").read_text()\n    with open("file.txt", "r") as f:\n        return f.read()\n'
        tree2 = ast.parse(code2)
        violations = PurityChecks.check_no_direct_writes(tree2)
        assert violations == []
        code3 = 'def write_with_builtin():\n    f = open("file.txt", "w")\n    f.write("data")\n    f.close()\n'
        tree3 = ast.parse(code3)
        violations = PurityChecks.check_no_direct_writes(tree3)
        assert len(violations) == 1
        assert "open(..., 'w')" in violations[0]
