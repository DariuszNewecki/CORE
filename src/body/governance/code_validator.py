# src/body/governance/code_validator.py
# ID: 18f27500-2fbd-42a7-9180-a71ac3da5626

"""
Code Validator - Body Layer Enforcement Service.

CONSTITUTIONAL PROMOTION (v2.6):
- Mind/Body Separation: 'Checks' moved to .intent/enforcement/mappings/.
- Rule Primacy: 'Law' moved to .intent/rules/.
- Dynamic Dispatch: Uses EnforcementMappingLoader to resolve check logic.
"""

from __future__ import annotations

import ast
from pathlib import Path

from mind.governance.enforcement_loader import EnforcementMappingLoader
from mind.governance.violation_report import ViolationReport
from mind.logic.engines.registry import EngineRegistry
from shared.logger import getLogger
from shared.models.constitutional_validation import ConstitutionalValidationResult


logger = getLogger(__name__)


# ID: ca5b215a-cc3c-4539-bd3f-89f411694441
class CodeValidator:
    """
    Body service that validates code against architectural patterns.
    Resolves enforcement strategies from the Mind's mappings.
    """

    @staticmethod
    # ID: d2605a19-d9d7-49cb-8b0d-3ce2acb85964
    async def validate_generated_code(
        code: str, pattern_id: str, target_path: str
    ) -> ConstitutionalValidationResult:
        """
        Validate generated code against its assigned architectural pattern.
        """
        violations: list[ViolationReport] = []

        # 1. Mandatory Syntax Check (Internal Body Capability)
        try:
            ast.parse(code)
        except SyntaxError as e:
            violations.append(
                ViolationReport(
                    rule_name="syntax_error",
                    path=target_path,
                    message=f"Syntax error: {e}",
                    severity="error",
                    source_policy="code_purity",
                )
            )
            return ConstitutionalValidationResult(is_valid=False, violations=violations)

        # 2. Dynamic Enforcement Resolution
        # We use the pattern_id to look up the mapped rule_id in the Mind.
        # Example: 'action_pattern' -> 'architecture.patterns.action_pattern'
        rule_id = f"architecture.patterns.{pattern_id}"

        # Initialize the Loader (Uses PathResolver internally)
        intent_root = Path(
            ".intent"
        )  # This would ideally come from PathResolver via Context
        loader = EnforcementMappingLoader(intent_root)
        strategy = loader.get_enforcement_strategy(rule_id)

        if not strategy:
            # If no mapping exists, we cannot prove legality.
            logger.warning("No enforcement strategy mapped for rule: %s", rule_id)
            return ConstitutionalValidationResult(is_valid=True, source="CodeValidator")

        # 3. Engine Dispatch
        try:
            engine_id = strategy.get("engine")
            params = strategy.get("params", {})

            engine = EngineRegistry.get(engine_id)
            # The Engine executes the derived implementation of the Law
            result = await engine.verify(Path(target_path), {**params, "code": code})

            if not result.ok:
                for msg in result.violations:
                    violations.append(
                        ViolationReport(
                            rule_name=rule_id,
                            path=target_path,
                            message=msg,
                            severity="error",
                            source_policy="enforcement_mappings",
                        )
                    )

        except Exception as e:
            logger.error("Pattern validation engine failure: %s", e)
            violations.append(
                ViolationReport(
                    rule_name="validator_failure",
                    path=target_path,
                    message=f"Enforcement Engine {strategy.get('engine')} failed.",
                    severity="error",
                    source_policy="system_integrity",
                )
            )

        return ConstitutionalValidationResult(
            is_valid=len(violations) == 0, violations=violations, source="CodeValidator"
        )
