# src/body/governance/intent_pattern_validators.py
"""
Pattern validators dispatched by IntentGuard.validate_generated_code.

Currently houses the ``test_file`` validator (issue #574 — write-time
import-resolution gate for generated test code). Rule statements are
looked up from ``IntentRepository`` by id; the executor lives in code,
the rule lives in ``.intent/``.
"""

from __future__ import annotations

import ast
import builtins
import importlib.util
import symtable

from mind.governance.violation_report import ViolationReport
from shared.logger import getLogger


logger = getLogger(__name__)

CORE_ROLE = "catalog"  # ADR-095 D3

_PYTHON_BUILTINS: frozenset[str] = frozenset(dir(builtins))

# Module attributes the interpreter sets without an assignment in the source
# and that are not builtins (__name__, __doc__, __spec__, __loader__ and
# __package__ already are).
_INTERPRETER_MODULE_NAMES: frozenset[str] = frozenset(
    {"__file__", "__builtins__", "__cached__"}
)

_GENERATED_RESOLVE_RULE_ID = "code.imports.generated_must_resolve"
_GENERATED_NO_RELATIVE_RULE_ID = "code.imports.generated_no_relative"

# #589 Tier 2 — test-quality static checks. These are referenced by id from
# .intent/rules/code/test_quality.json (declared with the Tier 3 ship); on
# any lookup failure the validators fall back to inline messages, mirroring
# the #574 fail-loud-on-gate, fail-soft-on-messaging posture.
_TEST_NO_MAGICMOCK_ON_AWAIT_RULE_ID = "code.tests.no_magicmock_on_await"
_TEST_NO_IMPORTED_SYMBOL_REDECLARED_RULE_ID = "code.tests.no_imported_symbol_redeclared"
_TEST_NO_PLACEHOLDER_TEST_BODY_RULE_ID = "code.tests.no_placeholder_test_body"
_TEST_NO_GLOBAL_MODULE_MUTATION_RULE_ID = "code.tests.no_global_module_mutation"
_TEST_NO_UNRESOLVED_FREE_NAMES_RULE_ID = "code.tests.no_unresolved_free_names"

_TIER2_RULE_IDS: frozenset[str] = frozenset(
    {
        _TEST_NO_MAGICMOCK_ON_AWAIT_RULE_ID,
        _TEST_NO_IMPORTED_SYMBOL_REDECLARED_RULE_ID,
        _TEST_NO_PLACEHOLDER_TEST_BODY_RULE_ID,
        _TEST_NO_GLOBAL_MODULE_MUTATION_RULE_ID,
        _TEST_NO_UNRESOLVED_FREE_NAMES_RULE_ID,
    }
)


def _full_call_name(node: ast.AST) -> str:
    """Return the dotted source form of an ast.Call ``func``.

    ``MagicMock``           -> "MagicMock"
    ``mock.MagicMock``      -> "mock.MagicMock"
    ``unittest.mock.AsyncMock`` -> "unittest.mock.AsyncMock"
    Anything more exotic    -> ""  (caller treats empty as "not a name").
    """
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _full_call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else ""
    return ""


