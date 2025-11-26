# src/will/agents/coder_agent_v1.py
"""
CoderAgentV1 - Phase 1 Enhanced Code Generation

Enhanced with semantic infrastructure:
- Policy vectorization for constitutional guidance
- Module anchors for architectural placement
- Context-aware code generation

Phase 1 Goal: 90%+ semantic placement (from 45% baseline)

Constitutional Alignment:
- reason_with_purpose: Evidence-based placement through semantic similarity
- clarity_first: Explicit architectural guidance in prompts
- safe_by_default: Constitutional compliance through policy context
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from services.clients.qdrant_client import QdrantService
from shared.logger import getLogger

from will.orchestration.cognitive_service import CognitiveService
from will.tools.architectural_context_builder import (
    ArchitecturalContext,
    ArchitecturalContextBuilder,
)
from will.tools.module_anchor_generator import ModuleAnchorGenerator
from will.tools.policy_vectorizer import PolicyVectorizer

if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext

logger = getLogger(__name__)


# ID: f0964760-03c4-4ff8-b730-683c54eb13aa
class CoderAgentV1:
    """
    Enhanced code generation agent with semantic infrastructure.

    Improvements over V0:
    - Searches constitutional policies for relevant rules
    - Uses module anchors for semantic placement
    - Builds rich architectural context for prompts
    - Calculates placement confidence scores
    """

    def __init__(
        self,
        repo_root: Path,
        cognitive_service: CognitiveService,
        qdrant_service: QdrantService,
        auditor_context: AuditorContext | None = None,
    ):
        """
        Initialize CoderAgentV1.

        Args:
            repo_root: Path to CORE repository root
            cognitive_service: Service for LLM access and embeddings
            qdrant_service: Vector database service
            auditor_context: Optional auditor for validation
        """
        self.repo_root = Path(repo_root)
        self.cognitive_service = cognitive_service
        self.qdrant_service = qdrant_service
        self.auditor_context = auditor_context

        # Initialize Phase 1 components
        self.policy_vectorizer = PolicyVectorizer(
            repo_root,
            cognitive_service,
            qdrant_service,
        )

        self.module_anchor_generator = ModuleAnchorGenerator(
            repo_root,
            cognitive_service,
            qdrant_service,
        )

        self.context_builder = ArchitecturalContextBuilder(
            self.policy_vectorizer,
            self.module_anchor_generator,
        )

        logger.info("CoderAgentV1 initialized with semantic infrastructure")

    # ID: 08c455a0-d64d-48fd-bf58-8e38a191804d
    async def generate(
        self,
        goal: str,
        target_file: str,
        symbol_name: str | None = None,
        context_hints: dict | None = None,
    ) -> str:
        """
        Generate code using semantic infrastructure.

        Enhanced pipeline:
        1. Build architectural context (policies + anchors)
        2. Generate enhanced prompt
        3. Call LLM with context-aware prompt
        4. Extract and return code

        Args:
            goal: What the code should do
            target_file: Target file path (may be adjusted by semantic placement)
            symbol_name: Optional function/class name
            context_hints: Optional additional context

        Returns:
            Generated Python code
        """
        logger.info(f"CoderAgentV1.generate() called for: {goal[:80]}...")

        # Step 1: Build architectural context
        logger.info("Building architectural context...")
        arch_context = await self.context_builder.build_context(
            goal=goal,
            target_file=target_file,
        )

        logger.info(
            f"Context: layer={arch_context.target_layer}, "
            f"confidence={arch_context.placement_confidence}, "
            f"score={arch_context.placement_score:.3f}"
        )

        # Step 2: Build enhanced prompt
        prompt = self._build_enhanced_prompt(
            goal=goal,
            arch_context=arch_context,
            symbol_name=symbol_name,
            context_hints=context_hints,
        )

        logger.debug(f"Prompt length: {len(prompt)} characters")

        # Step 3: Generate code via LLM
        logger.info("Calling LLM for code generation...")
        generated_text = await self._call_llm(prompt)

        # Step 4: Extract clean code
        code = self._extract_code(generated_text)
        logger.info(f"Generated {len(code)} characters of code")

        return code

    def _build_enhanced_prompt(
        self,
        goal: str,
        arch_context: ArchitecturalContext,
        symbol_name: str | None,
        context_hints: dict | None,
    ) -> str:
        """
        Build enhanced prompt with semantic context.

        Args:
            goal: Generation goal
            arch_context: Architectural context from Phase 1
            symbol_name: Optional symbol name
            context_hints: Optional additional hints

        Returns:
            Complete prompt with context
        """
        parts = []

        # Architectural context (NEW in V1!)
        parts.append(self.context_builder.format_for_prompt(arch_context))

        # Code generation task
        parts.append("## Task")
        parts.append("")
        parts.append(f"Generate Python code: {goal}")
        if symbol_name:
            parts.append(f"Symbol name: `{symbol_name}`")
        parts.append("")

        # Code standards (always included)
        parts.append("## Code Standards")
        parts.append("")
        parts.append("ALL generated code MUST include:")
        parts.append(
            "1. **Docstrings**: Every function/class with purpose, params, returns"
        )
        parts.append("2. **Type Hints**: All parameters and returns typed")
        parts.append("3. **Error Handling**: Proper try-except where appropriate")
        parts.append("4. **Imports**: All necessary imports at the top")
        parts.append("")

        # Additional context hints
        if context_hints:
            parts.append("## Additional Context")
            parts.append("")
            for key, value in context_hints.items():
                parts.append(f"**{key}**: {value}")
            parts.append("")

        # Output instruction
        parts.append("## Output")
        parts.append("")
        parts.append("Return ONLY the Python code.")
        parts.append("No explanations, no markdown, just clean Python code.")

        return "\n".join(parts)

    async def _call_llm(self, prompt: str) -> str:
        """
        Call LLM via CognitiveService to generate code.

        Args:
            prompt: The generation prompt

        Returns:
            Raw LLM response text

        Raises:
            Exception: If LLM call fails
        """
        try:
            # Get client for code generation role
            client = await self.cognitive_service.aget_client_for_role("Coder")

            # Generate code
            response = await client.make_request_async(
                prompt=prompt,
                user_id="coder_agent_v1",
            )

            logger.info("LLM generation successful")
            return response

        except Exception as e:
            logger.error(f"LLM generation failed: {e}", exc_info=True)
            raise

    def _extract_code(self, llm_response: str) -> str:
        """
        Extract clean Python code from LLM response.

        Handles various formats:
        - ```python code blocks
        - ``` generic code blocks
        - Plain code

        Args:
            llm_response: Raw LLM output

        Returns:
            Extracted Python code
        """
        # Try to extract from ```python block
        python_block = re.search(
            r"```python\s*\n(.*?)\n```",
            llm_response,
            re.DOTALL,
        )
        if python_block:
            return python_block.group(1).strip()

        # Try to extract from generic ``` block
        generic_block = re.search(
            r"```\s*\n(.*?)\n```",
            llm_response,
            re.DOTALL,
        )
        if generic_block:
            return generic_block.group(1).strip()

        # If no code blocks, return as-is (might be plain code)
        return llm_response.strip()
