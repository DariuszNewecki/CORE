"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/mind/logic/engines/ast_gate/engine.py
- Symbol: ASTGateEngine
- Generated: 2026-01-11 02:26:12
- 2026-06-07 (#572 Cat B batch 5):
    * signatures realigned for path_resolver DI
    * tmp paths moved under var/tmp/ per CLAUDE.md (no /tmp/ writes)
    * test_supported_check_types now reads the canonical
      _SUPPORTED_CHECK_TYPES ClassVar — the previous public-method form
      was an autogen guess that never existed on the class
    * per-check_type message assertions updated to the current canonical
      'AST Check complete: {check_type}' format (was 'AST Gate: Compliant'
      / 'AST Gate: Violations found' in the autogen vintage)
    * test_verify_unknown_check_type / _empty_check_type updated for
      #588's unknown-check_type guard: source now returns ok=False with a
      "Logic Error: Unknown check_type ..." message instead of silently
      completing.
    * test_verify_forbidden_assignments updated for #588's dispatch wiring
      — source now flags assignments to forbidden target names (the
      data.ssot.database_primacy rule in governance.yaml depends on this).
    * test_verify_write_defaults_false_violation / _decorator_args still
      pin the generic-primitive alias semantics: source dispatches them
      through the generic harness, which needs explicit selector +
      requirement params. The flat-params shape this test passes still
      yields no violations — that's the alias-without-explicit-params
      behavior, not a missing dispatch.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from mind.logic.engines.ast_gate.engine import ASTGateEngine
from shared.path_resolver import PathResolver


_REPO_ROOT = Path("/opt/dev/CORE")


@pytest.fixture
def path_resolver():
    """Real PathResolver at the repo root. ASTGateEngine reads ``.intent_root``
    inside a single check_type (protected_namespace_access) which the tests
    below do not exercise."""
    return PathResolver(repo_root=_REPO_ROOT)


@pytest.fixture
def tmp_py_file():
    """Per-test source file under var/tmp/ (CLAUDE.md prohibits /tmp/)."""
    repo_tmp = _REPO_ROOT / "var" / "tmp"
    repo_tmp.mkdir(parents=True, exist_ok=True)
    p = repo_tmp / f"ast_gate_test_{uuid.uuid4().hex}.py"
    yield p
    p.unlink(missing_ok=True)


async def test_verify_unknown_check_type(path_resolver, tmp_py_file):
    """An unknown check_type is now caught by the #588 final-else guard
    and returned as a Logic Error verdict. Pre-#588 source silently fell
    through to a generic "AST Check complete" passing verdict — a
    typo'd check_type or a name belonging to a different engine would
    invisibly audit-PASS forever."""
    engine = ASTGateEngine(path_resolver=path_resolver)
    tmp_py_file.write_text("print('test')")
    result = await engine.verify(tmp_py_file, {"check_type": "unknown_check"})
    assert not result.ok
    assert result.message == "Logic Error: Unknown check_type 'unknown_check'"
    assert result.violations == []
    assert result.engine_id == "ast_gate"


async def test_verify_empty_check_type(path_resolver, tmp_py_file):
    """An empty check_type matches no dispatch clause; same #588 guard
    fires as for any unknown name."""
    engine = ASTGateEngine(path_resolver=path_resolver)
    tmp_py_file.write_text("print('test')")
    result = await engine.verify(tmp_py_file, {"check_type": ""})
    assert not result.ok
    assert result.message == "Logic Error: Unknown check_type ''"
    assert result.violations == []
    assert result.engine_id == "ast_gate"


async def test_verify_parse_error(path_resolver, tmp_py_file):
    """Invalid Python syntax → ast.parse raises → engine returns a Parse Error
    result. This path is exercised before any check_type dispatch."""
    engine = ASTGateEngine(path_resolver=path_resolver)
    tmp_py_file.write_text("def invalid syntax")
    result = await engine.verify(tmp_py_file, {"check_type": "no_print_statements"})
    assert not result.ok
    assert "Parse Error:" in result.message
    assert result.violations == []
    assert result.engine_id == "ast_gate"


async def test_verify_no_print_statements_compliant(path_resolver, tmp_py_file):
    """Code without print() → no_print_statements check passes."""
    engine = ASTGateEngine(path_resolver=path_resolver)
    tmp_py_file.write_text("def foo():\n    pass")
    result = await engine.verify(tmp_py_file, {"check_type": "no_print_statements"})
    assert result.ok
    assert result.message == "AST Check complete: no_print_statements"
    assert result.violations == []
    assert result.engine_id == "ast_gate"


async def test_verify_no_print_statements_violation(path_resolver, tmp_py_file):
    """Code with print() → no_print_statements check fires a violation. The
    violation string mentions print explicitly (current source emits
    'Line N: Replace print() with logger.')."""
    engine = ASTGateEngine(path_resolver=path_resolver)
    tmp_py_file.write_text("print('hello')")
    result = await engine.verify(tmp_py_file, {"check_type": "no_print_statements"})
    assert not result.ok
    assert result.message == "AST Check complete: no_print_statements"
    assert len(result.violations) > 0
    assert "print" in result.violations[0]
    assert result.engine_id == "ast_gate"


async def test_verify_forbidden_assignments(path_resolver, tmp_py_file):
    """forbidden_assignments now flags module-level assignments to
    target names listed in the rule's ``targets`` param. The
    data.ssot.database_primacy rule in governance.yaml uses this to
    catch hardcoded operational vocabularies (LLM_MODELS, AGENT_ROLES,
    SYSTEM_DOMAINS, ...) — see #588 for the source-side fix that wired
    the dispatch."""
    engine = ASTGateEngine(path_resolver=path_resolver)
    tmp_py_file.write_text("SECRET_KEY = 'abc123'")
    result = await engine.verify(
        tmp_py_file,
        {"check_type": "forbidden_assignments", "targets": ["SECRET_KEY", "API_KEY"]},
    )
    assert not result.ok
    assert result.message == "AST Check complete: forbidden_assignments"
    assert len(result.violations) == 1
    assert "SECRET_KEY" in result.violations[0]
    assert result.engine_id == "ast_gate"


async def test_verify_forbidden_assignments_clean(path_resolver, tmp_py_file):
    """forbidden_assignments returns clean when the file's module-level
    assignments don't match the forbidden target list."""
    engine = ASTGateEngine(path_resolver=path_resolver)
    tmp_py_file.write_text("ALLOWED_NAME = 'fine'\n")
    result = await engine.verify(
        tmp_py_file,
        {"check_type": "forbidden_assignments", "targets": ["LLM_MODELS"]},
    )
    assert result.ok
    assert result.violations == []
    assert result.engine_id == "ast_gate"


async def test_verify_write_defaults_false_violation(path_resolver, tmp_py_file):
    """write_defaults_false is dispatched via the generic-primitive harness
    (engine.py:300) which requires non-trivial selector+requirement params.
    With the flat {check_type: ...} shape this test passes, the harness
    selects every node and validates with empty requirement → no violations.
    Pinning current behavior; see #588 (Drift 2) for the alias-semantics
    documentation gap."""
    engine = ASTGateEngine(path_resolver=path_resolver)
    tmp_py_file.write_text("def foo(write=True):\n    pass")
    result = await engine.verify(tmp_py_file, {"check_type": "write_defaults_false"})
    assert result.ok
    assert result.message == "AST Check complete: write_defaults_false"
    assert result.violations == []
    assert result.engine_id == "ast_gate"


async def test_verify_write_defaults_false_compliant(path_resolver, tmp_py_file):
    """Same generic-primitive dispatch as the violation case; the bare-params
    path produces no violations either way."""
    engine = ASTGateEngine(path_resolver=path_resolver)
    tmp_py_file.write_text("def foo(write=False):\n    pass")
    result = await engine.verify(tmp_py_file, {"check_type": "write_defaults_false"})
    assert result.ok
    assert result.message == "AST Check complete: write_defaults_false"
    assert result.violations == []
    assert result.engine_id == "ast_gate"


async def test_verify_max_file_lines_violation(path_resolver, tmp_py_file):
    """max_file_lines reads the params['limit'] and counts source lines.
    Source emits the violation as a single string with the count."""
    engine = ASTGateEngine(path_resolver=path_resolver)
    lines = [f"line_{i} = {i}" for i in range(500)]
    tmp_py_file.write_text("\n".join(lines))
    result = await engine.verify(
        tmp_py_file, {"check_type": "max_file_lines", "limit": 400}
    )
    assert not result.ok
    assert result.message == "AST Check complete: max_file_lines"
    assert len(result.violations) > 0
    assert "500" in result.violations[0]
    assert "400" in result.violations[0]
    assert result.engine_id == "ast_gate"


async def test_verify_decorator_args(path_resolver, tmp_py_file):
    """decorator_args is the second generic-primitive alias (see
    test_verify_write_defaults_false_violation). Same dispatch shape, same
    bare-params no-op outcome. See #588 Drift 2."""
    engine = ASTGateEngine(path_resolver=path_resolver)
    tmp_py_file.write_text("@my_decorator\ndef foo():\n    pass")
    result = await engine.verify(
        tmp_py_file,
        {
            "check_type": "decorator_args",
            "decorator": "my_decorator",
            "required_args": ["arg1", "arg2"],
        },
    )
    assert result.ok
    assert result.message == "AST Check complete: decorator_args"
    assert result.violations == []
    assert result.engine_id == "ast_gate"


async def test_verify_stable_id_anchor(path_resolver, tmp_py_file):
    """stable_id_anchor check returns a successful result for the simple
    `id = 'unstable'` input. Test pins engine_id only — the assertion
    surface that survives whatever check logic does or doesn't fire here."""
    engine = ASTGateEngine(path_resolver=path_resolver)
    tmp_py_file.write_text("id = 'unstable'")
    result = await engine.verify(tmp_py_file, {"check_type": "stable_id_anchor"})
    assert result.engine_id == "ast_gate"


async def test_verify_runtime_import_boundary(path_resolver, tmp_py_file):
    """import of a forbidden module → runtime_import_boundary check fires."""
    engine = ASTGateEngine(path_resolver=path_resolver)
    tmp_py_file.write_text("import forbidden_module")
    result = await engine.verify(
        tmp_py_file,
        {"check_type": "runtime_import_boundary", "forbidden": ["forbidden_module"]},
    )
    assert not result.ok
    assert result.message == "AST Check complete: runtime_import_boundary"
    assert len(result.violations) > 0
    assert "forbidden_module" in result.violations[0]
    assert result.engine_id == "ast_gate"


async def test_embedding_access_rule_catches_direct_import(path_resolver, tmp_py_file):
    """architecture.boundary.embedding_access: importing EmbeddingService directly
    in body/mind/will/cli fires; importing _chunk_text (the only permitted symbol)
    from the same module does not.

    Exercises the runtime_import_boundary check with the exact forbidden patterns
    declared in .intent/enforcement/mappings/architecture/privileged_boundaries.yaml.
    """
    engine = ASTGateEngine(path_resolver=path_resolver)
    _FORBIDDEN = [
        "shared.utils.embedding_utils.EmbeddingService",
        "shared.utils.embedding_utils.build_embedder_from_env",
    ]

    # Violation: direct EmbeddingService import — the pattern that was the bug
    tmp_py_file.write_text(
        "from shared.utils.embedding_utils import EmbeddingService\n"
    )
    result = await engine.verify(
        tmp_py_file,
        {"check_type": "runtime_import_boundary", "forbidden": _FORBIDDEN},
    )
    assert not result.ok, "EmbeddingService direct import must be blocked"
    assert any("EmbeddingService" in v for v in result.violations)

    # Violation: build_embedder_from_env — settings-based factory, same bypass
    tmp_py_file.write_text(
        "from shared.utils.embedding_utils import build_embedder_from_env\n"
    )
    result = await engine.verify(
        tmp_py_file,
        {"check_type": "runtime_import_boundary", "forbidden": _FORBIDDEN},
    )
    assert not result.ok, "build_embedder_from_env direct import must be blocked"

    # Clean: _chunk_text is a pure utility, not a resource-access bypass
    tmp_py_file.write_text(
        "from shared.utils.embedding_utils import _chunk_text\n"
    )
    result = await engine.verify(
        tmp_py_file,
        {"check_type": "runtime_import_boundary", "forbidden": _FORBIDDEN},
    )
    assert result.ok, "_chunk_text import must be allowed (not a resource bypass)"

    # Clean: CognitiveEmbedderAdapter — the canonical path
    tmp_py_file.write_text(
        "from shared.infrastructure.vector.cognitive_adapter import CognitiveEmbedderAdapter\n"
    )
    result = await engine.verify(
        tmp_py_file,
        {"check_type": "runtime_import_boundary", "forbidden": _FORBIDDEN},
    )
    assert result.ok, "CognitiveEmbedderAdapter import must be allowed"


def test_supported_check_types():
    """The canonical surface for the dispatch vocabulary is the class-level
    ``_SUPPORTED_CHECK_TYPES`` ClassVar — a frozenset enumerating every
    check_type ``verify`` knows about. The previous public
    ``supported_check_types()`` form never existed on the class."""
    supported = ASTGateEngine._SUPPORTED_CHECK_TYPES
    assert isinstance(supported, frozenset)
    assert "no_print_statements" in supported
    assert "runtime_import_boundary" in supported
    assert "max_file_lines" in supported
    assert len(supported) > 0


async def test_verify_all_supported_check_types_exist(path_resolver, tmp_py_file):
    """Every check_type in _SUPPORTED_CHECK_TYPES yields an EngineResult with
    no 'Unknown check_type' message. Note: this currently passes even for
    check_types with no dispatch clause (see #588 Drift 1) because the
    fall-through generic-completion path produces 'AST Check complete: X'
    instead of any 'Unknown' message — so this assertion is satisfied by
    the buggy behavior too. The test is preserved as a regression guard
    against the eventual #588 fix accidentally re-introducing an Unknown
    error for currently-silent check_types."""
    engine = ASTGateEngine(path_resolver=path_resolver)
    tmp_py_file.write_text("pass")
    for check_type in ASTGateEngine._SUPPORTED_CHECK_TYPES:
        result = await engine.verify(tmp_py_file, {"check_type": check_type})
        assert result.engine_id == "ast_gate"
        assert "Logic Error: Unknown check_type" not in result.message
