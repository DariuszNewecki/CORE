# src/shared/models/prompt_model.py
# ID: pm-core-001

"""
PromptModel — the sole governed surface for AI invocations in CORE.

CONSTITUTIONAL AUTHORITY:
    Rule:   ai.prompt.model_required
    Source: .intent/rules/ai/prompt_governance.json
    Effect: blocking — all direct LLM calls are a constitutional violation.

DESIGN:
    Every AI call in CORE MUST flow through PromptModel.invoke().
    Workers never hardcode a cognitive role. They read it from the manifest:

        pm = PromptModel.load("docstring_writer")
        client = await cognitive_service.aget_client_for_role(pm.manifest.role)
        result = await pm.invoke(client, {"source_code": src})

ARTIFACT LAYOUT (var/prompts/<name>/):
    model.yaml   — manifest: id, role, model config, output constraints
    system.txt   — constitutional system prompt (verbatim, no templating)
    user.txt     — user-turn template with {placeholder} variables

PRINCIPLES:
    - PromptModel.load() must NEVER be called at module level.
    - Cognitive role must be read from manifest.role, never hardcoded.
    - max_tokens flows from model.yaml → manifest → provider API.
    - Output validation is mechanical, not social.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import yaml

from shared.config import settings
from shared.logger import getLogger


logger = getLogger(__name__)

_DEFAULT_MAX_TOKENS = 4096
_DEFAULT_MAX_LENGTH = 4096


# ID: pm-manifest-001
@dataclasses.dataclass(frozen=True)
# ID: 11108bdb-2bc2-4fc2-8c6a-d6c7d0a628d5
class PromptModelManifest:
    """
    Immutable snapshot of a PromptModel artifact's model.yaml configuration.

    Populated by PromptModel.load(); never constructed directly by callers.
    """

    id: str
    role: str
    model_max_tokens: int
    output_max_length: int
    output_must_contain: list[str]
    output_must_not_contain: list[str]
    success_criteria: str

    @classmethod
    # ID: 8596b7ed-d827-4c96-936e-9a6399a8fda8
    def from_yaml(cls, data: dict) -> PromptModelManifest:
        """
        Parses a model.yaml dict into a PromptModelManifest.

        Constitutional defaults apply when optional fields are absent —
        the manifest is always fully populated regardless of what the YAML omits.
        """
        model_block = data.get("model", {})
        output_block = data.get("output", {})

        return cls(
            id=data["id"],
            role=data["role"],
            model_max_tokens=int(model_block.get("max_tokens", _DEFAULT_MAX_TOKENS)),
            output_max_length=int(output_block.get("max_length", _DEFAULT_MAX_LENGTH)),
            output_must_contain=output_block.get("must_contain", []),
            output_must_not_contain=output_block.get("must_not_contain", []),
            success_criteria=data.get("success_criteria", "").strip(),
        )


# ID: pm-core-002
# ID: c6243c0b-2e59-465c-92e0-28fa0ea3eac7
class PromptModelValidationError(Exception):
    """
    Raised when PromptModel output fails constitutional validation.

    Callers should treat this as a soft failure — log it, skip the symbol,
    and continue. It is NOT a system error; it means the AI response did not
    meet the artifact's declared output contract.
    """


# ID: pm-core-003
# ID: bf8abbad-432d-48c0-93b6-a5f8aee3c30e
class PromptModel:
    """
    Governed wrapper for a single PromptModel artifact.

    A PromptModel is the combination of:
    - A constitutional manifest (model.yaml)
    - A system prompt (system.txt)
    - A user-turn template (user.txt)

    It enforces that AI responses conform to declared output constraints
    before returning them to the caller.
    """

    def __init__(
        self,
        manifest: PromptModelManifest,
        system_prompt: str,
        user_template: str,
    ) -> None:
        self.manifest = manifest
        self._system_prompt = system_prompt
        self._user_template = user_template

    @classmethod
    # ID: a6fdf7fe-5563-4cfd-a2aa-a3d8d1e9304e
    def load(cls, name: str) -> PromptModel:
        """
        Loads a PromptModel artifact from var/prompts/<name>/.

        This is the only constructor. Must not be called at module level —
        settings may not be fully initialised at import time.

        Args:
            name: Artifact directory name (e.g. "docstring_writer").

        Returns:
            Fully loaded PromptModel ready for invocation.

        Raises:
            FileNotFoundError: If the artifact directory or any required file
                               is missing. Missing files are a constitutional
                               violation of the artifact contract.
        """
        artifact_dir: Path = settings.paths.prompts_dir / name

        model_yaml_path = artifact_dir / "model.yaml"
        system_txt_path = artifact_dir / "system.txt"
        user_txt_path = artifact_dir / "user.txt"

        for path in (model_yaml_path, system_txt_path, user_txt_path):
            if not path.exists():
                raise FileNotFoundError(
                    f"PromptModel artifact '{name}' is missing required file: {path}"
                )

        raw = yaml.safe_load(model_yaml_path.read_text(encoding="utf-8"))
        manifest = PromptModelManifest.from_yaml(raw)
        system_prompt = system_txt_path.read_text(encoding="utf-8")
        user_template = user_txt_path.read_text(encoding="utf-8")

        logger.debug(
            "PromptModel loaded: id=%s role=%s max_tokens=%s",
            manifest.id,
            manifest.role,
            manifest.model_max_tokens,
        )
        return cls(manifest, system_prompt, user_template)

    # ID: b0792772-4524-4133-bf88-cede80f0a207
    async def invoke(self, client: object, inputs: dict) -> str:
        """
        Renders the user template, calls the AI, and validates the response.

        Args:
            client: An LLMClient instance resolved for this manifest's role.
                    Workers must obtain this via:
                        cognitive_service.aget_client_for_role(pm.manifest.role)
            inputs: Template variables used to fill {placeholder} slots in user.txt.
                    Extra keys are ignored; missing keys raise KeyError.

        Returns:
            Validated AI response string.

        Raises:
            PromptModelValidationError: If the response fails output constraints.
            KeyError: If a required template variable is missing from inputs.
        """
        prompt = self._user_template.format(**inputs)

        raw: str = await client.make_request_with_system_async(
            prompt=prompt,
            system_prompt=self._system_prompt,
            max_tokens=self.manifest.model_max_tokens,
        )

        return self._validate(raw)

    def _validate(self, response: str) -> str:
        """
        Applies mechanical output validation against the manifest's constraints.

        Truncation is applied for max_length before pattern checks, so that
        an over-long response does not silently hide a must_contain failure.

        Args:
            response: Raw string returned by the LLM provider.

        Returns:
            Validated (and possibly truncated) response.

        Raises:
            PromptModelValidationError: If must_contain or must_not_contain
                                        checks fail after truncation.
        """
        result = response

        if len(result) > self.manifest.output_max_length:
            logger.warning(
                "PromptModel '%s': response length %s exceeds max_length %s — truncating.",
                self.manifest.id,
                len(result),
                self.manifest.output_max_length,
            )
            result = result[: self.manifest.output_max_length]

        for pattern in self.manifest.output_must_contain:
            if pattern not in result:
                criteria = self.manifest.success_criteria or "(no criteria defined)"
                raise PromptModelValidationError(
                    f"PromptModel '{self.manifest.id}': output missing required pattern "
                    f"{pattern!r}. Success criteria: {criteria}"
                )

        for pattern in self.manifest.output_must_not_contain:
            if pattern in result:
                raise PromptModelValidationError(
                    f"PromptModel '{self.manifest.id}': output contains forbidden pattern "
                    f"{pattern!r}."
                )

        return result
