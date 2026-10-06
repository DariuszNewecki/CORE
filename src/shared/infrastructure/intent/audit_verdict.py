# src/shared/infrastructure/intent/audit_verdict.py
"""
Audit verdict policy loader.

Single source of truth for the severity-to-verdict mapping, the
finding-type carve-out, and the DEGRADED preconditions consumed by
ConstitutionalAuditor._determine_verdict. The governing document is
.intent/enforcement/config/audit_verdict.yaml, accessed exclusively
via IntentRepository. See ADR-005.

NO HARDCODED FALLBACK. This loader is deliberately different from
its sibling task_type_phases.py: when the YAML is missing, unparseable,
or validation-fails, it returns a sentinel dict

    {"_error": True, "reason": "<human-readable reason>"}

and does NOT substitute default values. The caller
(_determine_verdict) MUST treat the sentinel as AuditVerdict.DEGRADED.

Rationale (ADR-005 §3): for the verdict rule, silent fallback converts
"the verdict law is missing" into "the verdict law is silently the old
one." The failure mode would be indistinguishable from success and
would hide subsequent governance edits. Forcing DEGRADED on missing
policy makes instrument failure loud, visible, and recoverable.

SUBSTRATE MINIMUM (ADR-005 Amendment 2026-10-06, #952). What a verdict
*means* is the same for every project; only *what is checked* is project
law. The bundled machinery floor's audit_verdict.yaml
(``shared/_machinery_floor/enforcement/config/audit_verdict.yaml``) is
read from the installed package -- never from the project's ``.intent/``
-- and its three lists are unioned into the project policy. A project may
add entries (stricter); it can never remove a floor entry. An unreadable
floor is an instrument failure and returns the error sentinel, like a
missing project policy.

LAYER: shared/infrastructure/intent — pure helper. Returns a dict;
does not import AuditVerdict or the auditor. The governance layer
decides how to consume the dict. No imports from will/, body/, or cli/.
"""

from __future__ import annotations

from typing import Any

import yaml

from shared.infrastructure.intent._floor import resolve_floor_path
from shared.logger import getLogger
from shared.models.audit_models import AuditSeverity


logger = getLogger(__name__)


_KNOWN_PRECONDITIONS: frozenset[str] = frozenset(
    {
        "any_crashed_rules",
        "stats_error",
        "any_unmapped_mapping_required_rules",
        "any_blocking_unavailable_rules",
        "law_drift",
    }
)

_REQUIRED_LIST_KEYS: tuple[str, ...] = (
    "fail_severities",
    "ignored_finding_types",
    "degraded_on",
)

_POLICY_REL = ".intent/enforcement/config/audit_verdict.yaml"


def _validate_policy(policy: dict[str, Any]) -> None:
    """
    Validate the loaded policy dict at load time.

    Raises ValueError with a precise, human-readable message on the
    first offending key/value. The outer loader converts any exception
    to the error sentinel.
    """
    for key in _REQUIRED_LIST_KEYS:
        if key not in policy:
            raise ValueError(f"audit_verdict: required key {key!r} is missing")
        if not isinstance(policy[key], list):
            raise ValueError(
                f"audit_verdict: {key!r} must be a list, got "
                f"{type(policy[key]).__name__}"
            )

    valid_severity_names = set(AuditSeverity.__members__)
    for name in policy["fail_severities"]:
        if not isinstance(name, str):
            raise ValueError(
                f"audit_verdict: fail_severities entries must be strings, "
                f"got {type(name).__name__} ({name!r})"
            )
        if name not in valid_severity_names:
            raise ValueError(
                f"audit_verdict: fail_severities entry {name!r} is not a "
                f"valid AuditSeverity name; allowed values are "
                f"{sorted(valid_severity_names)}"
            )

    for precondition in policy["degraded_on"]:
        if precondition not in _KNOWN_PRECONDITIONS:
            raise ValueError(
                f"audit_verdict: degraded_on entry {precondition!r} is not "
                f"a known precondition; allowed values are "
                f"{sorted(_KNOWN_PRECONDITIONS)}"
            )


def _load_floor_policy() -> dict[str, Any]:
    """Load and validate the substrate minimum from the installed package.

    Raises on any failure; the outer loader converts that to the error
    sentinel. Deliberately not routed through IntentRepository: the floor
    must be the package's bytes, not whatever the project's .intent/ holds.
    """
    path = resolve_floor_path(_POLICY_REL)
    if path is None:
        raise FileNotFoundError(
            "bundled machinery floor has no enforcement/config/audit_verdict.yaml"
        )
    floor = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(floor, dict):
        raise ValueError(
            f"floor audit_verdict.yaml did not parse as a dict "
            f"(got {type(floor).__name__})"
        )
    _validate_policy(floor)
    return floor


def _apply_floor(policy: dict[str, Any], floor: dict[str, Any]) -> dict[str, Any]:
    """Union the floor's entries into each policy list, project order first."""
    effective = dict(policy)
    for key in _REQUIRED_LIST_KEYS:
        merged = list(policy[key])
        merged.extend(entry for entry in floor[key] if entry not in merged)
        effective[key] = merged
    return effective


# ID: a7d4f2e1-3c8b-4f9a-b2d6-5e1c7f9a3b4d
def load_audit_verdict_policy() -> dict[str, Any]:
    """
    Load .intent/enforcement/config/audit_verdict.yaml via IntentRepository.

    Returns the parsed-and-validated policy dict on success, with the
    bundled floor's entries unioned into each list (a project cannot
    remove them; ADR-005 Amendment 2026-10-06). On ANY failure — missing
    file, parse error, unexpected top-level type, schema validation
    failure, unreadable floor — returns the error sentinel

        {"_error": True, "reason": "<human-readable reason>"}

    and logs the specific reason at ERROR level. Callers MUST treat the
    sentinel as AuditVerdict.DEGRADED; see ADR-005 §3.
    """
    try:
        from shared.infrastructure.intent.intent_repository import (
            get_intent_repository,
        )

        repo = get_intent_repository()
        config_path = repo.resolve_rel("enforcement/config/audit_verdict.yaml")
        config = repo.load_document(config_path)
        if not isinstance(config, dict):
            reason = (
                f"audit_verdict.yaml did not parse as a dict "
                f"(got {type(config).__name__})"
            )
            logger.error("audit_verdict: %s", reason)
            return {"_error": True, "reason": reason}

        _validate_policy(config)
        return _apply_floor(config, _load_floor_policy())

    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
        logger.error(
            "audit_verdict: could not load the audit verdict policy (%s)",
            reason,
        )
        return {"_error": True, "reason": reason}


# ID: 1e43c492-57cc-470f-99d8-23e394af27e8
def law_drift_degrades(policy: dict[str, Any], relationship: str | None) -> bool:
    """True when the policy declares ``law_drift`` and the evaluated law is not
    known to be the law of record (relationship DRIFT or UNKNOWN; ADR-169 D2).

    One implementation for every verdict path (online auditor, stateless
    audit, persisted runs), so they cannot disagree about drift.
    """
    if policy.get("_error"):
        return False  # the error sentinel already forces DEGRADED
    return "law_drift" in policy.get("degraded_on", []) and relationship != "MATCH"
