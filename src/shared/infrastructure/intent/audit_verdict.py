# src/shared/infrastructure/intent/audit_verdict.py
# ID: shared.infrastructure.intent.audit_verdict
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

LAYER: shared/infrastructure/intent — pure helper. Returns a dict;
does not import AuditVerdict or the auditor. The governance layer
decides how to consume the dict. No imports from will/, body/, or cli/.
"""

from __future__ import annotations

from typing import Any

from shared.logger import getLogger
from shared.models.audit_models import AuditSeverity


logger = getLogger(__name__)


_KNOWN_PRECONDITIONS: frozenset[str] = frozenset({"any_crashed_rules"})

_REQUIRED_LIST_KEYS: tuple[str, ...] = (
    "fail_severities",
    "ignored_finding_types",
    "degraded_on",
)


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


# ID: a7d4f2e1-3c8b-4f9a-b2d6-5e1c7f9a3b4d
def load_audit_verdict_policy() -> dict[str, Any]:
    """
    Load .intent/enforcement/config/audit_verdict.yaml via IntentRepository.

    Returns the parsed-and-validated policy dict on success. On ANY
    failure — missing file, parse error, unexpected top-level type,
    schema validation failure — returns the error sentinel

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
        return config

    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
        logger.error(
            "audit_verdict: could not load .intent/enforcement/config/"
            "audit_verdict.yaml (%s)",
            reason,
        )
        return {"_error": True, "reason": reason}
