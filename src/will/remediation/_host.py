# src/will/remediation/_host.py
"""Typing-only host contract for the RemediationCeremony mixins.

The mixins in this package (CrateCanary, Context, LLM) are only ever
combined into :class:`RemediationCeremony`, which sets ``_ctx`` /
``_target_rule`` / ``_write`` in ``__init__``. This module gives mypy a
static view of that host surface so each mixin type-checks in isolation
instead of reporting ``attr-defined`` on attributes the host supplies.

Zero runtime effect: at runtime ``HostBase`` is ``object``, so the mixins
are plain mixins and the real composition is supplied by
``RemediationCeremony`` itself. Only under ``TYPE_CHECKING`` do the mixins
inherit the host-set attributes.

Mirrors will/workers/violation_remediator_body/_host.py, which serves the
same purpose for the mixins ADR-153 extracted this package from — the
difference is this host has no ``Worker`` base and no ``_worker_uuid``
(the ceremony no longer claims findings or holds a Worker identity; it
posts and marks through an injected ``RemediationBlackboard``, ADR-153 D2).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from will.remediation.blackboard import RemediationBlackboard

    class _CeremonyHost:
        """Static view of the class the mixins are composed into."""

        _ctx: Any
        _target_rule: str | None
        _write: bool
        _blackboard: RemediationBlackboard

    HostBase = _CeremonyHost
else:
    HostBase = object
