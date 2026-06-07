# src/will/test_generation/introspection_facts.py

"""
Live source-contract introspection for test-gen prompts (#589).

Purpose:
- Produce a structured "ground truth" view of the target symbol that the
  LLM cannot hallucinate around: live signature, public/private attribute
  surface (for classes), awaited call sites grepped from the symbol's
  source body, decorator list, async-ness.

Why this exists:
- Across #572's 20-batch drain we observed ~60% of autogen test failures
  trace back to the generator imagining an API the source never had:
  attributes that never existed, constructors that gained DI args, mocks
  pointed at the wrong call site. The single biggest leverage point is
  to refuse to let the LLM hallucinate by giving it the live source
  contract in-context. See memory ``feedback_autogen_introspect_before_assert``
  for the longer reasoning; this module is its load-bearing dependency.

Failure mode:
- Any introspection step can fail (target not importable from the
  derived module path, target not a class/function, dynamic attrs only
  visible at instance time, etc.). The helper degrades gracefully: it
  returns the same dict shape with an ``introspection_error`` key set,
  the prompt-side will then skip the GROUND TRUTH section instead of
  blocking the test-gen entirely. Fail-soft on this surface; fail-loud
  on the actual code-write gate (see PatternValidators / #574).
"""

from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path
from typing import Any

from mind.logic.engines.ast_gate.base import ASTHelpers
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 6c7d8e9f-1a2b-3c4d-5e6f-7a8b9c0d1e2f
def build_introspection_facts(
    file_path: str,
    symbol_name: str,
    symbol_code: str,
) -> dict[str, Any]:
    """Build a ground-truth fact dict for ``symbol_name`` in ``file_path``.

    The dict has a stable shape regardless of success/failure — callers
    can switch on ``introspection_error is None`` to decide whether to
    emit ground-truth-derived hard constraints.

    Args:
        file_path: Repository-relative file path (e.g. ``"src/body/services/foo.py"``
            or ``"body/services/foo.py"``). The leading ``src/`` is stripped.
        symbol_name: The name of the class or function to introspect.
        symbol_code: The source text of the symbol's definition (used for
            AST-level facts like decorator list and awaited call sites that
            don't require a live import).

    Returns:
        A dict with these keys:
        - ``import_path``: ``"body.services.foo"`` (the live-import path)
        - ``signature``: ``"(self, repo_root: Path) -> None"`` or ``"()"``
        - ``kind``: ``"class"`` | ``"function"`` | ``"async_function"`` | ``"unknown"``
        - ``is_async``: bool
        - ``public_attrs``: list of public names from ``dir(cls)`` (class only)
        - ``private_attrs``: list of private (``_``-prefixed) names (class only)
        - ``awaited_call_sites``: list of dotted names appearing under
          ``ast.Await`` in the symbol body (e.g. ``["self._qdrant.search"]``)
        - ``decorators``: list of decorator source strings (e.g. ``["@atomic_action(...)"]``)
        - ``has_governance_decorator``: bool — True if any decorator on the
          target is ``@atomic_action`` or a similar governance-routed wrapper
          (tests for such targets MUST call ``.__wrapped__`` or go via
          ``ActionExecutor.execute``).
        - ``introspection_error``: None on success; a short reason string
          when the live import or signature extraction failed.
    """
    facts: dict[str, Any] = {
        "import_path": _file_path_to_import_path(file_path),
        "signature": "",
        "kind": "unknown",
        "is_async": False,
        "public_attrs": [],
        "private_attrs": [],
        "awaited_call_sites": [],
        "decorators": [],
        "has_governance_decorator": False,
        "introspection_error": None,
    }

    # AST-derived facts come from symbol_code and don't need a live import.
    # Do them first so partial facts survive an import failure.
    try:
        facts["decorators"] = _extract_target_decorators(symbol_code, symbol_name)
        facts["has_governance_decorator"] = _has_governance_decorator(
            facts["decorators"]
        )
        facts["awaited_call_sites"] = _extract_awaited_call_sites(
            symbol_code, symbol_name
        )
    except Exception as exc:
        logger.debug(
            "introspection_facts: AST-side extraction failed for %s: %s",
            symbol_name,
            exc,
        )

    # Live-import facts: signature, public/private attribute surface.
    try:
        target = _import_target(facts["import_path"], symbol_name)
    except Exception as exc:
        facts["introspection_error"] = (
            f"could not import {symbol_name} from {facts['import_path']}: {exc}"
        )
        return facts

    if inspect.isclass(target):
        facts["kind"] = "class"
        try:
            facts["signature"] = str(inspect.signature(target.__init__))
        except (TypeError, ValueError) as exc:
            facts["signature"] = "(self, ...)  # signature unavailable: " + str(exc)
        all_names = sorted(dir(target))
        facts["public_attrs"] = [n for n in all_names if not n.startswith("_")]
        facts["private_attrs"] = [
            n for n in all_names if n.startswith("_") and not n.startswith("__")
        ]
    elif inspect.iscoroutinefunction(target):
        facts["kind"] = "async_function"
        facts["is_async"] = True
        try:
            facts["signature"] = str(inspect.signature(target))
        except (TypeError, ValueError) as exc:
            facts["signature"] = "(...)  # signature unavailable: " + str(exc)
    elif inspect.isfunction(target) or inspect.isbuiltin(target):
        facts["kind"] = "function"
        try:
            facts["signature"] = str(inspect.signature(target))
        except (TypeError, ValueError) as exc:
            facts["signature"] = "(...)  # signature unavailable: " + str(exc)
    else:
        # Module-level constant, dataclass instance, etc. — out of scope for
        # test-gen but we don't error out.
        facts["kind"] = type(target).__name__

    return facts


