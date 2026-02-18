# src/mind/governance/assumption_extractor.py
# ID: b5206bc1-1962-45dc-892d-e4fe16a8c311

"""
Dynamic Assumption Extraction - Synthesizes operational defaults from constitutional policies.

CONSTITUTIONAL PRINCIPLE:
".intent/ is the ONLY paper in CORE... rest should be dynamic based on .intent/"

HARDENING (V2.6):
- Decoupled from Will layer via Protocols (P2.2).
- Uses TaskStructureProtocol and CognitiveProtocol to maintain Mind-Will boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

from shared.logger import getLogger


logger = getLogger(__name__)

if TYPE_CHECKING:
    from shared.protocols import CognitiveProtocol, TaskStructureProtocol


# ID: 8657b4ac-238c-40fc-b63e-1ad1fd07aac9
@dataclass
# ID: d54d180e-d661-44fc-9332-29b1adbcb5e3
class Assumption:
    """
    Represents an operational assumption derived from constitutional policy.

    An assumption is NOT law—it's a suggested value when user intent is incomplete.
    It must ALWAYS cite the policy it was derived from.
    """

    aspect: str
    suggested_value: Any
    cited_policy: str
    rationale: str
    confidence: float

    # ID: 0baec8fb-7c64-4798-8cd6-28c9d455ea9e
    def to_dict(self) -> dict[str, Any]:
        """Serialize for logging/presentation."""
        return {
            "aspect": self.aspect,
            "suggested_value": self.suggested_value,
            "cited_policy": self.cited_policy,
            "rationale": self.rationale,
            "confidence": self.confidence,
        }


# ID: 3a26a683-f2b1-43c3-bc2d-f16d220c5534
@dataclass
# ID: 22b98dd0-0e85-462a-a3cb-467f1ae5eb9d
class GuidanceExtraction:
    """Result of extracting guidance from a policy text."""

    value: Any
    policy_clause: str
    explanation: str
    confidence: float


# ID: dd83c386-f1f5-4b3e-ad36-4bb8c93009a5
class AssumptionExtractor:
    """
    Dynamically synthesizes operational defaults from constitutional policies.

    NO STATIC FILES. NO CACHED DEFAULTS.
    """

    KNOWN_ASPECTS: ClassVar[set[str]] = {
        "error_handling_strategy",
        "retry_policy",
        "logging_level",
        "timeout_seconds",
        "network_policy",
        "data_retention_policy",
        "security_level",
        "validation_strictness",
    }

    def __init__(
        self,
        intent_repository: Any,
        policy_vectorizer: Any,
        cognitive_service: CognitiveProtocol,
    ):
        self.intent_repo = intent_repository
        self.policy_vectorizer = policy_vectorizer
        self.llm = cognitive_service

    # ID: fbfcffbb-1c8f-451f-9ab8-c2bd29f687c4
    async def extract_assumptions(
        self,
        task_structure: TaskStructureProtocol,
        matched_policies: list[dict[str, Any]],
    ) -> list[Assumption]:
        logger.info(
            "🔍 Extracting assumptions for task: %s",
            task_structure.intent,
        )

        incomplete_aspects = self._identify_incomplete_aspects(task_structure)

        if not incomplete_aspects:
            logger.info("✅ Task is complete, no assumptions needed")
            return []

        logger.info(
            "📋 Identified %d incomplete aspects: %s",
            len(incomplete_aspects),
            incomplete_aspects,
        )

        assumptions: list[Assumption] = []

        for aspect in incomplete_aspects:
            try:
                assumption = await self._extract_assumption_for_aspect(
                    aspect,
                    task_structure,
                    matched_policies,
                )
                if assumption:
                    assumptions.append(assumption)
            except Exception as e:
                logger.error(
                    "Failed to extract assumption for %s: %s",
                    aspect,
                    e,
                    exc_info=True,
                )

        logger.info("✅ Extracted %d assumptions", len(assumptions))
        return assumptions

    # ID: a0e7033d-1ce0-446a-9714-95611c1d7c0b
    def _identify_incomplete_aspects(
        self,
        task_structure: TaskStructureProtocol,
    ) -> list[str]:
        missing: list[str] = []

        aspect_requirements = {
            "CREATE": [
                "error_handling_strategy",
                "logging_level",
                "validation_strictness",
            ],
            "REFACTOR": ["safety_level", "test_coverage_requirement"],
            "ANALYZE": ["analysis_depth", "output_format"],
        }

        expected_aspects = aspect_requirements.get(
            task_structure.task_type.value,
            [],
        )

        constraint_text = " ".join(task_structure.constraints).lower()

        for aspect in expected_aspects:
            aspect_keyword = aspect.replace("_", " ")
            if aspect_keyword not in constraint_text:
                missing.append(aspect)

        return missing

    # ID: 0591a704-d0ea-4f44-87c0-60c7b8bd6b45
    async def _extract_assumption_for_aspect(
        self,
        aspect: str,
        task_structure: TaskStructureProtocol,
        matched_policies: list[dict[str, Any]],
    ) -> Assumption | None:
        logger.debug("🔎 Extracting guidance for aspect: %s", aspect)

        policy_text = await self._find_relevant_policy_text(
            aspect,
            matched_policies,
        )

        if not policy_text:
            logger.warning("No policy guidance found for aspect: %s", aspect)
            return None

        guidance = await self._extract_guidance_from_policy(
            aspect,
            policy_text,
            task_structure,
        )

        if not guidance:
            return None

        return Assumption(
            aspect=aspect,
            suggested_value=guidance.value,
            cited_policy=guidance.policy_clause,
            rationale=guidance.explanation,
            confidence=guidance.confidence,
        )

    # ID: 700dac32-7215-4e53-b743-e01c636958c3
    async def _find_relevant_policy_text(
        self,
        aspect: str,
        matched_policies: list[dict[str, Any]],
    ) -> str | None:
        aspect_query = aspect.replace("_", " ")
        policy_hits = await self.policy_vectorizer.search_policies(
            query=aspect_query,
            limit=3,
        )

        if not policy_hits:
            return None

        best_hit = policy_hits[0]
        policy_path = best_hit.get("metadata", {}).get("source")

        if not policy_path:
            return None

        try:
            policy_full_path = self.intent_repo.resolve_rel(policy_path)
            policy_doc = self.intent_repo.load_document(policy_full_path)

            return self._format_policy_for_llm(
                policy_doc,
                policy_full_path,
            )

        except Exception as e:
            logger.error(
                "Failed to load policy %s: %s",
                policy_path,
                e,
            )
            return None

    # ID: fa357f7f-5fe0-422d-9ba6-51feed6433a2
    def _format_policy_for_llm(
        self,
        policy_doc: dict[str, Any],
        policy_path: Any,
    ) -> str:
        lines = [f"POLICY: {policy_path}", ""]

        metadata = policy_doc.get("metadata", {})
        if metadata:
            lines.append(f"Title: {metadata.get('title', 'Unknown')}")
            lines.append(f"Authority: {metadata.get('authority', 'Unknown')}")
            lines.append("")

        rules = policy_doc.get("rules", [])
        for i, rule in enumerate(rules, 1):
            rule_id = rule.get("id", "unknown")
            statement = rule.get("statement", "")
            rationale = rule.get("rationale", "")

            lines.append(f"Rule {i}: {rule_id}")
            lines.append(f"  Statement: {statement}")
            if rationale:
                lines.append(f"  Rationale: {rationale}")
            lines.append("")

        return "\n".join(lines)

    # ID: 9fbb2643-0e52-4f01-ba8b-43b6a1722bd5
    async def _extract_guidance_from_policy(
        self,
        aspect: str,
        policy_text: str,
        task_structure: TaskStructureProtocol,
    ) -> GuidanceExtraction | None:
        prompt = f"""
