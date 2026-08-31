# src/shared/infrastructure/intent/vocabulary_register_validator.py

"""Operational-register casing validation for .intent/ artifacts.

Enforces governance.vocabulary_registers.operational_fields_must_be_lowercase
(.intent/rules/governance/vocabulary_registers.json). Two independent checks:

1. Authored field-instance casing across .intent/ artifacts. Path-qualified,
   not bare-field-name matching -- a bare name like `class` or `status`
   collides with unrelated fields elsewhere in the corpus (`implementation.class`
   names a Python class; `mappings.*.status` in auto_remediation.yaml carries
   an unrelated ACTIVE/DELEGATE/PENDING routing vocabulary). Any occurrence of
   a watched bare field name whose path is neither governed nor explicitly
   excluded is itself a violation ("unclassified occurrence") rather than a
   silent pass -- a future document shape introducing an unanticipated path
   fails loud instead of silently widening an allowlist gap.

2. A ratification guard over the enum vocabularies `.intent/META/enums.json`
   itself declares for this register (catches a silent revert of the
   vocabulary declaration, independent of whether any field currently uses it).

Two callers share this module (ADR-158, #854): IntentRepository.__init__
uses it as a fail-closed bootstrap guard (CORE refuses to load a .intent/
tree with a casing violation in this scope); artifact_gate's
register_casing_validation check_type uses it as the audit-time, G2-provable
mechanism. The two have different failure semantics -- a bootstrap-guard
violation raises and prevents CORE from starting; an audit-time violation is
a finding. In production the bootstrap guard means the audit path can never
actually observe a violation (a bad tree never gets far enough to be
audited) -- see the enforcement mapping's own comment for that division
stated explicitly.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from shared.infrastructure.intent.errors import GovernanceError


_REGISTER_GRAMMAR = re.compile(r"^[a-z][a-z0-9_]*$")

# Field paths confirmed (2026-08-31, ADR-158) to carry real Operational-register
# values across the live .intent/ corpus. "*" matches any single dict key;
# "[]" matches any list index. A trailing single-element tuple is a top-level
# key (workflow-stage and taxonomy documents declare these directly).
GOVERNED_PATHS: frozenset[tuple[str, ...]] = frozenset(
    {
        ("metadata", "authority"),
        ("metadata", "phase"),
        ("metadata", "status"),
        ("identity", "class"),
        ("mandate", "phase"),
        ("rules", "[]", "authority"),
        ("rules", "[]", "phase"),
        ("rules", "[]", "enforcement"),
        ("roles", "*", "authority"),
        ("separation_of_duties", "*", "enforcement"),
        ("separation_of_duties", "*", "status"),
        ("authority",),
        ("phase",),
        ("status",),
    }
)

# Field paths confirmed to carry a DIFFERENT vocabulary despite sharing a
# watched bare name -- never flagged, but documented so the reason is visible.
EXCLUDED_PATHS: frozenset[tuple[str, ...]] = frozenset(
    {
        # Python class reference (e.g. "RepoCrawlerWorker"), not an
        # operational `class:` value (e.g. "sensing"/"acting").
        ("implementation", "class"),
        # auto_remediation.yaml's per-rule remediation routing state
        # (ACTIVE/DELEGATE/PENDING) -- an unrelated, legitimately
        # UPPER_CASE vocabulary that happens to share the field name.
        ("mappings", "*", "status"),
        # A citation ("ADR-075 D1"), not an authority-level value.
        ("namespaces", "project", "reserved_names", "*", "authority"),
        # Prose ("RepoCrawlerWorker is the authoritative writer..."),
        # not an authority-level value.
        ("projections", "[]", "authority"),
    }
)

WATCHED_FIELD_NAMES = frozenset(
    {"authority", "phase", "enforcement", "status", "class"}
)

# .intent/META/enums.json definitions confirmed (2026-08-31, ADR-158) to
# declare Operational-register vocabulary. `audit_severity` joined this set
# via ADR-059 D2 + ADR-158 D1. Deliberately NOT every enums.json definition --
# many legitimately use dot- or hyphen-separated compound identifiers (e.g.
# `blackboard_subject`'s "worker.heartbeat", `action_impact`'s "write-code")
# that are lowercase but fall outside this rule's strict `[a-z][a-z0-9_]*$`
# grammar for a different, valid reason; checking them here would false-positive.
ENUMS_RATIFIED_NAMES = frozenset({"authority", "phase", "strength", "audit_severity"})

_ENUMS_JSON_REL = "META/enums.json"
_SCAN_EXCLUDE_PREFIXES = ("META/", "enforcement/mappings/")


@dataclass(frozen=True)
# ID: 3a7c9e1b-6d4f-4a82-9b3e-7c1f5a8d2e6b
class RegisterCasingReport:
    violations: list[str]


def _path_matches(path: tuple[str, ...], pattern: tuple[str, ...]) -> bool:
    if len(path) != len(pattern):
        return False
    return all(
        expected in ("*", "[]") or actual == expected
        for actual, expected in zip(path, pattern)
    )


def _classify_path(path: tuple[str, ...]) -> str:
    """Return 'governed', 'excluded', or 'unclassified' for a field path."""
    if any(_path_matches(path, p) for p in GOVERNED_PATHS):
        return "governed"
    if any(_path_matches(path, p) for p in EXCLUDED_PATHS):
        return "excluded"
    return "unclassified"


def _walk_fields(
    obj: Any, path: tuple[str, ...], rel_file: str, violations: list[str]
) -> None:
    if isinstance(obj, dict):
        if path and path[-1] == "ordering" and isinstance(obj.get("mode"), str):
            mode_value = obj["mode"]
            if not _REGISTER_GRAMMAR.match(mode_value):
                violations.append(
                    f"{rel_file}: operational-register field "
                    f"'{'.'.join(path)}.mode' = {mode_value!r} does not match "
                    f"the Operational grammar {_REGISTER_GRAMMAR.pattern}"
                )
        for key, value in obj.items():
            new_path = (*path, key)
            if key in WATCHED_FIELD_NAMES and isinstance(value, str):
                classification = _classify_path(new_path)
                if classification == "governed":
                    if not _REGISTER_GRAMMAR.match(value):
                        violations.append(
                            f"{rel_file}: operational-register field "
                            f"'{'.'.join(new_path)}' = {value!r} does not "
                            f"match the Operational grammar "
                            f"{_REGISTER_GRAMMAR.pattern}"
                        )
                elif classification == "unclassified":
                    violations.append(
                        f"{rel_file}: unclassified occurrence of field "
                        f"'{'.'.join(new_path)}' = {value!r} -- add to "
                        "GOVERNED_PATHS or EXCLUDED_PATHS in "
                        "vocabulary_register_validator.py"
                    )
            _walk_fields(value, new_path, rel_file, violations)
    elif isinstance(obj, list):
        for item in obj:
            _walk_fields(item, (*path, "[]"), rel_file, violations)


# ID: 9c4e7b2a-5f1d-4c68-8a3e-2b6d9f4c1a7e
def check_register_casing(intent_root: Path) -> RegisterCasingReport:
    """Walk intent_root and return every operational-register casing violation.

    Pure function: no raising, no logging. Callers decide what a non-empty
    report means (IntentRepository.__init__ raises; artifact_gate reports a
    finding).
    """
    violations: list[str] = []

    for pattern in ("*.yaml", "*.json"):
        for file_path in sorted(intent_root.rglob(pattern)):
            rel_posix = file_path.relative_to(intent_root).as_posix()
            if any(rel_posix.startswith(prefix) for prefix in _SCAN_EXCLUDE_PREFIXES):
                continue
            try:
                text = file_path.read_text(encoding="utf-8")
                data = yaml.safe_load(text) if pattern == "*.yaml" else json.loads(text)
            except (yaml.YAMLError, json.JSONDecodeError, OSError):
                continue
            rel_file = str(Path(".intent") / file_path.relative_to(intent_root))
            _walk_fields(data, (), rel_file, violations)

    enums_path = intent_root / _ENUMS_JSON_REL
    try:
        enums_data = json.loads(enums_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        violations.append(f".intent/{_ENUMS_JSON_REL}: could not read/parse: {exc}")
        enums_data = {}

    definitions = (
        enums_data.get("definitions", {}) if isinstance(enums_data, dict) else {}
    )
    for name in sorted(ENUMS_RATIFIED_NAMES):
        defn = definitions.get(name)
        if not isinstance(defn, dict):
            continue
        for value in defn.get("enum") or []:
            if isinstance(value, str) and not _REGISTER_GRAMMAR.match(value):
                violations.append(
                    f".intent/{_ENUMS_JSON_REL}: definitions.{name}.enum "
                    f"contains non-conforming value {value!r} (must match "
                    f"{_REGISTER_GRAMMAR.pattern})"
                )

    return RegisterCasingReport(violations=violations)


# ID: 1e5d8a3c-7b2f-4e91-9c6a-4d8b1f3e6c2a
def validate_register_casing(intent_root: Path, *, strict: bool = True) -> list[str]:
    """Fail-closed bootstrap guard. Raises GovernanceError in strict mode
    (matching validate_intent_tree's contract) when any violation is found;
    otherwise returns the violation list.
    """
    report = check_register_casing(intent_root)
    if report.violations and strict:
        msg = (
            "governance.vocabulary_registers.operational_fields_must_be_lowercase "
            "violated:\n" + "\n".join(f"- {v}" for v in report.violations)
        )
        raise GovernanceError(msg)
    return report.violations