# ID: 7d8e9f0a-1b2c-3d4e-5f6a-7b8c9d0e1f2a
def _file_path_to_import_path(file_path: str) -> str:
    """Convert a repo-relative .py path into a dotted import path.

    ``src/body/services/foo.py`` -> ``"body.services.foo"``
    ``body/services/foo.py``     -> ``"body.services.foo"``
    Trailing ``__init__.py`` collapses to the package name.
    """
    rel = Path(file_path)
    if rel.parts and rel.parts[0] == "src":
        rel = Path(*rel.parts[1:])
    rel = rel.with_suffix("")
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


# ID: 8e9f0a1b-2c3d-4e5f-6a7b-8c9d0e1f2a3b
def _import_target(import_path: str, symbol_name: str) -> Any:
    """Import ``import_path`` and resolve ``symbol_name`` off the module.

    Re-raised exceptions bubble up to the caller's ``introspection_error``
    handling. ``getattr`` raising AttributeError is the canonical "symbol
    not defined in module" signal.
    """
    if not import_path:
        raise ValueError("empty import_path")
    module = importlib.import_module(import_path)
    return getattr(module, symbol_name)


# ID: 9f0a1b2c-3d4e-5f6a-7b8c-9d0e1f2a3b4c
def _extract_awaited_call_sites(symbol_code: str, symbol_name: str) -> list[str]:
    """Walk the symbol's body for ``await x.y(...)`` patterns and return
    the dotted-name list of awaited call sites.

    The point is to give the LLM a concrete list of "these are the methods
    your test's mocks must match" — e.g. ``["self._qdrant.search",
    "self._audit_prompt_model.invoke"]``. Past autogen vintage mocked
    plausible-but-wrong call sites (``client.make_request`` when source
    uses ``_prompt_model.invoke``); naming the actual sites in the prompt
    closes that shape.
    """
    try:
        tree = ast.parse(symbol_code)
    except SyntaxError:
        return []

    target_node = _find_target_node(tree, symbol_name)
    if target_node is None:
        # symbol_code might be just the symbol body (no enclosing def);
        # fall back to walking the whole tree
        target_node = tree

    sites: list[str] = []
    for node in ast.walk(target_node):
        if isinstance(node, ast.Await) and isinstance(node.value, ast.Call):
            full = ASTHelpers.full_attr_name(node.value.func)
            if full and full not in sites:
                sites.append(full)
    return sites


# ID: 0a1b2c3d-4e5f-6a7b-8c9d-0e1f2a3b4c5d
def _extract_target_decorators(symbol_code: str, symbol_name: str) -> list[str]:
    """Return the source form of each decorator on the target.

    For ``@atomic_action(action_id="foo", impact=...)``, returns the full
    ``"atomic_action(action_id='foo', impact=...)"`` text — preserves the
    governance-decorator detection downstream.
    """
    try:
        tree = ast.parse(symbol_code)
    except SyntaxError:
        return []
    target_node = _find_target_node(tree, symbol_name)
    if target_node is None or not hasattr(target_node, "decorator_list"):
        return []
    out: list[str] = []
    for dec in target_node.decorator_list:
        try:
            out.append(ast.unparse(dec))
        except Exception:
            # ast.unparse failed on a weird decorator shape — skip it.
            continue
    return out


# ID: 1b2c3d4e-5f6a-7b8c-9d0e-1f2a3b4c5d6e
def _find_target_node(
    tree: ast.AST, symbol_name: str
) -> ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | None:
    """Locate the FunctionDef/AsyncFunctionDef/ClassDef for ``symbol_name``."""
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and node.name == symbol_name
        ):
            return node
    return None


# ID: 2c3d4e5f-6a7b-8c9d-0e1f-2a3b4c5d6e7f
def _has_governance_decorator(decorators: list[str]) -> bool:
    """True if any decorator on the target is a governance wrapper.

    Tests for such targets MUST call ``target.__wrapped__(...)`` or route
    through ``ActionExecutor.execute(...)`` — direct calls raise
    ``GovernanceBypassError`` (see #572 batch 15 evidence). The names
    listed here are the wrappers known to gate direct calls.
    """
    GOVERNANCE_DECORATOR_PREFIXES = ("atomic_action", "core_command")
    for dec in decorators:
        for prefix in GOVERNANCE_DECORATOR_PREFIXES:
            if dec.startswith(prefix):
                return True
    return False
