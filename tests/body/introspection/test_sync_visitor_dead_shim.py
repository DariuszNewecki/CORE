# tests/body/introspection/test_sync_visitor_dead_shim.py

"""
ADR-151 fixture matrix — marker attribution in the sync visitor (D1/D5).

Recreates the measured shapes from the ADR's verification note:
  - four POSITIVE fixtures (the #804 shapes): module-shim attribution,
    deprecated-alias method, `.. deprecated::` directive, DeprecationWarning
  - two PROPERTY must-not-fire (D1 exclusion: attribute reads ≠ call edges)
  - dispatch must-not-fire (D2 grace: Typer command)
  - prose must-not-fire (the legacy scanner's own module — mentions legacy,
    does not self-declare)
Plus the engine's deprecation-scoped state propagation pin.
"""

from __future__ import annotations

import ast
import inspect

from body.introspection.sync.visitor import SymbolVisitor


def _states(source: str) -> dict[str, str]:
    tree = ast.parse(source)
    v = SymbolVisitor("src/pkg/mod.py")
    v.visit(tree)
    return {s["qualname"]: s["state"] for s in v.symbols}


# ---------------------------------------------------------------------------
# Positive fixtures — the four #804 shapes
# ---------------------------------------------------------------------------


def test_module_shim_docstring_deprecates_all_public_symbols():
    """embedding_provider shape: module self-declaration attributes to symbols."""
    src = '''
"""Compatibility shim for legacy imports.

This module exists only to prevent import breakage while migrating."""

class EmbeddingService:
    """Legacy-compatible wrapper around the canonical service."""

def helper_func():
    """Does a thing."""
'''
    states = _states(src)
    assert states["EmbeddingService"] == "deprecated"
    assert states["helper_func"] == "deprecated"  # module attribution


def test_deprecated_alias_method_docstring():
    """qdrant upsert_capability_vector shape."""
    src = '''
class QdrantService:
    """Live service."""

    async def upsert_capability_vector(self):
        """Deprecated alias."""
        return None
'''
    states = _states(src)
    assert states["QdrantService"] == "discovered"
    assert states["QdrantService.upsert_capability_vector"] == "deprecated"


def test_deprecated_directive_in_docstring():
    """path_utils shape (i): sphinx directive."""
    src = '''
def matches_glob_pattern(path, pattern):
    """Check if path matches glob pattern.

    .. deprecated::
        Use the canonical helper directly.
    """
    return True
'''
    assert _states(src)["matches_glob_pattern"] == "deprecated"


def test_deprecation_warning_in_body():
    """path_utils shape (ii): warnings.warn(DeprecationWarning)."""
    src = '''
import warnings

def matches_any_pattern(path, patterns):
    """Check if path matches any pattern."""
    warnings.warn("gone soon", DeprecationWarning, stacklevel=2)
    return True
'''
    assert _states(src)["matches_any_pattern"] == "deprecated"


# ---------------------------------------------------------------------------
# Property must-not-fire — the two #804 ORM aliases (D1 exclusion)
# ---------------------------------------------------------------------------


def test_deprecated_property_does_not_fire():
    """role_name/resource_name shape: attribute reads are not call edges."""
    src = '''
class LlmResource:
    """ORM model."""

    @property
    def resource_name(self) -> str:
        """Backwards-compatible alias (legacy code expects resource_name)."""
        return self.name
'''
    states = _states(src)
    assert states["LlmResource.resource_name"] == "discovered"


def test_deprecated_property_setter_does_not_fire():
    src = '''
class AuditFinding:
    """Model."""

    @details.setter
    def details(self, value):
        """Backwards-compatible alias for structured finding context."""
        self.context = value
'''
    assert _states(src)["AuditFinding.details"] == "discovered"


# ---------------------------------------------------------------------------
# Dispatch must-not-fire (D2 grace) and prose must-not-fire
# ---------------------------------------------------------------------------


def test_deprecated_typer_command_does_not_fire():
    """The measured 'DEPRECATED alias' CLI commands: dispatch grace."""
    src = '''
@app.command("symbol-drift")
def symbol_drift_cmd(ctx):
    """DEPRECATED alias. Use: core-admin status drift symbol."""
    deprecated_command("inspect symbol-drift", "status drift symbol")
'''
    assert _states(src)["symbol_drift_cmd"] == "discovered"


def test_registered_action_does_not_fire():
    src = '''
@register_action(action_id="fix.something")
def action_fix_something(core_context, **kwargs):
    """DEPRECATED: superseded by fix.other."""
    return None
'''
    assert _states(src)["action_fix_something"] == "discovered"


def test_legacy_processing_prose_does_not_fire():
    """The legacy scanner's own module: mentions legacy, never self-declares."""
    src = '''
"""Legacy Scanner Logic - Pure read-only analysis.

Scans the codebase for markers that indicate technical debt:
workarounds, deprecated code, and unresolved TODOs."""

def scan_for_legacy_markers(root):
    """Walk the tree collecting legacy markers."""
    return []
'''
    assert _states(src)["scan_for_legacy_markers"] == "discovered"


def test_plain_live_symbol_stays_discovered():
    src = '''
def healthy_function():
    """Does useful work."""
    return 42
'''
    assert _states(src)["healthy_function"] == "discovered"


def test_member_documentation_in_class_notes_does_not_fire():
    """The AuditFinding shape (measured misfire, fixed): a live class whose
    docstring Notes document a MEMBER as a backwards-compatible alias. The
    self-declaration must sit in the first line to count."""
    src = '''
class AuditFinding:
    """Represents a single finding from a constitutional audit check.

    Notes:
        - `details` is a backwards-compatible alias to `context`.
    """
'''
    assert _states(src)["AuditFinding"] == "discovered"


def test_tombstone_do_not_use_module_fires():
    """The sync_manifest shape: 'LEGACY / DEPRECATED — DO NOT USE.' module."""
    src = '''
"""
LEGACY / DEPRECATED — DO NOT USE.

This module previously synchronized a legacy manifest.
"""

async def sync_manifest():
    """Disabled operation: BODY may not write to intent."""
    return None
'''
    assert _states(src)["sync_manifest"] == "deprecated"


# ---------------------------------------------------------------------------
# Engine pin — deprecation-scoped state propagation (D5)
# ---------------------------------------------------------------------------


def test_engine_propagates_state_deprecation_scoped_only():
    """The merge must move state into/out of 'deprecated' without clobbering
    other lifecycle values (e.g. 'classified')."""
    from body.introspection.sync.engine import run_db_merge

    sql = inspect.getsource(run_db_merge)
    assert "state = st.state" in sql
    assert "IS DISTINCT FROM" in sql
    assert "st.state = 'deprecated' OR core.symbols.state = 'deprecated'" in sql