You are CORE's Constitutional Interpretation Engine.
Your task: Extract operational guidance from a policy document.

CONTEXT:
The user is creating: {task_structure.intent}
Task type: {task_structure.task_type.value}

INCOMPLETE ASPECT:
The user did not specify: {aspect}

POLICY DOCUMENT:
{policy_text}

INSTRUCTIONS:
Find guidance in the policy relevant to "{aspect}"
Extract the recommended approach
Cite the EXACT policy clause (rule ID or line reference)
Rate confidence (0.0-1.0) based on how explicit the policy is

RESPOND IN JSON:
{{
"has_guidance": true/false,
"recommended_value": {{"strategy": "...", "retries": 3}},
"policy_clause": ".intent/policies/xyz.yaml#rule_id",
"explanation": "The policy recommends...",
"confidence": 0.85
}}

If no guidance found, set has_guidance=false.
"""

        try:
            interpreter = await self.llm.aget_client_for_role("Architect")

            response = await interpreter.make_request(
                prompt=prompt,
                system_prompt="Interpret policy defaults.",
            )

            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]

            import json

            result = json.loads(json_str.strip())

            if not result.get("has_guidance"):
                logger.debug(
                    "Policy provides no guidance for aspect: %s",
                    aspect,
                )
                return None

            return GuidanceExtraction(
                value=result.get("recommended_value"),
                policy_clause=result.get("policy_clause", "unknown"),
                explanation=result.get("explanation", ""),
                confidence=result.get("confidence", 0.5),
            )

        except Exception as e:
            logger.error(
                "LLM guidance extraction failed for %s: %s",
                aspect,
                e,
                exc_info=True,
            )
            return None
