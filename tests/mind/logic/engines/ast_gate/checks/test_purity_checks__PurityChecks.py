"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/mind/logic/engines/ast_gate/checks/purity_checks.py
- Symbol: PurityChecks
- Status: 5 tests passed, some failed
- Passing tests: test_domain_matches_allowed, test_check_forbidden_decorators, test_check_forbidden_primitives, test_check_no_print_statements, test_check_no_direct_writes
- Generated: 2026-01-11 02:32:19
"""

from pathlib import Path

from mind.logic.engines.ast_gate.checks.purity_checks import PurityChecks
from shared.infrastructure.intent.filesystem_operations import (
    FsOperationEntry,
    FsOperationTaxonomy,
)


def _build_fs_taxonomy() -> FsOperationTaxonomy:
    """Synthetic FS taxonomy mirroring the production shape for #489 tests.

    Constructed in-memory rather than loaded from .intent/ so the unit
    tests stay decoupled from filesystem layout. Covers the entry shapes
    exercised by ``check_no_direct_writes``: leaf-match writes,
    qualified-match writes, the ``write_mode`` predicate, and the
    collision-prone leaves (``replace``/``rename``) declared qualified
    per the #489 trap resolution.
    """
    pathlib_entries = frozenset(
        [
            FsOperationEntry(
                name="write_text",
                op_class="write",
                match="leaf",
                namespace="pathlib_path",
            ),
            FsOperationEntry(
                name="write_bytes",
                op_class="write",
                match="leaf",
                namespace="pathlib_path",
            ),
            FsOperationEntry(
                name="unlink",
                op_class="write",
                match="leaf",
                namespace="pathlib_path",
            ),
            FsOperationEntry(
                name="rmdir",
                op_class="write",
                match="leaf",
                namespace="pathlib_path",
            ),
            FsOperationEntry(
                name="mkdir",
                op_class="write",
                match="leaf",
                namespace="pathlib_path",
            ),
            FsOperationEntry(
                name="touch",
                op_class="write",
                match="leaf",
                namespace="pathlib_path",
            ),
            FsOperationEntry(
                name="chmod",
                op_class="write",
                match="leaf",
                namespace="pathlib_path",
            ),
            FsOperationEntry(
                name="open",
                op_class="write",
                match="leaf",
                namespace="pathlib_path",
                predicate="write_mode",
            ),
            # Collision-prone leaves declared qualified per #489 trap.
            FsOperationEntry(
                name="replace",
                op_class="write",
                match="qualified",
                namespace="pathlib_path",
            ),
            FsOperationEntry(
                name="rename",
                op_class="write",
                match="qualified",
                namespace="pathlib_path",
            ),
            # Read entries — must never trigger.
            FsOperationEntry(
                name="read_text",
                op_class="read",
                match="leaf",
                namespace="pathlib_path",
            ),
            FsOperationEntry(
                name="exists",
                op_class="read",
                match="leaf",
                namespace="pathlib_path",
            ),
        ]
    )
    watched_entries = frozenset(
        [
            FsOperationEntry(
                name="open",
                op_class="write",
                match="qualified",
                namespace="watched",
                predicate="write_mode",
            ),
            FsOperationEntry(
                name="os.replace",
                op_class="write",
                match="qualified",
                namespace="watched",
            ),
            FsOperationEntry(
                name="os.rename",
                op_class="write",
                match="qualified",
                namespace="watched",
            ),
            FsOperationEntry(
                name="os.remove",
                op_class="write",
                match="qualified",
                namespace="watched",
            ),
            FsOperationEntry(
                name="os.mkdir",
                op_class="write",
                match="qualified",
                namespace="watched",
            ),
            FsOperationEntry(
                name="shutil.rmtree",
                op_class="write",
                match="qualified",
                namespace="watched",
            ),
            FsOperationEntry(
                name="shutil.copyfile",
                op_class="write",
                match="qualified",
                namespace="watched",
            ),
        ]
    )
    return FsOperationTaxonomy(
        pathlib_path=pathlib_entries,
        watched=watched_entries,
        python_version="3.12",
    )


class TestPurityChecks:
    def test_domain_matches_allowed(self):
        """Domain matching moved to ``ASTHelpers.domain_matches`` in
        ``mind.logic.engines.ast_gate.base`` — the autogen vintage called
        a ``PurityChecks._domain_matches_allowed`` private helper that no
        longer exists on the class. Asserting on the live helper instead."""
        from mind.logic.engines.ast_gate.base import ASTHelpers

        assert ASTHelpers.domain_matches("mind.logic", ["mind.logic"])
        assert ASTHelpers.domain_matches("mind.logic.engines", ["mind.logic"])
        assert not ASTHelpers.domain_matches("other.domain", ["mind.logic"])
        assert ASTHelpers.domain_matches(
            "shared.infrastructure", ["mind.logic", "shared.infrastructure"]
        )
        assert not ASTHelpers.domain_matches("", ["mind.logic"])
        assert not ASTHelpers.domain_matches("mind.logic", [])
        assert not ASTHelpers.domain_matches("", [])

    def test_check_forbidden_decorators(self):
        """Test forbidden decorator checking.

        Message format drifted slightly: source now emits ``"Forbidden
        decorator 'X' on 'Y' (line N)."`` (no ``"function"`` qualifier
        between ``on`` and the name)."""
        import ast

        code = "@forbidden_decorator\ndef my_function():\n    pass\n\n@allowed.decorator\ndef another_function():\n    pass\n"
        tree = ast.parse(code)
        violations = PurityChecks.check_forbidden_decorators(
            tree, ["forbidden_decorator"]
        )
        assert violations == [
            "Forbidden decorator 'forbidden_decorator' on 'my_function' (line 1)."
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
        # Source's violation messages do not mention the allowed-domain
        # set (the autogen vintage assumed a richer format). Sufficient to
        # assert the primitives still fire when the file is outside the
        # allowed domains.
        assert len(violations) == 2
        assert "eval" in violations[0]
        assert "exec" in violations[1]
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
        code_bare = "from os import system\ndef f():\n    system('ls')\n"
        violations = PurityChecks.check_forbidden_primitives(
            ast.parse(code_bare), forbidden
        )
        assert len(violations) == 1
        assert "os.system" in violations[0]

        # 2. Module alias form.
        code_mod_alias = "import os as o\ndef f():\n    o.system('ls')\n"
        violations = PurityChecks.check_forbidden_primitives(
            ast.parse(code_mod_alias), forbidden
        )
        assert len(violations) == 1
        assert "os.system" in violations[0]

        # 3. Aliased function-name form.
        code_func_alias = "from subprocess import Popen as P\ndef f():\n    P(['ls'])\n"
        violations = PurityChecks.check_forbidden_primitives(
            ast.parse(code_func_alias), forbidden
        )
        assert len(violations) == 1
        assert "subprocess.Popen" in violations[0]

        # 4. Dotted form still flagged (no regression).
        code_dotted = "import os\ndef f():\n    os.system('ls')\n"
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
        code_clean = "def system(x):\n    return x\ndef use():\n    system('hello')\n"
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
        """Baseline coverage: pathlib write methods + builtin open with predicate."""
        import ast

        taxonomy = _build_fs_taxonomy()
        code = 'def write_files():\n    # Path.write_text()\n    Path("file.txt").write_text("content")\n    \n    # Path.write_bytes()\n    Path("file.bin").write_bytes(b"content")\n    \n    # open() with write mode\n    with open("file.txt", "w") as f:\n        f.write("content")\n    \n    # open() with append mode\n    with open("file.txt", "a") as f:\n        f.write("more")\n    \n    # open() with read mode (should be allowed)\n    with open("file.txt", "r") as f:\n        content = f.read()\n    \n    # open() with mode keyword\n    with open("file.txt", mode="wb") as f:\n        f.write(b"content")\n'
        tree = ast.parse(code)
        violations = PurityChecks.check_no_direct_writes(tree, taxonomy=taxonomy)
        assert len(violations) == 5
        assert all("Use FileHandler." in v for v in violations)
        joined = "\n".join(violations)
        assert "'write_text'" in joined
        assert "'write_bytes'" in joined
        # open() in write/append/write-binary modes fires 3 times.
        assert joined.count("'open'") == 3

        code2 = 'def read_only():\n    content = Path("file.txt").read_text()\n    with open("file.txt", "r") as f:\n        return f.read()\n'
        tree2 = ast.parse(code2)
        violations = PurityChecks.check_no_direct_writes(tree2, taxonomy=taxonomy)
        assert violations == []

        code3 = 'def write_with_builtin():\n    f = open("file.txt", "w")\n    f.write("data")\n    f.close()\n'
        tree3 = ast.parse(code3)
        violations = PurityChecks.check_no_direct_writes(tree3, taxonomy=taxonomy)
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

        taxonomy = _build_fs_taxonomy()
        code = (
            "from pathlib import Path\n"
            "def deletes():\n"
            "    target = Path('foo.py')\n"
            "    target.unlink()                       # variable receiver\n"
            "    Path('bar/').rmdir()                  # Call receiver\n"
            "    cache_file.unlink()                   # variable receiver\n"
            "    obj.nested.path.unlink()              # multi-segment receiver\n"
        )
        violations = PurityChecks.check_no_direct_writes(
            ast.parse(code), taxonomy=taxonomy
        )
        assert len(violations) == 4
        joined = "\n".join(violations)
        assert "unlink" in joined
        assert "rmdir" in joined

        # Negative: bare method names not in the taxonomy (e.g. .close())
        # must NOT trigger.
        clean = "def reads():\n    f = open('x', 'r')\n    f.close()\n"
        assert (
            PurityChecks.check_no_direct_writes(ast.parse(clean), taxonomy=taxonomy)
            == []
        )

    def test_check_no_direct_writes_catches_bare_import_form(self):
        """Closes the bare-import bypass (#488).

        Watched-block qualified entries like ``os.replace`` resolve both the
        dotted form ``os.replace(...)`` and the bare-import form
        ``from os import replace; replace(...)`` via the alias-map
        translator. After #489 the qualified set is sourced from the
        taxonomy's watched block, not a per-mapping forbidden_additional
        list.
        """
        import ast

        taxonomy = _build_fs_taxonomy()

        # 1. Bare import — the bypass case.
        code_bare = "from os import replace\ndef mutate():\n    replace('a', 'b')\n"
        violations = PurityChecks.check_no_direct_writes(
            ast.parse(code_bare), taxonomy=taxonomy
        )
        assert len(violations) == 1
        assert "os.replace" in violations[0]

        # 2. Aliased import.
        code_alias = "from os import replace as r\ndef mutate():\n    r('a', 'b')\n"
        violations = PurityChecks.check_no_direct_writes(
            ast.parse(code_alias), taxonomy=taxonomy
        )
        assert len(violations) == 1
        assert "os.replace" in violations[0]

        # 3. `import ... as` for a module — Attribute receiver via alias.
        code_mod_alias = "import os as o\ndef mutate():\n    o.rename('a', 'b')\n"
        violations = PurityChecks.check_no_direct_writes(
            ast.parse(code_mod_alias), taxonomy=taxonomy
        )
        assert len(violations) == 1
        assert "os.rename" in violations[0]

        # 4. Dotted form still flagged (no regression).
        code_dotted = "import shutil\ndef mutate():\n    shutil.rmtree('dir')\n"
        violations = PurityChecks.check_no_direct_writes(
            ast.parse(code_dotted), taxonomy=taxonomy
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
            ast.parse(code_multi), taxonomy=taxonomy
        )
        assert len(violations) == 2
        joined = "\n".join(violations)
        assert "shutil.rmtree" in joined
        assert "shutil.copyfile" in joined

        # 6. Unrelated bare name — no false positive (collision check).
        # The local `replace` function shadows the bare name; the alias
        # map carries no entry for it, so qualified resolution returns
        # "replace" (not "os.replace") and matches no taxonomy entry.
        code_clean = (
            "def replace(a, b):\n    return a + b\ndef use():\n    replace('a', 'b')\n"
        )
        violations = PurityChecks.check_no_direct_writes(
            ast.parse(code_clean), taxonomy=taxonomy
        )
        assert violations == []

    def test_check_no_direct_writes_replace_rename_qualified_only(self):
        """#489 trap resolution: replace/rename declared qualified, not leaf.

        ``str.replace`` is the dominant collision (143 src/ sites). Naive
        leaf-match on the taxonomy's pathlib ``replace`` entry would fire
        on every string-replace call. The taxonomy declares both
        ``replace`` and ``rename`` as ``match: qualified`` for the
        pathlib_path block; the check honors that per-entry setting.

        Net behavior: qualified module forms (``os.replace``,
        ``os.rename``) still fire; bare string/dict/list ``.replace(...)``
        do not; ``Path("x").replace(target)`` does not fire (the Call
        receiver is unresolvable through resolve_qualified_name — this is
        a pre-existing accepted gap, see #489 follow-up).
        """
        import ast

        taxonomy = _build_fs_taxonomy()

        # str.replace collision — must NOT fire.
        code_str = (
            "def normalize(s):\n    return s.replace('a', 'b').replace('c', 'd')\n"
        )
        assert (
            PurityChecks.check_no_direct_writes(ast.parse(code_str), taxonomy=taxonomy)
            == []
        )

        # os.replace via qualified — MUST fire.
        code_os = "import os\ndef m():\n    os.replace('a', 'b')\n"
        violations = PurityChecks.check_no_direct_writes(
            ast.parse(code_os), taxonomy=taxonomy
        )
        assert len(violations) == 1
        assert "os.replace" in violations[0]

        # Path("x").replace(target) — Call receiver, unresolvable
        # qualified; today's pre-existing accepted gap. No fire expected.
        code_path = "from pathlib import Path\ndef m():\n    Path('a').replace('b')\n"
        assert (
            PurityChecks.check_no_direct_writes(ast.parse(code_path), taxonomy=taxonomy)
            == []
        )

        # Variable-receiver Path.replace — same gap.
        code_var = (
            "from pathlib import Path\n"
            "def m():\n"
            "    p = Path('a')\n"
            "    p.replace('b')\n"
        )
        assert (
            PurityChecks.check_no_direct_writes(ast.parse(code_var), taxonomy=taxonomy)
            == []
        )

    def test_check_no_direct_writes_variable_receiver_write_text(self):
        """#489 new behavior: leaf-match catches variable-receiver writes.

        Pre-#489, ``check_no_direct_writes`` matched ``write_text`` /
        ``write_bytes`` via full_attr_name, which only resolved when the
        receiver was a Call (``Path("x").write_text(...)``). After #489
        the taxonomy declares these as ``match: leaf``, so the
        variable-receiver form ``p.write_text(...)`` is now caught — the
        same closure the deletion-leaf entries (``unlink``/``rmdir``)
        gained under ADR-071 D2.2.
        """
        import ast

        taxonomy = _build_fs_taxonomy()
        code = (
            "from pathlib import Path\n"
            "def writes():\n"
            "    p = Path('out.txt')\n"
            "    p.write_text('hello')\n"
            "    obj.cached.path.write_bytes(b'data')\n"
        )
        violations = PurityChecks.check_no_direct_writes(
            ast.parse(code), taxonomy=taxonomy
        )
        assert len(violations) == 2
        joined = "\n".join(violations)
        assert "write_text" in joined
        assert "write_bytes" in joined

    def test_check_no_direct_writes_gains_mkdir_touch_chmod_coverage(self):
        """#489 new coverage: pathlib mkdir/touch/chmod become first-class.

        ADR-077 §4 named these as silent gaps in the pre-#489 baseline.
        The taxonomy seeds them as leaf-match write entries, and the
        check now catches both the variable-receiver and Call-receiver
        forms.
        """
        import ast

        taxonomy = _build_fs_taxonomy()
        code = (
            "from pathlib import Path\n"
            "def mutates():\n"
            "    p = Path('dir')\n"
            "    p.mkdir(parents=True)\n"
            "    p.touch()\n"
            "    p.chmod(0o755)\n"
            "    Path('x').mkdir()\n"
        )
        violations = PurityChecks.check_no_direct_writes(
            ast.parse(code), taxonomy=taxonomy
        )
        assert len(violations) == 4
        joined = "\n".join(violations)
        assert "mkdir" in joined
        assert "touch" in joined
        assert "chmod" in joined

        # os.mkdir qualified — also covered, but the display name comes
        # from the leaf match (`mkdir`) because the taxonomy has both
        # pathlib_path leaf-`mkdir` AND watched qualified-`os.mkdir`, and
        # the check's candidate loop picks leaf first. The violation
        # still fires correctly on the right line; only the displayed
        # name is the less-specific bare form. The leaf-first ordering
        # is a deliberate choice in 5750fcc6's canonical check body.
        code_os = "import os\ndef m():\n    os.mkdir('x')\n"
        violations = PurityChecks.check_no_direct_writes(
            ast.parse(code_os), taxonomy=taxonomy
        )
        assert len(violations) == 1
        assert "mkdir" in violations[0]
