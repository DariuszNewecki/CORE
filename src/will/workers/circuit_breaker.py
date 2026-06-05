# src/will/workers/circuit_breaker.py
"""
Circuit-breaker on repeated proposal failures (ADR-038 / closes #281).

Bounds failure amplification in the autonomous remediation loop. When the
most recent N failed proposals for the same (ref_id, file_path) carry the
same canonical error signature, the circuit trips: the caller stops
minting new proposals for that key, marks the current cycle's findings
DELEGATE, and posts a `governance.circuit_breaker_tripped` finding for
governor triage.

Three pure functions plus a config dataclass:

- load_circuit_breaker_config — read .intent/enforcement/config/circuit_breaker.yaml
  via IntentRepository (governance values never live in src/, per ADR-031
  / #282).
- canonical_signature — strip volatile substrings from a failure_reason
  and return its first window_chars characters.
- recent_consecutive_identical_count — query the failed-proposal tail
  for a (ref_id, file_path) and walk it from newest to oldest, counting
  consecutive identical signatures.
- trip — DELEGATE the current cycle's findings via the existing
  blackboard helper and post the `governance.circuit_breaker_tripped`
  hazard finding through the calling Worker (so it carries Worker
  attribution per ADR-011).

LAYER: will/workers — internal collaborator of ViolationRemediatorWorker.
Accepts a session as a parameter; no direct database session imports.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select

from shared.logger import getLogger
from shared.workers.base import Worker


logger = getLogger(__name__)

_FALLBACK_THRESHOLD_N = 5
_FALLBACK_SIGNATURE_WINDOW_CHARS = 200
_FALLBACK_MAX_LOOKBACK = 25
_FALLBACK_VOLATILE_PATTERNS: list[dict[str, str]] = [
    {
        "name": "iso_timestamp",
        "regex": (
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}" r"(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?"
        ),
    },
    {
        "name": "uuid",
        "regex": (r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"),
    },
    {"name": "duration_seconds", "regex": r"\d+\.\d+s"},
    {"name": "pid", "regex": r"pid=\d+"},
]


@dataclass(frozen=True)
# ID: c0fd3c97-b14a-4a77-a1ca-681245394db3
class CircuitBreakerConfig:
    """Loaded view of circuit_breaker.yaml with compiled regex patterns."""

    threshold_n: int = _FALLBACK_THRESHOLD_N
    signature_window_chars: int = _FALLBACK_SIGNATURE_WINDOW_CHARS
    max_lookback: int = _FALLBACK_MAX_LOOKBACK
    volatile_patterns: tuple[re.Pattern[str], ...] = field(default_factory=tuple)


# ID: 2d548b15-fdaf-4230-8951-c30f1ef7d985
def load_circuit_breaker_config() -> CircuitBreakerConfig:
    """
    Load .intent/enforcement/config/circuit_breaker.yaml via IntentRepository.

    Returns a CircuitBreakerConfig with compiled regex patterns. On any
    failure — missing file, parse error, malformed entries — returns a
    config built from fallback defaults and logs a warning so callers
    degrade gracefully rather than halting the remediation loop.
    """
    raw: dict[str, Any] | None = None
    try:
        from shared.infrastructure.intent.intent_repository import (
            get_intent_repository,
        )

        repo = get_intent_repository()
        config_path = repo.resolve_rel("enforcement/config/circuit_breaker.yaml")
        loaded = repo.load_document(config_path)
        if isinstance(loaded, dict):
            raw = loaded
        else:
            logger.warning(
                "circuit_breaker: circuit_breaker.yaml did not parse as a dict "
                "— using fallback defaults."
            )
    except Exception as exc:
        logger.warning(
            "circuit_breaker: could not load .intent/enforcement/config/"
            "circuit_breaker.yaml (%s) — using fallback defaults.",
            exc,
        )

    raw = raw or {}
    threshold_n = int(raw.get("threshold_n", _FALLBACK_THRESHOLD_N))
    signature_window_chars = int(
        raw.get("signature_window_chars", _FALLBACK_SIGNATURE_WINDOW_CHARS)
    )
    max_lookback = max(
        int(raw.get("max_lookback", _FALLBACK_MAX_LOOKBACK)),
        threshold_n,
    )

    pattern_specs = raw.get("volatile_patterns") or _FALLBACK_VOLATILE_PATTERNS
    compiled: list[re.Pattern[str]] = []
    for spec in pattern_specs:
        if not isinstance(spec, dict) or "regex" not in spec:
            continue
        try:
            compiled.append(re.compile(spec["regex"], re.IGNORECASE))
        except re.error as exc:
            logger.warning(
                "circuit_breaker: skipping malformed pattern %r (%s)",
                spec.get("name", "<unnamed>"),
                exc,
            )

    return CircuitBreakerConfig(
        threshold_n=threshold_n,
        signature_window_chars=signature_window_chars,
        max_lookback=max_lookback,
        volatile_patterns=tuple(compiled),
    )


# ID: 0bd3e5d6-c721-4de6-a2b5-37d72e648f8e
def canonical_signature(
    failure_reason: str | None,
    config: CircuitBreakerConfig,
) -> str:
    """
    Reduce a failure_reason to a stable signature for identity comparison.

    Strips substrings matching every compiled volatile pattern (timestamps,
    UUIDs, duration suffixes, pids), collapses runs of whitespace to a
    single space, then truncates to the configured signature_window_chars.
    None and empty strings collapse to "" so they compare equal to
    themselves.
    """
    if not failure_reason:
        return ""

    normalized = failure_reason
    for pattern in config.volatile_patterns:
        normalized = pattern.sub("", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized[: config.signature_window_chars]


# ID: 942750c7-8b03-4f02-8a7a-e62bcfef9af9
async def recent_consecutive_identical_count(
    session: Any,
    *,
    ref_id: str,
    ref_kind: str,
    file_path: str | None,
    config: CircuitBreakerConfig,
) -> tuple[int, str | None, str | None, str | None]:
    """
    Count the streak of most-recent identical-signature failures for a key.

    Queries `core.autonomous_proposals` for `status='failed'` rows whose
    `actions` JSONB contains an element matching the given (ref_id,
    ref_kind, file_path) tuple, ordered by `execution_completed_at DESC`,
    bounded by `config.max_lookback`. Walks the result newest-to-oldest
    counting consecutive entries whose `failure_reason` canonicalizes to
    the same signature as the newest one.

    Returns:
        (count, signature, last_proposal_id, last_failure_reason)

        count                  — length of the consecutive identical streak
                                 starting from the newest failure (0 if
                                 there are no failures for the key).
        signature              — the streak's canonical signature, or
                                 None when count == 0.
        last_proposal_id       — public id of the most recent failed
                                 proposal in the streak (None when
                                 count == 0).
        last_failure_reason    — raw failure_reason of that proposal,
                                 truncated by Postgres only if the
                                 column is truncated upstream (Text is
                                 unbounded so this is the full text).

    Fail-soft: any DB error returns (0, None, None, None) and is logged.
    The caller treats that as "no streak detected" and proceeds with
    proposal creation — degrading toward retry rather than toward
    silent rejection.
    """
    from shared.infrastructure.database.models.autonomous_proposals import (
        AutonomousProposal,
    )

    try:
        if ref_kind == "flow":
            match_element: dict[str, Any] = {"flow_id": ref_id}
        else:
            params: dict[str, Any] = {"write": True}
            if file_path is not None:
                params["file_path"] = file_path
            match_element = {"action_id": ref_id, "parameters": params}

        stmt = (
            select(AutonomousProposal)
            .where(AutonomousProposal.status == "failed")
            .where(AutonomousProposal.actions.contains([match_element]))
            .order_by(AutonomousProposal.execution_completed_at.desc())
            .limit(config.max_lookback)
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()
    except Exception as exc:
        logger.warning(
            "circuit_breaker: failure-history query failed for "
            "(%s, %s, %s): %s — proceeding without circuit gate.",
            ref_kind,
            ref_id,
            file_path,
            exc,
        )
        return 0, None, None, None

    if not rows:
        return 0, None, None, None

    newest = rows[0]
    newest_signature = canonical_signature(newest.failure_reason, config)
    last_proposal_id = newest.proposal_id
    last_failure_reason = newest.failure_reason or ""

    count = 0
    for row in rows:
        if canonical_signature(row.failure_reason, config) == newest_signature:
            count += 1
        else:
            break

    return count, newest_signature, last_proposal_id, last_failure_reason


# ID: 62ca7f00-f3ed-464e-8034-afbbf6fc5ab8
async def trip(
    *,
    worker: Worker,
    ref_id: str,
    ref_kind: str,
    file_path: str | None,
    findings: list[dict[str, Any]],
    count: int,
    signature: str | None,
    last_proposal_id: str | None,
    last_failure_reason: str | None,
    mark_delegated: Any,
) -> None:
    """
    Trip the circuit for a (ref_id, file_path) key.

    Two effects, both fail-soft:

    1. Mark the current cycle's findings DELEGATE via the caller's
       `mark_delegated` helper (the existing
       ViolationRemediatorWorker._mark_delegated). This stops the loop
       from re-claiming the same findings on subsequent cycles.
    2. Post a `governance.circuit_breaker_tripped` observation (terminal
       at creation, status=abandoned) through the Worker so the entry
       carries Worker attribution per ADR-011 and surfaces on the
       operator's hazard queue alongside governance.instrument_degraded.

    Errors in either step are logged but never propagated — the
    remediator's run-loop accounting must not be reversed by a hiccup
    in the trip path.
    """
    try:
        delegated = await mark_delegated(findings)
    except Exception as exc:
        delegated = 0
        logger.error(
            "circuit_breaker: failed to mark findings DELEGATE for (%s, %s, %s): %s",
            ref_kind,
            ref_id,
            file_path,
            exc,
        )

    payload: dict[str, Any] = {
        "ref_id": ref_id,
        "ref_kind": ref_kind,
        "file_path": file_path,
        "failure_count": count,
        "error_signature": signature,
        "last_proposal_id": last_proposal_id,
        "last_failure_reason": last_failure_reason,
        "findings_delegated": delegated,
    }

    try:
        await worker.post_observation(
            subject="governance.circuit_breaker_tripped",
            payload=payload,
            status="abandoned",
        )
    except Exception as exc:
        logger.error(
            "circuit_breaker: failed to post hazard observation for (%s, %s, %s): %s",
            ref_kind,
            ref_id,
            file_path,
            exc,
        )

    logger.warning(
        "circuit_breaker: TRIPPED for (%s, %s, %s) after %d identical "
        "failures (signature=%r, last_proposal=%s) — %d findings delegated, "
        "no new proposal will be created this cycle.",
        ref_kind,
        ref_id,
        file_path,
        count,
        signature,
        last_proposal_id,
        delegated,
    )
