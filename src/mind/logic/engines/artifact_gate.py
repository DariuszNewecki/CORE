# src/mind/logic/engines/artifact_gate.py

"""
Constitutional Artifact Gate — PromptModel manifest validator.

Enforces structural and abstraction-boundary rules on var/prompts/*/model.yaml
files. Every check is deterministic: no LLM, no I/O beyond reading the file
already provided by the auditor.

Rules enforced:
- ai.prompt.artifact.required_fields   — id, version, role, input.required,
                                         output.format, success_criteria
- ai.prompt.artifact.no_provider_leak  — model.preference must not name an
                                         infrastructure provider
- ai.prompt.artifact.role_abstraction  — role field must reference a cognitive
                                         role, not a product or tool name
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from shared.logger import getLogger

from .base import BaseEngine, EngineResult


logger = getLogger(__name__)

# Providers are infrastructure. They must not appear in model.yaml.
_KNOWN_PROVIDERS = {"anthropic", "openai", "deepseek", "ollama", "azure", "mistral"}

# Cognitive roles declared in .intent/. Extend as new roles are declared.
_KNOWN_ROLES = {
    "LocalCoder",
    "Architect",
    "Planner",
    "IntentTranslator",
    "DocstringWriter",
    "CapabilityTagger",
    "CodeReviewer",
    "RefactoringArchitect",
    "GPTArchitect",
    "LocalReasoner",
}

_REQUIRED_TOP_LEVEL = {"id", "version", "role", "success_criteria"}
_REQUIRED_INPUT_SUBFIELDS = {"required"}
_REQUIRED_OUTPUT_SUBFIELDS = {"format"}


# ID: artifact-gate-engine-001
# ID: 69841a82-0920-480c-94cb-d5e4b6cb50dd
class ArtifactGateEngine(BaseEngine):
    """
    Constitutional validator for PromptModel artifact manifests.

    Checks model.yaml files for structural completeness and abstraction
    boundary compliance. All checks are purely mechanical — no LLM involved.
    """

    engine_id = "artifact_gate"

    # ID: artifact-gate-engine-002
    # ID: 46226873-bc5a-4258-b3c8-476b0cfc878a
    async def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        """
        Validate a model.yaml file against constitutional artifact rules.

        Dispatches to a specific check based on params['check_type'].
        Supported check types:
          - required_fields       — structural completeness
          - no_provider_leak      — preference field abstraction boundary
          - role_abstraction      — role field must be a cognitive role

        Args:
            file_path: Absolute path to the model.yaml being audited.
            params: Rule parameters from enforcement mapping.

        Returns:
            EngineResult with violations list; ok=True means compliant.
        """
        check_type = params.get("check_type", "required_fields")

        if not file_path.exists():
            return EngineResult(
                ok=False,
                message=f"Artifact file not found: {file_path}",
                violations=[f"Missing file: {file_path}"],
                engine_id=self.engine_id,
            )

        try:
            raw = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            return EngineResult(
                ok=False,
                message=f"Cannot parse model.yaml: {exc}",
                violations=[f"YAML parse error in {file_path}: {exc}"],
                engine_id=self.engine_id,
            )

        if check_type == "required_fields":
            return self._check_required_fields(file_path, raw)
        if check_type == "no_provider_leak":
            return self._check_no_provider_leak(file_path, raw)
        if check_type == "role_abstraction":
            return self._check_role_abstraction(file_path, raw)

        return EngineResult(
            ok=False,
            message=f"Unknown artifact_gate check_type: {check_type}",
            violations=[f"Configuration error: unknown check_type '{check_type}'"],
            engine_id=self.engine_id,
        )

    # -------------------------------------------------------------------------
    # Checks
    # -------------------------------------------------------------------------

    # ID: artifact-gate-engine-003
    def _check_required_fields(
        self, file_path: Path, manifest: dict[str, Any]
    ) -> EngineResult:
        """
        Verify all mandatory top-level and nested fields are present and
        non-empty in a model.yaml manifest.
        """
        violations: list[str] = []

        for field in _REQUIRED_TOP_LEVEL:
            if not manifest.get(field):
                violations.append(f"Missing or empty required field: '{field}'")

        input_block = manifest.get("input", {})
        if not isinstance(input_block, dict):
            violations.append("'input' must be a mapping")
        else:
            for sub in _REQUIRED_INPUT_SUBFIELDS:
                if sub not in input_block:
                    violations.append(f"Missing required field: 'input.{sub}'")

        output_block = manifest.get("output", {})
        if not isinstance(output_block, dict):
            violations.append("'output' must be a mapping")
        else:
            for sub in _REQUIRED_OUTPUT_SUBFIELDS:
                if sub not in output_block:
                    violations.append(f"Missing required field: 'output.{sub}'")

        return self._result(file_path, violations, "required_fields")

    # ID: artifact-gate-engine-004
    def _check_no_provider_leak(
        self, file_path: Path, manifest: dict[str, Any]
    ) -> EngineResult:
        """
        Ensure model.yaml does not reference infrastructure providers in the
        model.preference field. Preference must name a capability class
        (e.g. 'local', 'fast') or be absent — never a product name.
        """
        violations: list[str] = []

        model_block = manifest.get("model", {})
        if isinstance(model_block, dict):
            preference = str(model_block.get("preference", "")).lower().strip()
            if preference in _KNOWN_PROVIDERS:
                violations.append(
                    f"model.preference '{preference}' names an infrastructure provider. "
                    "Use a capability class (e.g. 'local', 'fast') or remove the field. "
                    "Provider routing belongs in CognitiveService role configuration, "
                    "not in a prompt artifact."
                )

        return self._result(file_path, violations, "no_provider_leak")

    # ID: artifact-gate-engine-005
    def _check_role_abstraction(
        self, file_path: Path, manifest: dict[str, Any]
    ) -> EngineResult:
        """
        Verify the role field references a declared cognitive role, not a
        product, tool, or arbitrary string.
        """
        violations: list[str] = []

        role = str(manifest.get("role", "")).strip()
        if not role:
            violations.append("'role' field is missing or empty.")
        elif role not in _KNOWN_ROLES:
            violations.append(
                f"role '{role}' is not a declared cognitive role. "
                f"Known roles: {sorted(_KNOWN_ROLES)}. "
                "If this is a new role, declare it in .intent/ first."
            )

        return self._result(file_path, violations, "role_abstraction")

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _result(
        self, file_path: Path, violations: list[str], check: str
    ) -> EngineResult:
        """Build a standardised EngineResult for an artifact_gate check."""
        if not violations:
            return EngineResult(
                ok=True,
                message=f"artifact_gate[{check}]: {file_path.name} passed.",
                violations=[],
                engine_id=self.engine_id,
            )
        return EngineResult(
            ok=False,
            message=f"artifact_gate[{check}]: {len(violations)} violation(s) in {file_path.name}.",
            violations=violations,
            engine_id=self.engine_id,
        )