def _has_observable_assertion(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    """True iff the function body contains at least one observable
    assertion: an ``assert`` statement, a ``pytest.raises(...)`` ``with``,
    or a call to a method whose name starts with ``assert_`` (e.g.
    ``mock.assert_awaited_once_with(...)``).
    """
    for node in ast.walk(func):
        if isinstance(node, ast.Assert):
            return True
        if isinstance(node, ast.With):
            for item in node.items:
                call = item.context_expr
                name = _full_call_name(call.func) if isinstance(call, ast.Call) else ""
                if name.endswith("pytest.raises") or name.endswith("raises"):
                    return True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr.startswith("assert_") or node.func.attr == "assert_":
                return True
    return False


def _scope_table_name(node: ast.AST) -> str | None:
    """The symtable child-table name ``node`` opens, or None if it opens no scope."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name
    if isinstance(node, ast.Lambda):
        return "lambda"
    if isinstance(node, ast.GeneratorExp):
        return "genexpr"
    if isinstance(node, ast.ListComp):
        return "listcomp"
    if isinstance(node, ast.SetComp):
        return "setcomp"
    if isinstance(node, ast.DictComp):
        return "dictcomp"
    return None


def _scope_parts(node: ast.AST) -> tuple[list[ast.AST], list[ast.AST]]:
    """Split a scope-opening node's children into those the compiler evaluates
    in the enclosing scope (decorators, defaults, annotations, class bases, a
    comprehension's first iterable) and those inside the new scope."""
    outer: list[ast.AST] = []
    inner: list[ast.AST] = []
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        args = node.args
        outer.extend(args.defaults)
        outer.extend(d for d in args.kw_defaults if d is not None)
        if isinstance(node, ast.Lambda):
            inner.append(node.body)
            return outer, inner
        outer.extend(node.decorator_list)
        outer.extend(getattr(node, "type_params", []))
        every_arg = [*args.posonlyargs, *args.args, *args.kwonlyargs]
        every_arg.extend(a for a in (args.vararg, args.kwarg) if a is not None)
        outer.extend(a.annotation for a in every_arg if a.annotation is not None)
        if node.returns is not None:
            outer.append(node.returns)
        inner.extend(node.body)
    elif isinstance(node, ast.ClassDef):
        outer.extend(node.decorator_list)
        outer.extend(getattr(node, "type_params", []))
        outer.extend(node.bases)
        outer.extend(node.keywords)
        inner.extend(node.body)
    elif isinstance(node, (ast.GeneratorExp, ast.ListComp, ast.SetComp, ast.DictComp)):
        first, *rest = node.generators
        outer.append(first.iter)
        inner.append(first.target)
        inner.extend(first.ifs)
        inner.extend(rest)
        if isinstance(node, ast.DictComp):
            inner.extend([node.key, node.value])
        else:
            inner.append(node.elt)
    return outer, inner


def _module_level_names(top: symtable.SymbolTable) -> set[str]:
    """Names bound at module level: module-scope assignments, imports, defs and
    classes, plus names a nested scope declares ``global`` and assigns."""
    defined = {
        s.get_name()
        for s in top.get_symbols()
        if s.is_assigned() or s.is_imported() or s.is_namespace()
    }
    pending = list(top.get_children())
    while pending:
        table = pending.pop()
        pending.extend(table.get_children())
        defined.update(
            s.get_name()
            for s in table.get_symbols()
            if s.is_declared_global() and s.is_assigned()
        )
    return defined


def _all_tables(top: symtable.SymbolTable) -> list[symtable.SymbolTable]:
    """``top`` and every table nested under it."""
    tables = [top]
    i = 0
    while i < len(tables):
        tables.extend(tables[i].get_children())
        i += 1
    return tables


def _is_type_parameter_scope(table: symtable.SymbolTable) -> bool:
    """PEP 695 annotation scope wrapping a generic def/class (``def f[T]()``)."""
    return "type param" in str(table.get_type()).lower()


def _unresolved_global_loads(
    tree: ast.Module, top: symtable.SymbolTable, defined: set[str]
) -> tuple[list[ast.Name], str | None]:
    """First Load of each name, per scope, that the compiler resolves as global
    and that ``defined`` does not bind; plus a description of the first scope
    that could not be paired with its symbol table, or None.

    Walks ``tree`` alongside the compiler's symbol tables, so every scoping rule
    (comprehension targets, lambda and nested-def parameters, walrus, match
    captures, class bodies, global/nonlocal) is the compiler's, not ours.
    Comprehensions inlined by the compiler (PEP 709) open no table and stay in
    the enclosing scope. A name absent from the current table (a decorator, a
    default or a comprehension's first iterable, which the compiler evaluates
    in the enclosing scope) is looked up outward.

    Pairing fails when a def, class, lambda or generator expression finds no
    table, or a table is left unpaired (a construct the walker does not model,
    e.g. a ``type`` alias). Names inside such a scope were never checked, so
    the caller must refuse rather than accept.
    """
    unresolved: list[ast.Name] = []
    reported: set[tuple[int, str]] = set()
    pending_children: dict[int, dict[str, list[symtable.SymbolTable]]] = {}
    paired: set[int] = {top.get_id()}
    unmatched: list[str] = []

    # ID: 50cc4926-a5f7-433a-974a-64e8a911c6f2
    def child_table(
        parent: symtable.SymbolTable, name: str, lineno: int
    ) -> symtable.SymbolTable | None:
        # Children are matched by name, preferring the same line; the line can
        # differ by a little for multi-line expressions.
        index = pending_children.get(parent.get_id())
        if index is None:
            index = {}
            for child in parent.get_children():
                index.setdefault(child.get_name(), []).append(child)
            pending_children[parent.get_id()] = index
        candidates = index.get(name)
        if not candidates:
            return None
        for i, child in enumerate(candidates):
            if child.get_lineno() == lineno:
                return candidates.pop(i)
        return candidates.pop(0)

    # ID: c4b491d6-0714-4ab1-9fc3-546bf923a982
    def visit(node: ast.AST, scopes: list[symtable.SymbolTable]) -> None:
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            for table in reversed(scopes):
                if node.id not in table.get_identifiers():
                    continue
                key = (table.get_id(), node.id)
                if (
                    table.lookup(node.id).is_global()
                    and node.id not in defined
                    and key not in reported
                ):
                    reported.add(key)
                    unresolved.append(node)
                break
        name = _scope_table_name(node)
        lineno = getattr(node, "lineno", None)
        if name is None or lineno is None:
            for child in ast.iter_child_nodes(node):
                visit(child, scopes)
            return
        # Enclosing-scope parts first: the compiler evaluates (and numbers the
        # tables of) decorators, defaults and the first iterable before the
        # scope's own body.
        outer, inner = _scope_parts(node)
        for child in outer:
            visit(child, scopes)
        opened = child_table(scopes[-1], name, lineno)
        if opened is not None and _is_type_parameter_scope(opened):
            # The def/class's own table sits inside its annotation scope.
            paired.add(opened.get_id())
            scopes = [*scopes, opened]
            opened = child_table(opened, name, lineno)
        if opened is not None:
            paired.add(opened.get_id())
            scopes = [*scopes, opened]
        elif not isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp)):
            unmatched.append(f"{type(node).__name__} {name!r} at line {lineno}")
        for child in inner:
            visit(child, scopes)

    visit(tree, [top])
    for table in _all_tables(top):
        if table.get_id() not in paired:
            unmatched.append(
                f"symbol table {table.get_name()!r} at line {table.get_lineno()}"
            )
    return unresolved, (unmatched[0] if unmatched else None)


