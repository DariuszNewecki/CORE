"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/mind/logic/engines/ast_gate/checks/purity_checks.py
- Symbol: PurityChecks
- Status: 5 tests passed, some failed
- Passing tests: test_domain_matches_allowed, test_check_forbidden_decorators, test_check_forbidden_primitives, test_check_no_print_statements, test_check_no_direct_writes
- Generated: 2026-01-11 02:32:19
"""

from pathlib import Path

from mind.logic.engines.ast_gate.checks.purity_checks import PurityChecks


class TestPurityChecks:
    def test_domain_matches_allowed(self):
        """Test domain matching logic."""
        assert PurityChecks._domain_matches_allowed("mind.logic", ["mind.logic"])
        assert PurityChecks._domain_matches_allowed(
            "mind.logic.engines", ["mind.logic"]
        )
        assert not PurityChecks._domain_matches_allowed("other.domain", ["mind.logic"])
        assert PurityChecks._domain_matches_allowed(
            "shared.infrastructure", ["mind.logic", "shared.infrastructure"]
        )
        assert not PurityChecks._domain_matches_allowed("", ["mind.logic"])
        assert not PurityChecks._domain_matches_allowed("mind.logic", [])
        assert not PurityChecks._domain_matches_allowed("", [])

    def test_check_forbidden_decorators(self):
        """Test forbidden decorator checking."""
        import ast

        code = "@forbidden_decorator\ndef my_function():\n    pass\n\n@allowed.decorator\ndef another_function():\n    pass\n"
        tree = ast.parse(code)
        violations = PurityChecks.check_forbidden_decorators(
            tree, ["forbidden_decorator"]
        )
        assert violations == [
            "Forbidden decorator 'forbidden_decorator' on function 'my_function' (line 1)."
        ]
        code2 = "@first_forbidden\ndef func1():\n    pass\n\n@second.forbidden\ndef func2():\n    pass\n"
        tree2 = ast.parse(code2)
        violations = PurityChecks.check_forbidden_decorators(
            tree2, ["first_forbidden", "second.forbidden"]
        )
        assert len(violations) == 2
        assert "first_forbidden" in violations[0]
        assert "second.forbidden" in violations[1]
        violations = PurityChecks.check_forbidden_decorators(tree2, [])
        assert violations == []
        violations = PurityChecks.check_forbidden_decorators(tree2, [""])
        assert violations == []

    def test_check_forbidden_primitives(self):
        """Test forbidden primitive checking."""
        import ast

        code = 'def dangerous():\n    eval("2+2")\n    result = exec("x = 1")\n'
        tree = ast.parse(code)
        violations = PurityChecks.check_forbidden_primitives(tree, ["eval", "exec"])
        assert len(violations) == 2
        assert "eval" in violations[0]
        assert "exec" in violations[1]
        violations = PurityChecks.check_forbidden_primitives(
            tree,
            ["eval", "exec"],
            file_path=Path("src/mind/logic/engine.py"),
            allowed_domains=["mind.logic"],
        )
        assert violations == []
        violations = PurityChecks.check_forbidden_primitives(
            tree,
            ["eval", "exec"],
            file_path=Path("src/other/domain/file.py"),
            allowed_domains=["mind.logic"],
        )
        assert len(violations) == 2
        assert "mind.logic" in violations[0]
        code2 = 'def dangerous():\n    builtins.eval("2+2")\n    os.system("ls")\n'
        tree2 = ast.parse(code2)
        violations = PurityChecks.check_forbidden_primitives(
            tree2, ["builtins.eval", "os.system"]
        )
        assert len(violations) == 2
        violations = PurityChecks.check_forbidden_primitives(tree, [])
        assert violations == []

    def test_check_forbidden_primitives_catches_bare_import_form(self):
        """Closes the bare-import bypass sibling of #488.

        Pre-fix: `from os import system; system(...)` and `import os as o;
        o.system(...)` slipped through because full_attr_name returned
        "system" / "o.system", neither of which matched the qualified
        "os.system" in the forbidden list. The alias-map resolver now
        translates both shapes to the qualified form for matching.
        """
        import ast

        forbidden = ["os.system", "subprocess.Popen"]

        # 1. Bare-import form.
        code_bare = (
            "from os import system\n"
            "def f():\n"
            "    system('ls')\n"
        )
        violations = PurityChecks.check_forbidden_primitives(
            ast.parse(code_bare), forbidden
        )
        assert len(violations) == 1
        assert "os.system" in violations[0]

        # 2. Module alias form.
        code_mod_alias = (
            "import os as o\n"
            "def f():\n"
            "    o.system('ls')\n"
        )
        violations = PurityChecks.check_forbidden_primitives(
            ast.parse(code_mod_alias), forbidden
        )
        assert len(violations) == 1
        assert "os.system" in violations[0]

        # 3. Aliased function-name form.
        code_func_alias = (
            "from subprocess import Popen as P\n"
            "def f():\n"
            "    P(['ls'])\n"
        )
        violations = PurityChecks.check_forbidden_primitives(
            ast.parse(code_func_alias), forbidden
        )
        assert len(violations) == 1
        assert "subprocess.Popen" in violations[0]

        # 4. Dotted form still flagged (no regression).
        code_dotted = (
            "import os\n"
            "def f():\n"
            "    os.system('ls')\n"
        )
        violations = PurityChecks.check_forbidden_primitives(
            ast.parse(code_dotted), forbidden
        )
        assert len(violations) == 1
        assert "os.system" in violations[0]

        # 5. Locally-shadowed name — accepted false positive trade.
        # The alias_map resolution does not track reassignment; documented
        # in build_import_alias_map docstring as the conservative trade.
        # Test omitted (intentional behavior, not a bug).

        # 6. Unrelated bare name — no false positive.
        code_clean = (
            "def system(x):\n"
            "    return x\n"
            "def use():\n"
            "    system('hello')\n"
        )
        violations = PurityChecks.check_forbidden_primitives(
            ast.parse(code_clean), forbidden
        )
        assert violations == []

    def test_check_no_print_statements(self):
        """Test print statement checking."""
        import ast

        code = (
            'def my_func():\n    print("Hello")\n    x = 1\n    print(f"Value: {x}")\n'
        )
        tree = ast.parse(code)
        violations = PurityChecks.check_no_print_statements(tree)
        assert len(violations) == 2
        assert all("print()" in v for v in violations)
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
        assert all("Use FileHandler." in v for v in violations)
        joined = "\n".join(violations)
        assert "'write_text'" in joined
        assert "'write_bytes'" in joined
        # open() in write/append/write-binary modes fires 3 times.
        assert joined.count("'open'") == 3
        code2 = 'def read_only():\n    content = Path("file.txt").read_text()\n    with open("file.txt", "r") as f:\n        return f.read()\n'
        tree2 = ast.parse(code2)
        violations = PurityChecks.check_no_direct_writes(tree2)
        assert violations == []
        code3 = 'def write_with_builtin():\n    f = open("file.txt", "w")\n    f.write("data")\n    f.close()\n'
        tree3 = ast.parse(code3)
        violations = PurityChecks.check_no_direct_writes(tree3)
        assert len(violations) == 1
        assert "'open'" in violations[0]

    def test_check_no_direct_writes_catches_bare_unlink_and_rmdir(self):
        """Closes the deletion gap (ADR-071 D2.2 / #451).

        Method-leaf matching for unlink/rmdir catches both the Call-receiver
        form (Path('x').unlink()) AND the variable-receiver form
        (target.unlink(), pathobj.unlink()). The real production violations
        that motivated this rule were all variable-receiver — relying on
        full_attr_name alone would have missed them.
        """
        import ast

        code = (
            "from pathlib import Path\n"
            "def deletes():\n"
            "    target = Path('foo.py')\n"
            "    target.unlink()                       # variable receiver\n"
            "    Path('bar/').rmdir()                  # Call receiver\n"
            "    cache_file.unlink()                   # variable receiver\n"
            "    obj.nested.path.unlink()              # multi-segment receiver\n"
        )
        violations = PurityChecks.check_no_direct_writes(ast.parse(code))
        assert len(violations) == 4
        joined = "\n".join(violations)
        assert "unlink" in joined
        assert "rmdir" in joined

        # Negative: bare method names not in the baseline (e.g. .close())
        # must NOT trigger.
        clean = "def reads():\n    f = open('x', 'r')\n    f.close()\n"
        assert PurityChecks.check_no_direct_writes(ast.parse(clean)) == []

    def test_check_no_direct_writes_catches_bare_import_form(self):
        """Closes the bare-import bypass (#488).

        `forbidden_additional` lists qualified names like 'os.replace'.
        Before #488 only the dotted form `os.replace(...)` matched;
        `from os import replace; replace(...)` slipped through because
        full_attr_name returned 'replace', not 'os.replace'. The alias-map
        resolver now translates Name-form callees back to the qualified
        form so both shapes are detected.
        """
        import ast

        forbidden = [
            "os.replace",
            "os.rename",
            "shutil.rmtree",
            "shutil.copyfile",
        ]

        # 1. Bare import — the bypass case.
        code_bare = (
            "from os import replace\n"
            "def mutate():\n"
            "    replace('a', 'b')\n"
        )
        violations = PurityChecks.check_no_direct_writes(
            ast.parse(code_bare), forbidden_additional=forbidden
        )
        assert len(violations) == 1
        assert "os.replace" in violations[0]

        # 2. Aliased import.
        code_alias = (
            "from os import replace as r\n"
            "def mutate():\n"
            "    r('a', 'b')\n"
        )
        violations = PurityChecks.check_no_direct_writes(
            ast.parse(code_alias), forbidden_additional=forbidden
        )
        assert len(violations) == 1
        assert "os.replace" in violations[0]

        # 3. `import ... as` for a module — Attribute receiver via alias.
        code_mod_alias = (
            "import os as o\n"
            "def mutate():\n"
            "    o.rename('a', 'b')\n"
        )
        violations = PurityChecks.check_no_direct_writes(
            ast.parse(code_mod_alias), forbidden_additional=forbidden
        )
        assert len(violations) == 1
        assert "os.rename" in violations[0]

        # 4. Dotted form still flagged (no regression).
        code_dotted = (
            "import shutil\n"
            "def mutate():\n"
            "    shutil.rmtree('dir')\n"
        )
        violations = PurityChecks.check_no_direct_writes(
            ast.parse(code_dotted), forbidden_additional=forbidden
        )
        assert len(violations) == 1
        assert "shutil.rmtree" in violations[0]

        # 5. Multiple bare imports in one module — all flagged.
        code_multi = (
            "from shutil import rmtree, copyfile\n"
            "def mutate():\n"
            "    rmtree('a')\n"
            "    copyfile('a', 'b')\n"
        )
        violations = PurityChecks.check_no_direct_writes(
            ast.parse(code_multi), forbidden_additional=forbidden
        )
        assert len(violations) == 2
        joined = "\n".join(violations)
        assert "shutil.rmtree" in joined
        assert "shutil.copyfile" in joined

        # 6. Unrelated bare name — no false positive (collision check).
        code_clean = (
            "def replace(a, b):\n"
            "    return a + b\n"
            "def use():\n"
            "    replace('a', 'b')\n"
        )
        violations = PurityChecks.check_no_direct_writes(
            ast.parse(code_clean), forbidden_additional=forbidden
        )
        assert violations == []
