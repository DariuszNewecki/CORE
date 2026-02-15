# src/mind/governance/authority_package_builder.py
"""
Authority Package Builder - Pre-flight constitutional validation orchestrator.

CONSTITUTIONAL PRINCIPLE:
"CORE must never produce software it cannot defend."

This module implements the pre-flight enforcement gate that:
1. Parses user intent into structured task
2. Matches constitutional policies
3. Detects contradictions (FATAL - stops execution)
4. Identifies incomplete aspects
5. Extracts assumptions from policies (dynamic synthesis)
6. Presents authority package for user confirmation

Authority Package = Evidence that generation is constitutionally valid.

Flow:
    User Request
        ↓
    [GATE 1] Parse Intent → TaskStructure
        ↓
    [GATE 2] Match Policies → Relevant constitutional rules
        ↓
    [GATE 3] Detect Contradictions → STOP if found
        ↓
    [GATE 4] Extract Assumptions → Dynamic defaults from policies
        ↓
    [GATE 5] Build Authority Package → Complete constitutional context
        ↓
    User Confirmation → Approve or reject
        ↓
    Code Generation (with authority)

Authority: Policy (constitutional enforcement)
Phase: Pre-flight (before code generation)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from shared.logger import getLogger


if TYPE_CHECKING:
    from mind.governance.assumption_extractor import Assumption
    from will.interpreters.request_interpreter import TaskStructure

logger = getLogger(__name__)


# ID: 389ab748-8667-484e-8bab-72eb9d223547
@dataclass
# ID: d9b1775a-7f7f-443c-9570-41df4c3be408
class PolicyMatch:
    """A constitutional policy matched to user intent."""

    policy_id: str
    """Policy identifier (e.g., 'agent_governance')"""

    rule_id: str
    """Specific rule within policy (e.g., 'autonomy.correction.mandatory')"""

    statement: str
    """Rule statement text"""

    authority: str
    """Authority level (meta, constitution, policy, code)"""

    enforcement: str
    """Enforcement type (blocking, reporting, advisory)"""

    relevance_score: float
    """Semantic similarity to user intent (0.0-1.0)"""


# ID: 5e63beb8-8b3f-4dae-a97f-98a7ddd650e7
@dataclass
# ID: f6f2803a-debd-4f41-b227-03dd7f122d4b
class ConstitutionalContradiction:
    """A detected contradiction between policies."""

    rule1_id: str
    rule2_id: str
    pattern: str
    """What they both try to govern"""

    conflict_description: str
    """How they contradict"""

    resolution_required: str
    """What user must decide"""


# ID: 73a10fe0-8c31-4fa3-9272-ac486449bbaf
@dataclass
# ID: 9e6b554b-598c-4fca-b638-325ee34c4391
class AuthorityPackage:
    """
    Complete constitutional context for code generation.

    This package serves as EVIDENCE that generation is constitutionally valid.
    Every field must be populated or explicitly marked as N/A.

    Generation cannot proceed if:
    - contradictions exist (user must resolve)
    - assumptions not confirmed (user must approve)
    """

    task_structure: TaskStructure
    """Parsed user intent"""

    matched_policies: list[PolicyMatch] = field(default_factory=list)
    """Constitutional policies governing this task"""

    contradictions: list[ConstitutionalContradiction] = field(default_factory=list)
    """Policy conflicts requiring resolution"""

    assumptions: list[Assumption] = field(default_factory=list)
    """Operational defaults derived from policies"""

    user_confirmed: bool = False
    """User has reviewed and approved this package"""

    constitutional_constraints: list[str] = field(default_factory=list)
    """Hard constraints extracted from policies (e.g., 'no network access', 'requires user confirmation')"""

    refusal_reason: str | None = None
    """If generation must be refused, why (e.g., 'contradictory requirements')"""

    # ID: 0b5d92b0-0fdc-4cf7-9c9b-7d36578fc296
    def is_valid_for_generation(self) -> bool:
        """
        Check if this package authorizes code generation.

        Returns:
            True if generation can proceed, False otherwise

        Blocking conditions:
        - Contradictions exist (user must resolve first)
        - Refusal reason set (constitutional violation)
        - User has not confirmed assumptions
        """
        if self.contradictions:
            return False
        if self.refusal_reason:
            return False
        if self.assumptions and not self.user_confirmed:
            return False
        return True

    # ID: e344f0b0-a9db-4f0b-8baa-95689abf0237
    def to_dict(self) -> dict[str, Any]:
        """Serialize for logging/storage."""
        return {
            "task_type": self.task_structure.task_type.value,
            "intent": self.task_structure.intent,
            "matched_policies": len(self.matched_policies),
            "contradictions": len(self.contradictions),
            "assumptions": len(self.assumptions),
            "user_confirmed": self.user_confirmed,
            "constitutional_constraints": self.constitutional_constraints,
            "refusal_reason": self.refusal_reason,
            "valid_for_generation": self.is_valid_for_generation(),
        }


# ID: 8330bceb-2e78-47de-98bd-07fb61573ca3
class AuthorityPackageBuilder:
    """
    Orchestrates pre-flight constitutional validation.

    This is the main entry point for constitutional enforcement BEFORE code generation.
    It coordinates all the validation gates and produces an AuthorityPackage that
    either authorizes generation or explains why it must be refused.

    Example usage:
        builder = AuthorityPackageBuilder(...)

        # Build authority package from user request
        package = await builder.build_from_request("Create an agent that monitors logs")

        # Check if generation is authorized
        if package.is_valid_for_generation():
            # Proceed with code generation
            generated_code = await coder.generate(package)
        else:
            # Refuse and explain why
            print(f"Cannot proceed: {package.refusal_reason}")
    """

    def __init__(
        self,
        request_interpreter,
        intent_repository,
        policy_vectorizer,
        assumption_extractor,
        rule_conflict_detector,
    ):
        """
        Initialize builder with constitutional infrastructure.

        Args:
            request_interpreter: RequestInterpreter for parsing user intent
            intent_repository: IntentRepository for loading policies
            policy_vectorizer: PolicyVectorizer for semantic policy search
            assumption_extractor: AssumptionExtractor for dynamic defaults
            rule_conflict_detector: RuleConflictDetector for contradiction detection
        """
        self.interpreter = request_interpreter
        self.intent_repo = intent_repository
        self.policy_vectorizer = policy_vectorizer
        self.assumption_extractor = assumption_extractor
        self.conflict_detector = rule_conflict_detector

    # ID: 13a165f2-a7dd-41e1-b5f0-6197bd25f49c
    async def build_from_request(self, user_request: str) -> AuthorityPackage:
        """
        Build complete authority package from user request.

        This is the main orchestration method that runs all validation gates.

        Args:
            user_request: Natural language user request

        Returns:
            AuthorityPackage ready for user review

        Process:
        1. Parse intent (GATE 1)
        2. Match policies (GATE 2)
        3. Detect contradictions (GATE 3)
        4. Extract assumptions (GATE 4)
        5. Build package (GATE 5)
        """
        logger.info("🔐 Building authority package for request: %s", user_request[:50])

        # GATE 1: Parse Intent
        task_structure = await self._parse_intent(user_request)
        logger.info(
            "✅ Intent parsed: %s → %s",
            task_structure.task_type.value,
            task_structure.intent,
        )

        # GATE 2: Match Constitutional Policies
        matched_policies = await self._match_policies(task_structure)
        logger.info("✅ Matched %d constitutional policies", len(matched_policies))

        # GATE 3: Detect Contradictions
        contradictions = await self._detect_contradictions(matched_policies)
        if contradictions:
            logger.warning(
                "⚠️  Detected %d constitutional contradictions", len(contradictions)
            )
            return AuthorityPackage(
                task_structure=task_structure,
                matched_policies=matched_policies,
                contradictions=contradictions,
                refusal_reason=f"Constitutional contradictions detected: {len(contradictions)} conflicts require resolution",
            )

        logger.info("✅ No contradictions detected")

        # GATE 4: Extract Assumptions
        assumptions = await self._extract_assumptions(task_structure, matched_policies)
        logger.info("✅ Extracted %d assumptions from policies", len(assumptions))

        # GATE 5: Build Authority Package
        package = AuthorityPackage(
            task_structure=task_structure,
            matched_policies=matched_policies,
            contradictions=contradictions,
            assumptions=assumptions,
            constitutional_constraints=self._extract_constraints(matched_policies),
        )

        logger.info("✅ Authority package complete: %s", package.to_dict())
        return package

    # ID: 034eed3d-dfcf-40cc-9ca6-35cc26c6b674
    async def _parse_intent(self, user_request: str) -> TaskStructure:
        """
        Parse user request into structured intent.

        Args:
            user_request: Natural language request

        Returns:
            TaskStructure with parsed intent
        """
        # Use RequestInterpreter to parse natural language
        result = await self.interpreter.execute(user_message=user_request)

        if not result.ok:
            raise ValueError(f"Intent parsing failed: {result.error}")

        task = result.data.get("task")
        if not task:
            raise ValueError("No task structure returned from interpreter")

        return task

    # ID: 26fabda6-9dc4-448b-8f3d-78ee70ca1d1d
    async def _match_policies(self, task_structure: TaskStructure) -> list[PolicyMatch]:
        """
        Find constitutional policies relevant to this task.

        Args:
            task_structure: Parsed user intent

        Returns:
            List of matched policies with relevance scores

        Strategy:
        - Semantic search via PolicyVectorizer
        - Filter to policies with authority over this task type
        - Return top N most relevant
        """
        # Build search query from task structure
        query_parts = [
            task_structure.task_type.value,
            task_structure.intent,
        ]
        if task_structure.targets:
            query_parts.extend(task_structure.targets)
        query = " ".join(query_parts)

        # Semantic search for relevant policies
        policy_hits = await self.policy_vectorizer.search_policies(
            query=query, limit=10
        )

        # Convert to PolicyMatch objects
        matches = []
        for hit in policy_hits:
            payload = hit.get("payload", {})
            metadata = payload.get("metadata", {})

            match = PolicyMatch(
                policy_id=metadata.get("policy_id", "unknown"),
                rule_id=metadata.get("rule_id", "unknown"),
                statement=payload.get("text", ""),
                authority=metadata.get("authority", "policy"),
                enforcement=metadata.get("enforcement", "reporting"),
                relevance_score=hit.get("score", 0.0),
            )
            matches.append(match)

        return matches

    # ID: 3999993f-3320-41c7-a644-b4e0dce4ae74
    async def _detect_contradictions(
        self, matched_policies: list[PolicyMatch]
    ) -> list[ConstitutionalContradiction]:
        """
        Detect contradictions between matched policies.

        Args:
            matched_policies: Policies matched to user intent

        Returns:
            List of contradictions, empty if none found

        Strategy:
        - Convert PolicyMatches to PolicyRules
        - Use RuleConflictDetector
        - Format results as ConstitutionalContradiction
        """
        # Convert to format RuleConflictDetector expects
        from mind.governance.policy_rule import PolicyRule

        rules = [
            PolicyRule(
                name=match.rule_id,
                pattern=match.policy_id,  # Simplified for now
                action="block" if match.enforcement == "blocking" else "allow",
                authority=match.authority,
                source_policy=match.policy_id,
            )
            for match in matched_policies
        ]

        # Detect conflicts
        conflicts = self.conflict_detector.detect_conflicts(rules)

        # Convert to ConstitutionalContradiction objects
        contradictions = []
        for conflict in conflicts:
            contradictions.append(
                ConstitutionalContradiction(
                    rule1_id=conflict["rule1"],
                    rule2_id=conflict["rule2"],
                    pattern=conflict["pattern"],
                    conflict_description=f"Rule '{conflict['rule1']}' ({conflict['action1']}) conflicts with '{conflict['rule2']}' ({conflict['action2']})",
                    resolution_required="User must explicitly choose which rule takes precedence or modify requirements to avoid conflict",
                )
            )

        return contradictions

    # ID: c9d0e1f2-a3b4-5c6d-7e8f-9a0b1c2d3e4f
    async def _extract_assumptions(
        self, task_structure: TaskStructure, matched_policies: list[PolicyMatch]
    ) -> list[Assumption]:
        """
        Extract operational assumptions for incomplete aspects.

        Args:
            task_structure: User's task
            matched_policies: Relevant policies

        Returns:
            List of assumptions with policy citations
        """
        # Convert PolicyMatches to format AssumptionExtractor expects
        policy_dicts = [
            {
                "policy_id": match.policy_id,
                "rule_id": match.rule_id,
                "statement": match.statement,
                "metadata": {
                    "authority": match.authority,
                    "enforcement": match.enforcement,
                },
            }
            for match in matched_policies
        ]

        # Extract assumptions dynamically from policies
        assumptions = await self.assumption_extractor.extract_assumptions(
            task_structure, policy_dicts
        )

        return assumptions

    # ID: d0e1f2a3-b4c5-6d7e-8f9a-0b1c2d3e4f5a
    def _extract_constraints(self, matched_policies: list[PolicyMatch]) -> list[str]:
        """
        Extract hard constraints from matched policies.

        Args:
            matched_policies: Policies matched to user intent

        Returns:
            List of constraint strings (e.g., 'no_network_access', 'requires_user_confirmation')

        Strategy:
        - Look for blocking-level policies
        - Extract constraint keywords from statements
        - Return as list of constraint identifiers
        """
        constraints = []

        for match in matched_policies:
            # Only blocking policies create hard constraints
            if match.enforcement != "blocking":
                continue

            # Extract constraint keywords from statement
            statement_lower = match.statement.lower()

            # Common constraint patterns
            if "no network" in statement_lower or "network access" in statement_lower:
                constraints.append("no_network_access")
            if (
                "user confirmation" in statement_lower
                or "explicit approval" in statement_lower
            ):
                constraints.append("requires_user_confirmation")
            if "no mutation" in statement_lower or "read-only" in statement_lower:
                constraints.append("read_only_operation")
            if "audit trail" in statement_lower or "must log" in statement_lower:
                constraints.append("requires_audit_logging")

        return list(set(constraints))  # Deduplicate

    # ID: e1f2a3b4-c5d6-7e8f-9a0b-1c2d3e4f5a6b
    async def confirm_authority_package(
        self, package: AuthorityPackage, user_approval: bool
    ) -> AuthorityPackage:
        """
        Record user confirmation of authority package.

        Args:
            package: Authority package to confirm
            user_approval: Whether user approves

        Returns:
            Updated package with confirmation status
        """
        package.user_confirmed = user_approval

        if not user_approval:
            package.refusal_reason = "User rejected assumptions"
            logger.info("❌ User rejected authority package")
        else:
            logger.info("✅ User confirmed authority package")

        return package
