# src/shared/ai/prompt_model.py
# ID: pm-core-001

"""
PromptModel — the sole governed surface for AI invocations in CORE.

CONSTITUTIONAL AUTHORITY:
    Rule: ai.prompt.model_required
    Source: .intent/rules/ai/prompt_governance.json
    Enforcement: blocking (ast_gate)

DESIGN:
    Every AI call in CORE MUST flow through PromptModel.invoke().
    Direct calls to make_request_async() are constitutionally prohibited
    outside of this file and llm_client.py.

    A PromptModel is loaded from a directory under var/prompts/:
        var/prompts/<n>/
            model.yaml    — manifest: id, role, input contract, output contract
            system.txt    — constitutional system prompt (governs AI behaviour)
            user.txt      — user-turn template with {placeholders}
            examples.json — reference examples injected into system prompt (optional)

CONSTITUTIONAL ENVELOPE (v2):
    invoke() accepts target_files= to declare which source files the LLM
    will generate or modify. The ConstitutionalEnvelope resolves all
    applicable .intent/ rules for the touched layers and injects them
    automatically between system.txt and examples.

    The caller never specifies which rules apply — jurisdiction resolves that.
    Law outranks intelligence.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from shared.logger import getLogger


logger = getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
# ID: pm-core-002
# ID: 0e5e4048-5e19-4120-b5f5-b9b4d9838f77
class PromptModelManifest:
    """
    Parsed contents of a PromptModel's model.yaml manifest.

    Represents the complete contract for one AI invocation type.
    """

    id: str
    version: str
    role: str
    description: str = ""

    # Input contract
    required_inputs: list[str] = field(default_factory=list)
    optional_inputs: list[str] = field(default_factory=list)

    # Output contract
    output_format: str = "raw_text"
    output_max_length: int = 0  # 0 = no limit
    output_must_contain: list[str] = field(default_factory=list)
    output_must_not_contain: list[str] = field(default_factory=list)

    # Model preferences (advisory — CognitiveService resolves actual model)
    model_preference: str = ""  # e.g. "local", "deepseek", "anthropic"
    temperature: float | None = None

    success_criteria: str = ""

    # Constitutional scope hint — used when target_files not passed at invoke time.
    # Declares which layers this prompt type operates in.
    # Example model.yaml: scope: { layers: ["body", "shared"] }
    scope_layers: list[str] = field(default_factory=list)


@dataclass
# ID: pm-core-003
# ID: 6fe4bcb7-6c81-4635-95e2-fcb146a82fc2
class PromptModelArtifact:
    """
    Fully loaded PromptModel artifact, ready for invocation.

    Holds the manifest, raw text parts, and compiled examples.
    Produced by PromptModel.load() — do not construct directly.
    """

    manifest: PromptModelManifest
    system_text: str
    user_template: str
    examples: list[dict[str, Any]] = field(default_factory=list)
    _artifact_path: Path = field(default_factory=Path)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


# ID: pm-core-004
# ID: f931206c-808c-42a2-9ec3-e832636ca065
class PromptModel:
    """
    Factory and invocation surface for constitutional AI calls.

    Usage (basic):
        model = PromptModel.load("docstring_writer")
        result = await model.invoke(
            {"source_code": source},
            client=writer_client,
            user_id="docstring_healing_service",
        )

    Usage (with constitutional envelope):
        model = PromptModel.load("code_fixer")
        result = await model.invoke(
            {"source_code": source},
            client=fixer_client,
            user_id="fix_logging_service",
            target_files=["src/body/workers/doc_worker.py"],
        )
        # Constitutional rules for the 'body' layer are automatically injected.
    """

    # ID: pm-core-005
    @classmethod
    # ID: d24a1c7f-2165-4fb4-8a7f-181c0a2743f3
    def load(cls, name: str, prompts_root: Path | None = None) -> PromptModel:
        """
        Load a PromptModel artifact by name from var/prompts/.

        Args:
            name: Directory name under var/prompts/ (e.g. 'docstring_writer').
            prompts_root: Override path to var/prompts/. Defaults to
                          settings.paths.prompt(name).parent.

        Returns:
            Initialised PromptModel ready for invoke().

        Raises:
            FileNotFoundError: If model.yaml, system.txt, or user.txt are missing.
            ValueError: If model.yaml is missing required fields.
        """
        if prompts_root is None:
            from shared.config import settings

            prompts_root = settings.paths.prompt(name).parent

        artifact_dir = prompts_root / name

        # --- Load manifest ---
        manifest_path = artifact_dir / "model.yaml"
        if not manifest_path.exists():
            raise FileNotFoundError(
                f"PromptModel '{name}' missing model.yaml at {manifest_path}. "
                "See: .intent/rules/ai/prompt_governance.json [ai.prompt.model_artifact_required]"
            )
        raw_manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        manifest = cls._parse_manifest(raw_manifest, name)

        # --- Load system prompt ---
        system_path = artifact_dir / "system.txt"
        if not system_path.exists():
            raise FileNotFoundError(
                f"PromptModel '{name}' missing system.txt at {system_path}. "
                "See: .intent/rules/ai/prompt_governance.json [ai.prompt.system_prompt_required]"
            )
        system_text = system_path.read_text(encoding="utf-8").strip()
        if not system_text:
            raise ValueError(
                f"PromptModel '{name}' has empty system.txt. "
                "A system prompt is mandatory constitutional grounding."
            )

        # --- Load user template ---
        user_path = artifact_dir / "user.txt"
        if not user_path.exists():
            raise FileNotFoundError(
                f"PromptModel '{name}' missing user.txt at {user_path}."
            )
        user_template = user_path.read_text(encoding="utf-8")

        # --- Load examples (optional) ---
        examples: list[dict[str, Any]] = []
        examples_path = artifact_dir / "examples.json"
        if examples_path.exists():
            try:
                examples = json.loads(examples_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                logger.warning(
                    "PromptModel '%s': could not parse examples.json: %s", name, e
                )

        artifact = PromptModelArtifact(
            manifest=manifest,
            system_text=system_text,
            user_template=user_template,
            examples=examples,
            _artifact_path=artifact_dir,
        )

        instance = cls()
        instance._artifact = artifact
        logger.debug("PromptModel '%s' loaded from %s", name, artifact_dir)
        return instance

    # ID: pm-core-006
    # ID: 4fb47d41-9cf8-4389-b981-850edad5398a
    async def invoke(
        self,
        context: dict[str, Any],
        client: Any,
        user_id: str = "core_system",
        target_files: list[str] | None = None,
    ) -> str:
        """
        Execute the AI invocation with full constitutional governance.

        Steps:
            1. Validate all required inputs are present
            2. Build user turn from template + context
            3. Assemble system prompt: system.txt + constitutional envelope + examples
            4. Call client.make_request_with_system_async()
            5. Validate output against contract
            6. Return validated result

        Args:
            context:      Dict of {placeholder: value} matching input contract.
            client:       LLMClient instance (from CognitiveService role).
            user_id:      Audit identifier.
            target_files: File paths the LLM will generate or modify.
                          Used to resolve and inject applicable constitutional
                          rules. Falls back to manifest.scope_layers if omitted.

        Returns:
            Validated AI response string.

        Raises:
            ValueError: If required inputs are missing or output fails validation.
        """
        artifact = self._artifact
        manifest = artifact.manifest

        # 1. Validate inputs
        self._validate_inputs(context, manifest)

        # 2. Build user turn
        try:
            user_prompt = artifact.user_template.format(**context)
        except KeyError as e:
            raise ValueError(
                f"PromptModel '{manifest.id}': user.txt references placeholder {e} "
                "not provided in context."
            ) from e

        # 3. Resolve target_files for envelope
        #    Priority: explicit target_files > scope_layers hint from manifest
        resolved_files = target_files or _expand_scope_layers(manifest.scope_layers)

        # 4. Assemble system prompt: system.txt + envelope + examples
        system_prompt = self._build_system_prompt(artifact, resolved_files)

        # 5. Invoke — ONLY allowed call site for make_request_with_system_async
        logger.debug(
            "PromptModel '%s' invoking role '%s' for user '%s' (envelope layers: %s)",
            manifest.id,
            manifest.role,
            user_id,
            sorted(_resolve_layers_for_log(resolved_files)),
        )
        raw_response = await client.make_request_with_system_async(
            prompt=user_prompt,
            system_prompt=system_prompt,
            user_id=user_id,
        )

        # 6. Validate output
        validated = self._validate_output(raw_response, manifest)

        return validated

    # ---------------------------------------------------------------------------
    # Private helpers
    # ---------------------------------------------------------------------------

    # ID: pm-core-007
    @staticmethod
    def _parse_manifest(raw: dict[str, Any], name: str) -> PromptModelManifest:
        """Parse and validate raw YAML manifest dict into PromptModelManifest."""
        for required_key in ("id", "version", "role"):
            if not raw.get(required_key):
                raise ValueError(
                    f"PromptModel '{name}' model.yaml missing required field '{required_key}'."
                )

        input_block = raw.get("input", {})
        output_block = raw.get("output", {})
        scope_block = raw.get("scope", {})

        return PromptModelManifest(
            id=raw["id"],
            version=raw["version"],
            role=raw["role"],
            description=raw.get("description", ""),
            required_inputs=input_block.get("required", []),
            optional_inputs=input_block.get("optional", []),
            output_format=output_block.get("format", "raw_text"),
            output_max_length=output_block.get("max_length", 0),
            output_must_contain=output_block.get("must_contain", []),
            output_must_not_contain=output_block.get("must_not_contain", []),
            model_preference=raw.get("model", {}).get("preference", ""),
            temperature=raw.get("model", {}).get("temperature"),
            success_criteria=raw.get("success_criteria", ""),
            scope_layers=scope_block.get("layers", []),
        )

    # ID: pm-core-008
    @staticmethod
    def _validate_inputs(
        context: dict[str, Any], manifest: PromptModelManifest
    ) -> None:
        """Verify all required inputs are present in context."""
        missing = [k for k in manifest.required_inputs if k not in context]
        if missing:
            raise ValueError(
                f"PromptModel '{manifest.id}': missing required inputs: {missing}"
            )

    # ID: pm-core-009
    @staticmethod
    def _build_system_prompt(
        artifact: PromptModelArtifact,
        target_files: list[str],
    ) -> str:
        """
        Assemble the final system prompt.

        Order:
            1. system.txt   — task-specific grounding
            2. Constitutional envelope — law for the touched layers (automatic)
            3. examples.json — reference examples (optional)
        """
        from shared.ai.constitutional_envelope import ConstitutionalEnvelope

        parts = [artifact.system_text]

        # Constitutional envelope — injected between task prompt and examples
        if target_files:
            envelope = ConstitutionalEnvelope.build(target_files)
            if envelope.text:
                parts.append("")
                parts.append(envelope.text)
                logger.debug(
                    "PromptModel '%s': injected %d constitutional rules",
                    artifact.manifest.id,
                    envelope.rule_count,
                )
        else:
            logger.debug(
                "PromptModel '%s': no target_files — constitutional envelope skipped",
                artifact.manifest.id,
            )

        # Examples
        good_examples = [e for e in artifact.examples if e.get("label") == "good"]
        bad_examples = [
            e for e in artifact.examples if e.get("label", "").startswith("bad")
        ]

        if good_examples or bad_examples:
            parts.append("\n\n## Reference Examples")

        if good_examples:
            parts.append("\n### Good (follow this pattern)")
            for ex in good_examples:
                parts.append(f"\nInput:\n{ex.get('input', '')}")
                parts.append(f"\nExpected output:\n{ex.get('output', '')}")

        if bad_examples:
            parts.append("\n### Bad (avoid this pattern)")
            for ex in bad_examples:
                parts.append(f"\nLabel: {ex.get('label', '')}")
                parts.append(f"\nInput:\n{ex.get('input', '')}")
                parts.append(f"\nBad output:\n{ex.get('output', '')}")

        return "\n".join(parts)

    # ID: pm-core-010
    @staticmethod
    def _validate_output(response: str, manifest: PromptModelManifest) -> str:
        """
        Validate AI response against the output contract in model.yaml.

        Checks:
            - Response is not empty
            - max_length if configured
            - must_contain patterns
            - must_not_contain patterns

        Returns cleaned response or raises ValueError on contract violation.
        """
        cleaned = response.strip()

        if not cleaned:
            raise ValueError(
                f"PromptModel '{manifest.id}': AI returned empty response."
            )

        if manifest.output_max_length > 0 and len(cleaned) > manifest.output_max_length:
            logger.warning(
                "PromptModel '%s': response length %d exceeds max_length %d — truncating.",
                manifest.id,
                len(cleaned),
                manifest.output_max_length,
            )
            cleaned = cleaned[: manifest.output_max_length]

        for pattern in manifest.output_must_contain:
            if pattern not in cleaned:
                raise ValueError(
                    f"PromptModel '{manifest.id}': output missing required pattern '{pattern}'. "
                    f"Success criteria: {manifest.success_criteria}"
                )

        for pattern in manifest.output_must_not_contain:
            if pattern in cleaned:
                logger.warning(
                    "PromptModel '%s': output contains forbidden pattern '%s' — check AI behaviour.",
                    manifest.id,
                    pattern,
                )

        return cleaned


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _expand_scope_layers(scope_layers: list[str]) -> list[str]:
    """
    Convert manifest scope_layers hints into pseudo file paths so the envelope
    resolver can determine jurisdiction without explicit target_files.

    Example: ["body", "shared"] → ["src/body/_scope_hint", "src/shared/_scope_hint"]
    """
    if not scope_layers:
        return []
    return [f"src/{layer}/_scope_hint" for layer in scope_layers]


def _resolve_layers_for_log(target_files: list[str]) -> set[str]:
    """Cheap layer resolution for debug logging only."""
    _LAYER_MAP = {
        "src/body/": "body",
        "src/will/": "will",
        "src/mind/": "mind",
        "src/shared/": "shared",
        "src/cli/": "cli",
    }
    layers: set[str] = set()
    for f in target_files:
        f_norm = f.replace("\\", "/")
        for prefix, layer in _LAYER_MAP.items():
            if f_norm.startswith(prefix):
                layers.add(layer)
                break
        else:
            layers.add("shared")
    return layers
