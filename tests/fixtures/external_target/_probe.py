"""Subprocess probe for the external-target authority tests (Unit C).

Runs in a genuinely fresh interpreter, once per invocation, so
``get_intent_repository()``'s process-wide singleton (see
``shared.infrastructure.intent.intent_repository``) is never contaminated
by CORE's own ``.intent/`` having already been loaded elsewhere in the
same pytest session -- the same isolation technique Units A and B's own
tests already use for singleton-sensitive properties.

Not a general-purpose test runner: a small, fixed set of modes, each
calling a real, unmodified CORE function directly -- never reproducing its
logic. Invoked as ``python _probe.py <mode>``, with ``REPO_PATH``/``MIND``
already bound in the environment by the parent test process. JSON in on
stdin (where a mode needs input), JSON out on stdout.
"""

from __future__ import annotations

import asyncio
import json
import sys
from types import SimpleNamespace


def _mode_root() -> dict:
    from shared.infrastructure.intent.intent_repository import get_intent_repository

    return {"intent_root": str(get_intent_repository().root)}


def _mode_envelope() -> dict:
    from shared.infrastructure.intent.action_risk import (
        load_safe_auto_approval_envelope,
    )

    envelope = load_safe_auto_approval_envelope()
    if envelope.get("_error"):
        return {"_error": True, "reason": envelope.get("reason")}
    return {
        "authorized_actions": sorted(envelope["authorized_actions"]),
        "authorized_path_prefixes": list(envelope["authorized_path_prefixes"]),
        "authorized_extensions": list(envelope["authorized_extensions"]),
    }


def _mode_validate(payload: dict) -> dict:
    from will.autonomy.safe_auto_approval_envelope import (
        SafeAutoApprovalDeniedError,
        validate_envelope,
    )

    try:
        validate_envelope(payload["actions"], payload["scope"])
        return {"ok": True}
    except SafeAutoApprovalDeniedError as exc:
        return {"ok": False, "error": str(exc), "error_type": "denied"}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "error_type": type(exc).__name__}


def _mode_policy_resolve() -> dict:
    import body.atomic  # noqa: F401 -- triggers action registration
    from body.atomic.executor import ActionExecutor
    from body.atomic.registry import action_registry

    definition = action_registry.get("fix.format")
    if definition is None:
        return {"ok": False, "error": "fix.format not registered"}

    # Calls the real, unmodified ActionExecutor._validate_policies -- the
    # exact function ActionExecutor.execute() itself calls at step 2 -- as
    # an unbound function. Its body never reads `self`, so passing None
    # exercises the real policy-resolution logic without constructing an
    # ActionExecutor (which would require a full CoreContext and would run
    # apply_risk_config, i.e. genuinely "invoking ActionExecutor"). This is
    # a deliberate, narrow choice to satisfy "use the real ... validation
    # function, do not reproduce its logic" while staying outside the
    # Scope Exclusions' "do not invoke ... ActionExecutor".
    result = asyncio.run(ActionExecutor._validate_policies(None, definition))
    return result


def _mode_physical_containment(payload: dict) -> dict:
    """Calls the real, unmodified ``_check_physical_containment`` (Unit
    C.1) against this process's real ``REPO_PATH``, which the parent test
    has already prepared with whatever real symlink scenario is under
    test. Uses the real ``get_intent_repository()`` singleton in this
    fresh subprocess, so the envelope genuinely loads from the fixture's
    own ``.intent/`` -- no mocking anywhere in this mode."""
    import os

    from body.atomic.executor import _check_physical_containment

    exec_context = SimpleNamespace(
        git_service=SimpleNamespace(repo_path=os.environ["REPO_PATH"])
    )
    reason = _check_physical_containment(exec_context, payload["file_path"])
    return {"denied": reason is not None, "reason": reason}


def main() -> int:
    mode = sys.argv[1]
    if mode == "root":
        result = _mode_root()
    elif mode == "envelope":
        result = _mode_envelope()
    elif mode == "validate":
        payload = json.loads(sys.stdin.read())
        result = _mode_validate(payload)
    elif mode == "policy_resolve":
        result = _mode_policy_resolve()
    elif mode == "physical_containment":
        payload = json.loads(sys.stdin.read())
        result = _mode_physical_containment(payload)
    else:
        raise ValueError(f"unknown probe mode: {mode!r}")

    json.dump(result, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
