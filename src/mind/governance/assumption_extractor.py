# src/mind/governance/assumption_extractor.py
"""
Dynamic Assumption Extraction - Synthesizes operational defaults from constitutional policies.

CONSTITUTIONAL PRINCIPLE:
".intent/ is the ONLY paper in CORE... rest should be dynamic based on .intent/"

This module does NOT store defaults in files or database.
Instead, it queries .intent/ policies at request time and extracts guidance
using LLM-based semantic interpretation.

Why dynamic, not static?
1. Defaults are DERIVED from policies, not policies themselves
2. Policies evolve → defaults must track automatically
3. Single source of truth → policies are authoritative
4. Defensibility → every default cites specific policy clause

Architecture:
    User Request (incomplete)
        ↓
    Identify Missing Aspects
        ↓
    Query .intent/ for Relevant Policies
        ↓
    Extract Guidance via LLM (semantic interpretation)
        ↓
    Synthesize Assumption with Citation
        ↓
    Present to User for Confirmation

Authority: Policy (derives from constitutional policies)
Phase: Pre-flight (before code generation)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

from shared.logger import getLogger


if TYPE_CHECKING:
    from will.interpreters.request_interpreter import TaskStructure
    from will.orchestration.cognitive_service import CognitiveService

logger = getLogger(__name__)


# ID: 1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d
@dataclass
# ID: 8657b4ac-238c-40fc-b63e-1ad1fd07aac9
class Assumption:
    """
    Represents an operational assumption derived from constitutional policy.

    An assumption is NOT law—it's a suggested value when user intent is incomplete.
    It must ALWAYS cite the policy it was derived from.
    """

    aspect: str
    """What aspect of the request is this assumption about (e.g., 'error_handling_strategy')"""

    suggested_value: Any
    """The recommended value (e.g., {'strategy': 'exponential_backoff', 'retries': 3})"""

    cited_policy: str
    """Exact policy clause this was derived from (e.g., '.intent/policies/agents.yaml#L47')"""

    rationale: str
    """LLM explanation of why this default was chosen from the policy"""

    confidence: float
    """Confidence score 0-1 (how clearly the policy specifies this)"""

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


# ID: 2b3c4d5e-6f7a-8b9c-0d1e-2f3a4b5c6d7e
@dataclass
# ID: 3a26a683-f2b1-43c3-bc2d-f16d220c5534
class GuidanceExtraction:
    """Result of extracting guidance from a policy text."""

    value: Any
    """The extracted recommended value"""

    policy_clause: str
    """Citation to specific policy location"""

    explanation: str
    """LLM's interpretation of the policy guidance"""

    confidence: float
    """How clear/explicit the policy guidance was"""


