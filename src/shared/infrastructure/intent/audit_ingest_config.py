# src/shared/infrastructure/intent/audit_ingest_config.py
"""Loader for .intent/enforcement/config/audit_ingest.yaml (ADR-098 D5).

Reads the audit-ingest pipeline constraint file and returns a frozen
dataclass. On any failure the loader falls back to safe defaults so the
daemon can boot even when the config is temporarily missing.

Pattern mirrors src/will/workers/circuit_breaker.py: one frozen dataclass,
one public load_* function, fail-open on every error path.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from shared.infrastructure.intent.intent_repository import get_intent_repository
from shared.logger import getLogger


logger = getLogger(__name__)

_CONFIG_PATH = "enforcement/config/audit_ingest.yaml"

_DEFAULT_QUALITY_INGEST_CAP = 25
_DEFAULT_ENABLED_RULES: list[str] = []


@dataclass(frozen=True)
# ID: 92896f2d-2a7d-4b6f-8f8c-cec855e93316
class AuditIngestConfig:
    """Frozen snapshot of audit_ingest.yaml.

    Attributes:
        quality_ingest_cap: Maximum findings to post per (rule, audit run).
        enabled_rules: Quality rule IDs enabled for blackboard posting.
    """

    quality_ingest_cap: int = _DEFAULT_QUALITY_INGEST_CAP
    enabled_rules: list[str] = field(default_factory=list)


# ID: fa4571c1-8332-49f4-a767-ae08abad183b
def load_audit_ingest_config() -> AuditIngestConfig:
    """Read audit_ingest.yaml and return a frozen AuditIngestConfig.

    Returns defaults on any failure — missing file, parse error, or bad
    value types. Never raises so the daemon can boot without this file.
    """
    try:
        repo = get_intent_repository()
        config_path = repo.resolve_rel(_CONFIG_PATH)
        raw = repo.load_document(config_path)
    except Exception:
        logger.warning(
            "audit_ingest_config: could not load %s — using defaults.", _CONFIG_PATH
        )
        return AuditIngestConfig()

    if not isinstance(raw, dict):
        logger.warning(
            "audit_ingest_config: %s is not a YAML mapping — using defaults.",
            _CONFIG_PATH,
        )
        return AuditIngestConfig()

    cap = raw.get("quality_ingest_cap", _DEFAULT_QUALITY_INGEST_CAP)
    try:
        cap = int(cap)
    except (TypeError, ValueError):
        logger.warning(
            "audit_ingest_config: quality_ingest_cap %r is not an int — using %d.",
            cap,
            _DEFAULT_QUALITY_INGEST_CAP,
        )
        cap = _DEFAULT_QUALITY_INGEST_CAP

    enabled_rules = raw.get("enabled_rules") or []
    if not isinstance(enabled_rules, list):
        logger.warning(
            "audit_ingest_config: enabled_rules is not a list — using empty.",
        )
        enabled_rules = []
    else:
        enabled_rules = [str(r) for r in enabled_rules if r]

    return AuditIngestConfig(quality_ingest_cap=cap, enabled_rules=enabled_rules)
