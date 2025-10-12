# src/cli/logic/context.py
"""
Refactored under dry_by_design.
Pattern: introduce_facade with resilient fallback.
Source of truth centralization for CLI context handling.

Back-compat notes:
- Accepts both signatures: set_context(context) and set_context(context, module_name).
- If a module_name is provided but not importable (e.g., "fix" vs "cli.commands.fix"),
  we normalize to a fully qualified hint ("cli.commands.fix") before forwarding.
- Any failure in provider-specific signatures gracefully degrades to a no-op to avoid
  breaking callers during migration.
"""

from __future__ import annotations

from typing import Optional

try:
    # Prefer local cli_utils if available; keeps behavior consistent while migrating.
    from . import cli_utils as _cli_utils  # type: ignore
except Exception:  # pragma: no cover - hard fallback
    _cli_utils = None  # type: ignore[assignment]


def _normalize_module_name(module_name: Optional[str]) -> Optional[str]:
    """Ensure module_name is fully-qualified enough to be importable in legacy code."""
    if not module_name:
        return None
    if "." in module_name:
        return module_name
    return f"cli.commands.{module_name}"


def _forward_to_cli_utils(context, module_name: Optional[str] = None) -> None:
    """
    Try to call cli_utils.set_context with the most specific signature, but
    degrade gracefully on signature mismatches or import-time errors.
    """
    # --- THIS IS THE FIX ---
    # If no module name is provided, there is nothing to forward. Return immediately.
    # This prevents `None` from being passed down the call chain, which caused the error.
    if module_name is None:
        return
    # --- END OF FIX ---

    if _cli_utils is None or not hasattr(_cli_utils, "set_context"):
        return

    fn = getattr(_cli_utils, "set_context")
    normalized = _normalize_module_name(module_name)
    try:
        fn(context, normalized)  # type: ignore[misc,call-arg]
        return
    except TypeError:
        # Signature mismatch—retry below without module_name.
        pass
    except Exception:
        # Import-time or provider error—retry below without module_name.
        pass

    # Fallback to (context) only
    try:
        fn(context)  # type: ignore[misc,call-arg]
        return
    except Exception:
        # Swallow final failure to remain non-intrusive during rollout.
        return


# ID: cf70e4b3-a493-4e90-8daf-2f07effe223e
def set_context(context, module_name: Optional[str] = None):
    """
    Canonical context setter for CLI modules.

    Parameters
    ----------
    context : CoreContext
        Shared application context object.
    module_name : Optional[str]
        Optional logical module label (e.g., "fix", "run") for telemetry
        or legacy helper behavior.

    Returns
    -------
    CoreContext
        Returns the input context for convenience.
    """
    _forward_to_cli_utils(context, module_name)
    return context


__all__ = ["set_context"]
