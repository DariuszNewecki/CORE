# src/mind/logic/auditor.py
"""
Engine-based Constitutional Auditor (rule -> engine dispatch).

This auditor implements the newer CORE enforcement pattern:
- Constitutional rules live in .intent (resolved via IntentConnector)
- Each rule declares an engine + params
- Engines are resolved via EngineRegistry and invoked deterministically

This module intentionally does NOT configure logging or sys.path.
It relies on CORE's logging and packaging/import conventions.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

# NOTE:
# If these imports fail in your environment, adjust ONLY these two lines to match
# your actual package layout.
from mind.logic.engines.registry import EngineRegistry
from shared.infrastructure.intent.intent_connector import IntentConnector
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: ca5b4a38-95ff-41cf-8c50-62e20aee39da
class ConstitutionalAuditor:
    """
    Engine-based constitutional auditor.

    Executes applicable constitutional rules against a single target file by:
    1) querying IntentConnector for applicable rules
    2) dispatching each rule to its declared verification engine
    """

    def __init__(self, *, connector: IntentConnector | None = None) -> None:
        self.connector = connector or IntentConnector()
        # EngineRegistry uses classmethods; instantiating is harmless but unnecessary.
        self._registry = EngineRegistry

    # ID: 4fa6ac93-791b-4e87-aea9-c6448c72a6c4
    def audit_file(self, file_path: Path) -> list[dict[str, Any]]:
        """
        Run all applicable constitutional checks against a single file.

        Returns:
            List of findings (dicts). Empty list means compliant.
        """
        target = Path(file_path)

        if not target.exists():
            logger.error("File not found: %s", target)
            return []

        # Ask governance layer which rules apply to this file
        applicable_rules = self.connector.get_applicable_rules(target)
        findings: list[dict[str, Any]] = []

        for rule in applicable_rules:
            rule_id = (rule.get("id") or rule.get("uid") or "").strip()
            check_meta = rule.get("check")

            # Only engine-based checks are supported in this auditor.
            if not isinstance(check_meta, dict):
                continue

            engine_id = (check_meta.get("engine") or "").strip()
            params = check_meta.get("params", {})

            if not engine_id:
                continue
            if not isinstance(params, dict):
                params = {}

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
                # Engine failure should be visible but must not crash whole audit run
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

        # Deterministic ordering (helps testing and reproducibility)
        findings.sort(key=lambda f: (str(f.get("severity")), str(f.get("rule_id"))))
        return findings


# ID: 9d5fa0f1-7d43-46b4-8f51-d729fd09d71c
def main(argv: list[str] | None = None) -> int:
    """
    CLI entrypoint for individual file auditing.

    Usage:
        poetry run python -m mind.logic.auditor <file_path>
    """
    parser = argparse.ArgumentParser(prog="core-audit-file")
    parser.add_argument("file_path", type=str, help="Path to the file to audit")
    args = parser.parse_args(argv)

    target = Path(args.file_path)

    auditor = ConstitutionalAuditor()
    logger.info("Auditing file: %s", target)

    results = auditor.audit_file(target)
    if not results:
        print("✅ COMPLIANT: No constitutional violations found.")
        return 0

    print(f"❌ NON-COMPLIANT: Found {len(results)} violations.\n")
    for res in results:
        rid = res.get("rule_id", "<unknown>")
        sev = str(res.get("severity", "error")).upper()
        stmt = res.get("statement", "")
        eng = res.get("engine", "")
        msg = res.get("message", "")
        violations = res.get("violations") or []

        print(f"[{rid}] ({sev})")
        if stmt:
            print(f"  Statement: {stmt}")
        if eng:
            print(f"  Engine:    {eng}")
        print(f"  Issue:     {msg}")
        for v in violations:
            print(f"    - {v}")
        print("-" * 40)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