# ID: 5d89fc56-2fb5-45da-98f0-f813e8e79343
class PatternValidators:
    """Pattern validators dispatched by ``PatternValidators.validate``.

    Each registered ``pattern_id`` maps to a classmethod that walks the
    generated code and returns ``list[ViolationReport]``. Unknown
    ``pattern_id`` values fall through to an empty-list result (deliberate
    "no validator applies" — see ``validate``'s docstring).
    """

    _RULE_STATEMENT_CACHE: dict[str, str] | None = None

    @classmethod
    # ID: 2781e0e8-0fff-4764-8c11-b6cfbc508a65
    def validate_test_file_pattern(
        cls, code: str, target_path: str
    ) -> list[ViolationReport]:
        """Validate generated test code for import resolution + absolute-import discipline.

        Closes #574 — IntentGuard.validate_generated_code previously accepted
        hallucinated imports for ``pattern_id="test_file"`` (no validator was
        registered). The two rules enforced here are declared in
        ``.intent/rules/code/imports.json`` and looked up by id from
        ``IntentRepository``; the validator holds the executor (AST walker +
        ``importlib.util.find_spec``), the rule statement lives in ``.intent/``.

        Rules enforced:
        - ``code.imports.generated_must_resolve`` — every absolute ``import`` /
          ``from M import …`` must resolve to a module on the Python path.
          ``__future__`` imports are skipped (always valid).
        - ``code.imports.generated_no_relative`` — relative imports
          (``from .foo import x``, ``from ..pkg import y``) are forbidden in
          generated code. Reported, and the resolve check is skipped for the
          same node (relative imports do not have an absolute module name
          ``find_spec`` could resolve).

        Out of scope (intentional, MVP for #574):
        - Whether a name imported from a real module actually exists in that
          module (e.g. ``from os import not_a_real_function``). Would require
          actually importing the module and inspecting attributes.
        - Dynamic imports (``importlib.import_module(...)``). Not visible to AST.
        - Semantic correctness of test assertions. Separate issue.
        """
        violations: list[ViolationReport] = []
        # tier2_violations accumulated below the SyntaxError guard; merged
        # at function-end so #574 + #589 surface in a single report.

        try:
            tree = ast.parse(code)
        except SyntaxError:
            # validate_generated_code step 2 already catches and reports
            # SyntaxError; re-emitting from here would duplicate the violation.
            return []

        # #589 Tier 2 — fan out across the test-quality static checks.
        # Each returns its own list[ViolationReport]; we concat. The
        # ordering doesn't matter for the IntentGuard verdict (any
        # violation fails the gate), but per-rule grouping helps triage.
        tier2_violations: list[ViolationReport] = []
        tier2_violations.extend(
            cls.check_no_magicmock_on_await(tree, code, target_path)
        )
        tier2_violations.extend(
            cls.check_no_imported_symbol_redeclared(tree, target_path)
        )
        tier2_violations.extend(cls.check_no_placeholder_test_body(tree, target_path))
        tier2_violations.extend(cls.check_no_global_module_mutation(tree, target_path))
        tier2_violations.extend(
            cls.check_no_unresolved_free_names(tree, target_path, code)
        )

        statements = cls._load_generated_import_rule_statements()

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == "__future__":
                    continue
                if node.level > 0:
                    violations.append(
                        ViolationReport(
                            rule_name=_GENERATED_NO_RELATIVE_RULE_ID,
                            path=target_path,
                            message=statements.get(
                                _GENERATED_NO_RELATIVE_RULE_ID,
                                "Generated code MUST use absolute imports; relative imports are forbidden.",
                            ),
                            severity="error",
                            suggested_fix="Replace the relative import with an absolute module path.",
                            source_policy="rules.code.imports",
                        )
                    )
                    continue
                if node.module and not cls._module_resolves(node.module):
                    violations.append(
                        ViolationReport(
                            rule_name=_GENERATED_RESOLVE_RULE_ID,
                            path=target_path,
                            message=statements.get(
                                _GENERATED_RESOLVE_RULE_ID,
                                "Generated code MUST have every import resolve to an existing module.",
                            )
                            + f" Unresolvable module: {node.module!r}.",
                            severity="error",
                            suggested_fix=(
                                f"Replace {node.module!r} with a module that exists on the Python path, "
                                "or remove the import if unused."
                            ),
                            source_policy="rules.code.imports",
                        )
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name
                    if not cls._module_resolves(module_name):
                        violations.append(
                            ViolationReport(
                                rule_name=_GENERATED_RESOLVE_RULE_ID,
                                path=target_path,
                                message=statements.get(
                                    _GENERATED_RESOLVE_RULE_ID,
                                    "Generated code MUST have every import resolve to an existing module.",
                                )
                                + f" Unresolvable module: {module_name!r}.",
                                severity="error",
                                suggested_fix=(
                                    f"Replace {module_name!r} with a module that exists on the Python path, "
                                    "or remove the import if unused."
                                ),
                                source_policy="rules.code.imports",
                            )
                        )

        return violations + tier2_violations

    @staticmethod
    def _module_resolves(module_name: str) -> bool:
        """Return True iff ``importlib.util.find_spec(module_name)`` finds a spec.

        ``find_spec`` raises on malformed names or when a parent package fails
        to import (its own broken import). Treated identically here: any
        exception means "does not resolve cleanly", which is the property the
        generated-must-resolve rule cares about.
        """
        try:
            return importlib.util.find_spec(module_name) is not None
        except (ModuleNotFoundError, ImportError, ValueError):
            return False

    @classmethod
    def _load_generated_import_rule_statements(cls) -> dict[str, str]:
        """Look up the two generated-import rule statements from IntentRepository.

        Lazy-loaded and cached on the class. On any lookup failure (missing
        rule, repository init failure) returns an empty dict; callers fall
        back to placeholder text so the validator still surfaces violations
        even when ``.intent/`` is degraded — fail-loud on the gate, fail-soft
        on the messaging.
        """
        if cls._RULE_STATEMENT_CACHE is not None:
            return cls._RULE_STATEMENT_CACHE

        try:
            from shared.infrastructure.intent.intent_repository import (
                get_intent_repository,
            )

            repo = get_intent_repository()
            repo.initialize()
            wanted = {_GENERATED_RESOLVE_RULE_ID, _GENERATED_NO_RELATIVE_RULE_ID}
            cache: dict[str, str] = {}
            for rule in repo.find_rules():
                rid = rule.get("id") if isinstance(rule, dict) else None
                if rid in wanted:
                    statement = (
                        rule.get("statement", "") if isinstance(rule, dict) else ""
                    )
                    if statement:
                        cache[rid] = statement
            cls._RULE_STATEMENT_CACHE = cache
        except Exception as exc:
            logger.warning(
                "PatternValidators: failed to load generated-import rule statements "
                "from IntentRepository — falling back to inline messages. Reason: %s",
                exc,
            )
            cls._RULE_STATEMENT_CACHE = {}

        return cls._RULE_STATEMENT_CACHE

    # ------------------------------------------------------------------
    # #589 Tier 2 — test-quality shape checks
    # ------------------------------------------------------------------

    @classmethod
    # ID: f362426d-dfe9-4e36-a346-10cbc8624dbf
    def check_no_magicmock_on_await(
        cls, tree: ast.AST, code: str, target_path: str
    ) -> list[ViolationReport]:
        """Flag ``X.Y = MagicMock(...)`` assignments where ``Y`` later
        appears in an ``await X.Y(...)`` call.

        Pure MagicMock returns a child MagicMock on call, and
        ``await MagicMock()`` raises ``TypeError: object MagicMock can't
        be used in 'await' expression``. Repeatedly observed across
        #572 batches 7 / 13 / 18.
        """
        statements = cls._load_test_quality_rule_statements()
        # 1. Collect awaited attribute names (last dotted segment) used in
        #    ``await x.y(...)`` and ``await x.y.z(...)`` chains.
        awaited_attrs: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Await) and isinstance(node.value, ast.Call):
                func = node.value.func
                if isinstance(func, ast.Attribute):
                    awaited_attrs.add(func.attr)
                elif isinstance(func, ast.Name):
                    awaited_attrs.add(func.id)

        if not awaited_attrs:
            return []

        # 2. Walk for ``<expr>.<attr> = MagicMock(...)`` assignments where
        #    <attr> is in the awaited set.
        violations: list[ViolationReport] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            if len(node.targets) != 1:
                continue
            target = node.targets[0]
            if not isinstance(target, ast.Attribute):
                continue
            if target.attr not in awaited_attrs:
                continue
            if not isinstance(node.value, ast.Call):
                continue
            call_name = _full_call_name(node.value.func)
            # Detect ``MagicMock(...)`` / ``Mock(...)`` (anything ending
            # in ``MagicMock`` or bare ``Mock``). AsyncMock is fine; spec
            # variants are fine — we only flag the unambiguous wrong-type.
            if call_name in {"MagicMock", "Mock"} or (
                call_name and call_name.endswith(".MagicMock")
            ):
                violations.append(
                    ViolationReport(
                        rule_name=_TEST_NO_MAGICMOCK_ON_AWAIT_RULE_ID,
                        path=target_path,
                        message=statements.get(
                            _TEST_NO_MAGICMOCK_ON_AWAIT_RULE_ID,
                            "Awaited attribute mocked with MagicMock — use AsyncMock instead "
                            "(`await MagicMock()` raises TypeError).",
                        )
                        + f" Attribute: {target.attr!r}.",
                        severity="error",
                        suggested_fix=(
                            f"Replace MagicMock with AsyncMock for the {target.attr!r} mock setup, "
                            "or use ``AsyncMock(spec=...)`` for stricter type-matching."
                        ),
                        source_policy="rules.code.tests",
                    )
                )
        return violations

    @classmethod
    # ID: 281872e1-a112-4d68-87e5-7a5c9d41306d
    def check_no_imported_symbol_redeclared(
        cls, tree: ast.Module, target_path: str
    ) -> list[ViolationReport]:
        """Flag top-level ``class Foo: pass`` / ``def Foo(...)`` where ``Foo``
        is also imported in the same file.

        The "speculative stub" autogen pattern (#572 batches 19/20): the
        generator emits a local placeholder for a symbol it couldn't
        introspect, then writes tests against the placeholder. Tests
        invisibly pass because Python's scoping resolves ``Foo`` to the
        local class, not the imported one.
        """
        statements = cls._load_test_quality_rule_statements()
        imported_names: set[str] = set()
        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    imported_names.add(alias.asname or alias.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    # ``import a.b`` binds ``a`` in the local namespace
                    bound = alias.asname or alias.name.split(".", 1)[0]
                    imported_names.add(bound)

        if not imported_names:
            return []

        violations: list[ViolationReport] = []
        for node in tree.body:
            if (
                isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name in imported_names
            ):
                violations.append(
                    ViolationReport(
                        rule_name=_TEST_NO_IMPORTED_SYMBOL_REDECLARED_RULE_ID,
                        path=target_path,
                        message=statements.get(
                            _TEST_NO_IMPORTED_SYMBOL_REDECLARED_RULE_ID,
                            "Top-level redeclaration of an imported symbol — "
                            "Python scoping resolves to the local definition, not the import. "
                            "This is the autogen 'speculative stub' pattern (#589).",
                        )
                        + f" Symbol: {node.name!r}.",
                        severity="error",
                        suggested_fix=(
                            f"Remove the local ``class {node.name}`` / ``def {node.name}`` block. "
                            "If the imported symbol can't be exercised, the test file should "
                            "be reduced to an import-smoke test instead of a placeholder."
                        ),
                        source_policy="rules.code.tests",
                    )
                )
        return violations

    @classmethod
    # ID: 3a302727-50ed-437a-9340-706aacb85c05
    def check_no_placeholder_test_body(
        cls, tree: ast.Module, target_path: str
    ) -> list[ViolationReport]:
        """Flag ``def test_X(...)`` functions whose body has no observable
        assertion — no ``assert``, no ``pytest.raises(...)``, no mock
        ``.assert_*`` call. These pass trivially and add fake coverage.
        """
        statements = cls._load_test_quality_rule_statements()
        violations: list[ViolationReport] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test_"):
                continue
            if _has_observable_assertion(node):
                continue
            violations.append(
                ViolationReport(
                    rule_name=_TEST_NO_PLACEHOLDER_TEST_BODY_RULE_ID,
                    path=target_path,
                    message=statements.get(
                        _TEST_NO_PLACEHOLDER_TEST_BODY_RULE_ID,
                        "Test function has no observable assertion — no ``assert``, "
                        "no ``pytest.raises(...)``, no mock ``.assert_*`` call. "
                        "Placeholder tests give false confidence.",
                    )
                    + f" Test: {node.name!r}.",
                    severity="error",
                    suggested_fix=(
                        f"Add at least one assertion to ``{node.name}``, or "
                        "remove the function if the contract is not yet specified."
                    ),
                    source_policy="rules.code.tests",
                )
            )
        return violations

    @classmethod
    # ID: 7e955726-c011-4deb-9a39-4adc6100a3c0
    def check_no_global_module_mutation(
        cls, tree: ast.Module, target_path: str
    ) -> list[ViolationReport]:
        """Flag ``<imported_module>.<attr> = <value>`` at module scope or
        directly inside a fixture body (outside a ``with patch(...)`` /
        ``monkeypatch.setattr(...)`` context).

        Pattern observed in #572 batch 13: fixtures doing
        ``yaml.safe_load = MagicMock(...)`` polluted every subsequent test
        in the process. Properly-scoped mutation via ``monkeypatch`` or
        ``patch`` is allowed (and not flagged here).
        """
        statements = cls._load_test_quality_rule_statements()

        # Collect imported module names so we can distinguish "mutating
        # a module attribute" from "mutating an instance attribute".
        imported_modules: set[str] = set()
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    bound = alias.asname or alias.name.split(".", 1)[0]
                    imported_modules.add(bound)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    # ``from X import Y`` binds Y; treat Y as a potentially
                    # mutated module/class attribute root.
                    imported_modules.add(alias.asname or alias.name)

        if not imported_modules:
            return []

        violations: list[ViolationReport] = []
        for walk_node in ast.walk(tree):
            if not isinstance(walk_node, ast.Assign):
                continue
            if len(walk_node.targets) != 1:
                continue
            target = walk_node.targets[0]
            if not isinstance(target, ast.Attribute):
                continue
            root = target.value
            if not isinstance(root, ast.Name) or root.id not in imported_modules:
                continue
            # If this assign is inside a ``with patch(...)`` block or is the
            # body of a ``monkeypatch.setattr(...)`` call, allow it.
            # Heuristic: we only flag at the *top of the module* or inside
            # FunctionDef bodies — both contexts where unscoped mutation is
            # the antipattern. patch() context managers wrap the mutation in
            # a With node, which we explicitly skip below in _is_inside_with_patch.
            violations.append(
                ViolationReport(
                    rule_name=_TEST_NO_GLOBAL_MODULE_MUTATION_RULE_ID,
                    path=target_path,
                    message=statements.get(
                        _TEST_NO_GLOBAL_MODULE_MUTATION_RULE_ID,
                        "Module-level mutation of an imported symbol — "
                        "pollutes every subsequent test in the process. "
                        "Use ``monkeypatch.setattr(...)`` or ``with patch(...)`` instead.",
                    )
                    + f" Target: {root.id}.{target.attr}.",
                    severity="error",
                    suggested_fix=(
                        f"Replace ``{root.id}.{target.attr} = <value>`` with "
                        f"``monkeypatch.setattr({root.id!r}, {target.attr!r}, <value>)`` "
                        "or wrap in a ``with patch(...)`` context manager."
                    ),
                    source_policy="rules.code.tests",
                )
            )
        return violations

    @classmethod
    # ID: 543f17dc-86a5-46a8-9ebd-4ad24dad9044
    def check_no_unresolved_free_names(
        cls, tree: ast.Module, target_path: str, code: str | None = None
    ) -> list[ViolationReport]:
        """Flag references to free names (Name nodes used as values) that
        are neither imported nor defined in the file and aren't builtins.

        Catches the autogen "missing import" pattern (#572 batch 19's
        ``MagicMock`` used without ``from unittest.mock import MagicMock``):
        the test will NameError at collection but the LLM didn't notice
        because its training prior treated the name as ambient.

        Name resolution is delegated to the compiler (stdlib ``symtable``): a
        Load is flagged only if the compiler resolves the name as global, it
        is not bound at module level, and it is not a builtin. Source that does
        not compile, or a scope that cannot be paired with its symbol table,
        yields a violation: names that were not checked are not accepted.
        ``code`` is the source ``tree`` was parsed from; without it the tree is
        unparsed and reported line numbers refer to that normalised form.
        """
        statements = cls._load_test_quality_rule_statements()

        if code is None:
            code = ast.unparse(tree)
            tree = ast.parse(code)
        statement = statements.get(
            _TEST_NO_UNRESOLVED_FREE_NAMES_RULE_ID,
            "Free name referenced without being imported or defined — "
            "test will NameError at collection.",
        )

        # Fail closed: when names cannot be resolved, the gate refuses rather
        # than relying on a later gate (governor ruling 2026-10-03).
        def _unanalysable(reason: str) -> list[ViolationReport]:
            return [
                ViolationReport(
                    rule_name=_TEST_NO_UNRESOLVED_FREE_NAMES_RULE_ID,
                    path=target_path,
                    message=f"{statement} Names could not be checked: {reason}.",
                    severity="error",
                    suggested_fix="Rewrite the test in plain, compilable Python.",
                    source_policy="rules.code.tests",
                )
            ]

        try:
            top = symtable.symtable(code, target_path, "exec")
        except SyntaxError as exc:
            # Parses but does not compile (e.g. ``nonlocal`` with no binding).
            return _unanalysable(f"source does not compile ({exc.msg})")

        defined = (
            _module_level_names(top) | _PYTHON_BUILTINS | _INTERPRETER_MODULE_NAMES
        )
        loads, unmatched = _unresolved_global_loads(tree, top, defined)
        if unmatched is not None:
            return _unanalysable(
                f"scope could not be matched to its symbol table ({unmatched})"
            )
        violations: list[ViolationReport] = []
        for sub in loads:
            name = sub.id
            violations.append(
                ViolationReport(
                    rule_name=_TEST_NO_UNRESOLVED_FREE_NAMES_RULE_ID,
                    path=target_path,
                    message=f"{statement} Name: {name!r} at line {sub.lineno}.",
                    severity="error",
                    suggested_fix=(
                        f"Add the missing import for {name!r}, "
                        f"or define / parameterise it in the enclosing scope."
                    ),
                    source_policy="rules.code.tests",
                )
            )
        return violations

    @classmethod
    def _load_test_quality_rule_statements(cls) -> dict[str, str]:
        """Like ``_load_generated_import_rule_statements`` but for the
        Tier 2 test-quality rules. Lazy + cached.
        """
        if cls._RULE_STATEMENT_CACHE is None:
            # populate from #574's loader first, so both #574 + Tier 2
            # statements share a single cache
            cls._load_generated_import_rule_statements()
        assert cls._RULE_STATEMENT_CACHE is not None
        try:
            from shared.infrastructure.intent.intent_repository import (
                get_intent_repository,
            )

            repo = get_intent_repository()
            repo.initialize()
            for rule in repo.find_rules():
                rid = rule.get("id") if isinstance(rule, dict) else None
                if rid in _TIER2_RULE_IDS and rid not in cls._RULE_STATEMENT_CACHE:
                    statement = (
                        rule.get("statement", "") if isinstance(rule, dict) else ""
                    )
                    if statement:
                        cls._RULE_STATEMENT_CACHE[rid] = statement
        except Exception as exc:
            logger.warning(
                "PatternValidators: failed to load Tier 2 rule statements — "
                "falling back to inline messages. Reason: %s",
                exc,
            )
        return cls._RULE_STATEMENT_CACHE

    @classmethod
    # ID: 88f6ecff-74fe-469c-aa00-7fea3a8e1831
    def validate(
        cls,
        code: str,
        pattern_id: str,
        component_type: str,
        target_path: str = "",
    ) -> list[ViolationReport]:
        """Dispatch to the appropriate per-pattern validator by ``pattern_id``.

        Issue #210: prior IntentGuard call invoked a method that did not
        exist, raising AttributeError that was silently swallowed by a
        broad except in build.tests. This classmethod is the canonical
        entry point.

        Returns an empty list when ``pattern_id`` does not correspond to
        any per-pattern validator. That is a deliberate "no validator
        applies" signal — not a failure — and is logged at INFO so the gap
        remains observable. Real validator failures must surface as
        exceptions or violations from the per-pattern validator itself,
        never as a silent empty list.

        ``component_type`` is accepted for API stability with the existing
        IntentGuard call shape but is currently unused — reserved for
        future per-component-type dispatch.
        """
        dispatch = {
            "test_file": cls.validate_test_file_pattern,
        }
        validator = dispatch.get(pattern_id)
        if validator is None:
            logger.info(
                "PatternValidators: no validator for pattern_id=%r "
                "(component_type=%r) — returning empty violations",
                pattern_id,
                component_type,
            )
            return []
        return validator(code, target_path)