# ID: 3c4d5e6f-7a8b-9c0d-1e2f-3a4b5c6d7e8f
class AssumptionExtractor:
    """
    Dynamically synthesizes operational defaults from constitutional policies.

    NO STATIC FILES. NO CACHED DEFAULTS.

    Every assumption is derived fresh from .intent/ policies at request time,
    ensuring perfect alignment between policy and practice.

    Example:
        User: "Create an agent that processes invoices"
        Missing: Error handling strategy

        Process:
        1. Identify gap: "error_handling_strategy"
        2. Query: .intent/policies/agent_governance.yaml
        3. Extract: "Exponential backoff with 3-5 retries for I/O operations"
        4. Cite: ".intent/policies/agent_governance.yaml, clause 4.2"
        5. Present: "I assume exponential backoff (3 retries). Proceed?"
    """

    # Common aspects that might need defaults
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
        intent_repository,
        policy_vectorizer,
        cognitive_service: CognitiveService,
    ):
        """
        Initialize extractor with constitutional infrastructure.

        Args:
            intent_repository: IntentRepository for loading policies
            policy_vectorizer: PolicyVectorizer for semantic policy search
            cognitive_service: LLM service for guidance extraction
        """
        self.intent_repo = intent_repository
        self.policy_vectorizer = policy_vectorizer
        self.llm = cognitive_service

    # ID: 4d5e6f7a-8b9c-0d1e-2f3a-4b5c6d7e8f9a
    async def extract_assumptions(
        self,
        task_structure: TaskStructure,
        matched_policies: list[dict[str, Any]],
    ) -> list[Assumption]:
        """
        Extract operational assumptions for incomplete task aspects.

        This is the main entry point for pre-flight validation.

        Args:
            task_structure: Parsed user intent
            matched_policies: Policies relevant to this task (from constitutional matcher)

        Returns:
            List of assumptions with policy citations

        Process:
        1. Identify what's missing from task_structure
        2. For each gap, query relevant policies
        3. Extract guidance using LLM semantic interpretation
        4. Return as Assumptions for user confirmation
        """
        logger.info("🔍 Extracting assumptions for task: %s", task_structure.intent)

        # Identify incomplete aspects
        incomplete_aspects = self._identify_incomplete_aspects(task_structure)

        if not incomplete_aspects:
            logger.info("✅ Task is complete, no assumptions needed")
            return []

        logger.info(
            "📋 Identified %d incomplete aspects: %s",
            len(incomplete_aspects),
            incomplete_aspects,
        )

        # Extract guidance for each missing aspect
        assumptions = []
        for aspect in incomplete_aspects:
            try:
                assumption = await self._extract_assumption_for_aspect(
                    aspect, task_structure, matched_policies
                )
                if assumption:
                    assumptions.append(assumption)
            except Exception as e:
                logger.error(
                    "Failed to extract assumption for %s: %s", aspect, e, exc_info=True
                )

        logger.info("✅ Extracted %d assumptions", len(assumptions))
        return assumptions

    # ID: 5e6f7a8b-9c0d-1e2f-3a4b-5c6d7e8f9a0b
    def _identify_incomplete_aspects(self, task_structure: TaskStructure) -> list[str]:
        """
        Identify which aspects of the task are unspecified.

        Args:
            task_structure: Parsed user intent

        Returns:
            List of aspect names that need defaults

        Strategy:
        - Check constraints list for explicit requirements
        - Infer missing aspects based on task type
        - Filter to known aspects that policies might address
        """
        missing = []

        # Map task type → expected aspects
        aspect_requirements = {
            "CREATE": [
                "error_handling_strategy",
                "logging_level",
                "validation_strictness",
            ],
            "REFACTOR": ["safety_level", "test_coverage_requirement"],
            "ANALYZE": ["analysis_depth", "output_format"],
        }

        expected_aspects = aspect_requirements.get(task_structure.task_type.value, [])

        # Check which expected aspects are not mentioned in constraints
        constraint_text = " ".join(task_structure.constraints).lower()

        for aspect in expected_aspects:
            # Simple heuristic: if aspect keyword not in constraints, it's missing
            aspect_keyword = aspect.replace("_", " ")
            if aspect_keyword not in constraint_text:
                missing.append(aspect)

        return missing

    # ID: 6f7a8b9c-0d1e-2f3a-4b5c-6d7e8f9a0b1c
    async def _extract_assumption_for_aspect(
        self,
        aspect: str,
        task_structure: TaskStructure,
        matched_policies: list[dict[str, Any]],
    ) -> Assumption | None:
        """
        Extract guidance for a single aspect from policies.

        Args:
            aspect: The missing aspect (e.g., 'error_handling_strategy')
            task_structure: User's task
            matched_policies: Relevant policies

        Returns:
            Assumption with cited policy, or None if no guidance found
        """
        logger.debug("🔎 Extracting guidance for aspect: %s", aspect)

        # Find most relevant policy for this aspect
        policy_text = await self._find_relevant_policy_text(aspect, matched_policies)

        if not policy_text:
            logger.warning("No policy guidance found for aspect: %s", aspect)
            return None

        # Use LLM to extract guidance from policy text
        guidance = await self._extract_guidance_from_policy(
            aspect, policy_text, task_structure
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

    # ID: 7a8b9c0d-1e2f-3a4b-5c6d-7e8f9a0b1c2d
    async def _find_relevant_policy_text(
        self, aspect: str, matched_policies: list[dict[str, Any]]
    ) -> str | None:
        """
        Find policy text most relevant to the given aspect.

        Args:
            aspect: Aspect needing guidance (e.g., 'error_handling_strategy')
            matched_policies: Policies from constitutional matcher

        Returns:
            Policy text content, or None if not found

        Strategy:
        - Search matched policies for aspect keywords
        - If not found, do semantic search via PolicyVectorizer
        - Load policy document and return full text
        """
        # Try semantic search for policies mentioning this aspect
        aspect_query = aspect.replace("_", " ")
        policy_hits = await self.policy_vectorizer.search_policies(
            query=aspect_query, limit=3
        )

        if not policy_hits:
            return None

        # Get the best matching policy
        best_hit = policy_hits[0]
        policy_path = best_hit.get("metadata", {}).get("source")

        if not policy_path:
            return None

        # Load the policy document
        try:
            policy_full_path = self.intent_repo.resolve_rel(policy_path)
            policy_doc = self.intent_repo.load_document(policy_full_path)

            # Return the policy as formatted text (for LLM consumption)
            return self._format_policy_for_llm(policy_doc, policy_full_path)

        except Exception as e:
            logger.error("Failed to load policy %s: %s", policy_path, e)
            return None

    # ID: 8b9c0d1e-2f3a-4b5c-6d7e-8f9a0b1c2d3e
    def _format_policy_for_llm(self, policy_doc: dict[str, Any], policy_path) -> str:
        """
        Format policy document for LLM consumption.

        Args:
            policy_doc: Parsed policy YAML/JSON
            policy_path: Path to policy file (for citation)

        Returns:
            Formatted policy text with citations
        """
        lines = [f"POLICY: {policy_path}", ""]

        # Include metadata
        metadata = policy_doc.get("metadata", {})
        if metadata:
            lines.append(f"Title: {metadata.get('title', 'Unknown')}")
            lines.append(f"Authority: {metadata.get('authority', 'Unknown')}")
            lines.append("")

        # Include rules with their statements
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

    # ID: 9c0d1e2f-3a4b-5c6d-7e8f-9a0b1c2d3e4f
    async def _extract_guidance_from_policy(
        self,
        aspect: str,
        policy_text: str,
        task_structure: TaskStructure,
    ) -> GuidanceExtraction | None:
        """
        Use LLM to extract operational guidance from policy text.

        This is where the "derivation" happens—LLM interprets policy
        and synthesizes a concrete default recommendation.

        Args:
            aspect: Aspect needing guidance
            policy_text: Full policy document text
            task_structure: User's task (for context)

        Returns:
            GuidanceExtraction with recommendation and citation
        """
        prompt = f"""You are CORE's Constitutional Interpretation Engine.

Your task: Extract operational guidance from a policy document.

CONTEXT:
The user is creating: {task_structure.intent}
Task type: {task_structure.task_type.value}

INCOMPLETE ASPECT:
The user did not specify: {aspect}

POLICY DOCUMENT:
{policy_text}

INSTRUCTIONS:
1. Find guidance in the policy relevant to "{aspect}"
2. Extract the recommended approach
3. Cite the EXACT policy clause (rule ID or line reference)
4. Rate confidence (0.0-1.0) based on how explicit the policy is

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
            # Get LLM for semantic interpretation
            interpreter = await self.llm.aget_client_for_role("Architect")

            response = await interpreter.make_request_async(
                prompt, user_id="assumption_extractor"
            )

            # Parse JSON response
            import json

            # Extract JSON from response (might be wrapped in markdown)
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]

            result = json.loads(json_str.strip())

            if not result.get("has_guidance"):
                logger.debug("Policy provides no guidance for aspect: %s", aspect)
                return None

            return GuidanceExtraction(
                value=result.get("recommended_value"),
                policy_clause=result.get("policy_clause", "unknown"),
                explanation=result.get("explanation", ""),
                confidence=result.get("confidence", 0.5),
            )

        except Exception as e:
            logger.error(
                "LLM guidance extraction failed for %s: %s", aspect, e, exc_info=True
            )
            return None
