# src/will/workers/audit_violation_filter.py
"""
Actionability filter for AuditViolationSensor.

Removes violations the remediator cannot act on. Four drop rules:

1. Sentinel file paths — the auditor could not resolve a real source
   file. These are project-scope findings ("System", "DB", "unknown")
   or empty strings.
2. Symbol-pair synthetic paths — file_path starts with "__symbol_pair__"
   indicating the normalizer's fallback gave up on path recovery.
3. Non-Python files — the remediator only operates on .py source files
   today.
4. Malformed rule IDs — the auditor sometimes returns an enforcement
   mapping file path as check_id (e.g.
   "enforcement/mappings/arch/foo.yaml"). Real rule IDs never contain
   "/". These create misleading subjects on the blackboard.

When the actionability vocabulary evolves — a new sentinel pattern, a
new file-type rule, a new malformed-ID shape — this is the module that
changes.

LAYER: will/workers — collaborator of AuditViolationSensor. Pure
transformation: takes a list of violation dicts and returns a filtered
list. No IO, no side effects beyond debug logging.
"""

from __future__ import annotations

from typing import Any

from shared.logger import getLogger


logger = getLogger(__name__)

# File path values produced by the auditor for project-scope or unresolvable
# findings. The remediator cannot open these as source files — skip them.
_SENTINEL_FILE_PATHS: frozenset[str] = frozenset(
    {
        "System",
        "system",
        "DB",
        "db",
        "unknown",
        "none",
        "None",
        "",
    }
)


# ID: df7ecb9e-e997-4ebd-85ec-3a4c60e1359d
def filter_actionable_violations(
    violations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Remove violations that cannot be acted on by the remediator.

    See module docstring for the four drop rules. Drops are logged at
    DEBUG so the caller can see exactly which violations were filtered
    and why.
    """
    actionable = []
    for v in violations:
        file_path = str(v.get("file_path") or "")
        rule_id = str(v.get("rule_id") or "")

        # Drop sentinel file paths
        if file_path in _SENTINEL_FILE_PATHS:
            logger.debug(
                "AuditViolationSensor: dropping sentinel file_path=%r rule=%r",
                file_path,
                rule_id,
            )
            continue

        if file_path.startswith("__symbol_pair__"):
            logger.debug(
                "AuditViolationSensor: dropping symbol-pair file_path=%r rule=%r",
                file_path,
                rule_id,
            )
            continue

        # Drop findings where the file path is not a Python source file
        if not file_path.endswith(".py"):
            logger.debug(
                "AuditViolationSensor: dropping non-Python file_path=%r rule=%r",
                file_path,
                rule_id,
            )
            continue

        # Drop malformed rule IDs — file paths leaked from the auditor engine.
        # A real rule ID never contains "/" (e.g. "purity.no_dead_code").
        # Enforcement mapping paths do (e.g. "enforcement/mappings/arch/foo.yaml").
        if "/" in rule_id:
            logger.debug(
                "AuditViolationSensor: dropping malformed rule_id=%r file=%r",
                rule_id,
                file_path,
            )
            continue

        actionable.append(v)

    return actionable
