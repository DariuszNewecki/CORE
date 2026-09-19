# src/shared/workers/launch.py
"""
Worker launch-mode resolver - single source of the daemon | on_demand decision.

Issue #898: ``metadata.status`` declares a worker's constitutional
availability; ``implementation.launch`` declares how an active worker is
activated. ``daemon`` (the default when the key is absent, for backward
compatibility) means the CORE daemon discovers, instantiates and hosts the
worker and continuous liveness is expected while the daemon runs.
``on_demand`` means a legitimate caller constructs one instance per
invocation and drives the ordinary ``Worker.start()`` lifecycle; daemon
discovery must not import, instantiate, schedule or report it as an error,
and no heartbeat is expected between invocations.

Every consumer that needs this distinction (daemon discovery, the
``workers run`` loader, the shared liveness state, runtime_gate) routes
through :func:`resolve_launch`. No consumer may special-case a worker by
filename or class name.

The vocabulary is closed and read from law: ``.intent/META/enums.json``
``worker_launch`` via ``canonical_enums.get_enum_members``. A value outside
that set is a ``GovernanceError`` (fail-closed), never a silent default.

LAYER: shared/workers — pure function over a parsed declaration dict.
No DB access, no file writes, no Worker dependency. Safe to import from
CLI, Mind engines, body services, and will/workers alike.
"""

from __future__ import annotations

from typing import Any

from shared.infrastructure.intent.canonical_enums import get_enum_members
from shared.infrastructure.intent.errors import GovernanceError


_ENUM_NAME = "worker_launch"

# The two values the runtime branches on. Membership in the canonical enum is
# re-checked on every resolve, so a drift between these names and enums.json
# surfaces as a GovernanceError rather than a silent misclassification.
LAUNCH_DAEMON = "daemon"
LAUNCH_ON_DEMAND = "on_demand"


# ID: 55d8200a-8044-44e5-9345-df660905a35f
def resolve_launch(declaration: dict[str, Any]) -> str:
    """Return the launch mode declared by a parsed worker declaration.

    Reads ``implementation.launch``; an absent key resolves to
    ``LAUNCH_DAEMON`` (backward compatibility for every declaration written
    before #898). The resolved value is validated against the canonical
    ``worker_launch`` enum; an unknown value raises ``GovernanceError``.
    """
    implementation = declaration.get("implementation") or {}
    raw = implementation.get("launch")
    launch = LAUNCH_DAEMON if raw is None else str(raw)

    members = get_enum_members(_ENUM_NAME)
    if launch not in members:
        worker_id = (declaration.get("metadata") or {}).get("id", "<unknown>")
        raise GovernanceError(
            f"Worker declaration {worker_id} has unknown implementation.launch "
            f"{launch!r}; canonical {_ENUM_NAME} values are "
            f"{sorted(members)}."
        )
    return launch
