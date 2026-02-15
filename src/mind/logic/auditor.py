# src/mind/logic/auditor.py
"""
Engine-based constitutional auditor.

Executes constitutional rules against files using registered engines.
Supports both file-level engines (ast_gate, regex_gate) and context-level
engines (knowledge_gate, workflow_gate).
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from mind.logic.engines.registry import EngineRegistry
from shared.infrastructure.intent.intent_connector import IntentConnector
from shared.logger import getLogger


logger = getLogger(__name__)

# CONSTITUTIONAL FIX: Engines that operate on the full system state (Mind)
# or process results (Workflows) rather than individual file content.
# These are skipped during single-file audits to prevent out-of-context errors.
CONTEXT_LEVEL_ENGINES = {"knowledge_gate", "workflow_gate", "action_gate"}


# ID: 18ce86c1-bc21-4290-9379-e3bedcbafc9a
class ConstitutionalAuditor:
    """
    Engine-based constitutional auditor.

    Executes applicable constitutional rules against a single target file by:
    1) querying IntentConnector for applicable rules
    2) dispatching each rule to its declared verification engine

    Supports both file-level and context-level engines.
    """

    def __init__(self, *, connector: IntentConnector | None = None) -> None:
        self.connector = connector or IntentConnector()
        self._registry = EngineRegistry

    # ID: fd9b1360-18db-432d-bd13-13f158dfa1a4
    def audit_file(self, file_path: Path) -> list[dict[str, Any]]:
        """
        Run all applicable constitutional checks against a single file.

        Note: Context-level engines are skipped silently during file-level
        audits as they require the full AuditorContext/Database state.
        """
        target = Path(file_path)
        if not target.exists():
            logger.error("File not found: %s", target)
            return []

        applicable_rules = self.connector.get_applicable_rules(target)
        findings: list[dict[str, Any]] = []

        for rule in applicable_rules:
            rule_id = (rule.get("id") or rule.get("uid") or "").strip()
            check_meta = rule.get("check")

            if not isinstance(check_meta, dict):
                continue

            engine_id = (check_meta.get("engine") or "").strip()
            params = check_meta.get("params", {})

            if not engine_id:
                continue

            if not isinstance(params, dict):
                params = {}

            # CONSTITUTIONAL FIX: Skip context-level engines during file-level audits.
            # This prevents reporting "Requires context" as an audit failure for
            # specific files, as these rules are meant for project-wide audits.
            if engine_id in CONTEXT_LEVEL_ENGINES:
                logger.debug(
                    "Skipping context-level engine '%s' for rule '%s' during file-level audit of %s",
                    engine_id,
                    rule_id,
                    file_path.name,
                )
                continue

            try:
                engine = self._registry.get(engine_id)
                result = engine.verify(target, params)

                if not getattr(result, "ok", False):
                    findings.append(
                        {
                            "rule_id": rule_id or "<unknown>",
                            "statement": rule.get("statement"),
                            "severity": rule.get("enforcement", "error"),
                            "engine": engine_id,
                            "message": getattr(result, "message", "Violation"),
                            "violations": getattr(result, "violations", []) or [],
                            "rationale": rule.get("rationale"),
                        }
                    )
            except Exception as e:
                logger.error(
                    "Engine failure [%s] on rule [%s]: %s", engine_id, rule_id, e
                )
                findings.append(
                    {
                        "rule_id": rule_id or "<unknown>",
                        "statement": rule.get("statement"),
                        "severity": "error",
                        "engine": engine_id,
                        "message": f"Engine failure: {e}",
                        "violations": [],
                        "rationale": rule.get("rationale"),
                    }
                )

        # Sort by severity (blocking first) then alphabetically by ID
        findings.sort(key=lambda f: (str(f.get("severity")), str(f.get("rule_id"))))
        return findings


# ID: f49bc20b-b19d-40ac-942f-2ae284d0a49b
def main(argv: list[str] | None = None) -> int:
    """
    CLI entrypoint for individual file auditing.
    """
    parser = argparse.ArgumentParser(prog="core-audit-file")
    parser.add_argument("file_path", type=str, help="Path to the file to audit")
    args = parser.parse_args(argv)

    target = Path(args.file_path)
    auditor = ConstitutionalAuditor()

    logger.info("Auditing file: %s", target)
    results = auditor.audit_file(target)

    if not results:
        logger.info("✅ COMPLIANT: No constitutional violations found.")
        return 0

    logger.info("❌ NON-COMPLIANT: Found %s violations.\n", len(results))
    for res in results:
        rid = res.get("rule_id", "<unknown>")
        sev = str(res.get("severity", "error")).upper()
        msg = res.get("message", "")
        violations = res.get("violations") or []

        logger.info("[%s] (%s)", rid, sev)
        logger.info("  Issue:     %s", msg)
        for v in violations:
            logger.info("    - %s", v)
        logger.info("-" * 40)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
