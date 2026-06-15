# src/will/workers/violation_remediator_body/_host.py
"""Typing-only host contract for the ViolationRemediator mixins.

The mixins in this package (Blackboard, Ceremony, Context, LLM) are only ever
combined into :class:`ViolationRemediator`, which is a :class:`Worker` that
additionally sets ``_ctx`` / ``_target_rule`` / ``_write`` in ``__init__``.
This module gives mypy a static view of that host surface so each mixin
type-checks in isolation instead of reporting ``attr-defined`` on attributes
the host supplies.

Zero runtime effect: at runtime ``HostBase`` is ``object``, so the mixins are
plain mixins and the real ``Worker`` MRO is supplied by ``ViolationRemediator``
itself. Only under ``TYPE_CHECKING`` do the mixins inherit the ``Worker``
contract plus the host-set attributes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    import uuid

    from shared.workers.base import Worker

    class _RemediatorHost(Worker):
        """Static view of the class the mixins are composed into."""

        _ctx: Any
        _target_rule: str | None
        _write: bool
        _worker_uuid: uuid.UUID

    HostBase = _RemediatorHost
else:
    HostBase = object
