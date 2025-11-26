# src/will/agents/coder_agent_v0.py
"""
CoderAgentV0: Minimal code generation agent for Phase 0 validation.

This is a stripped-down version that uses existing CORE infrastructure
to validate the core capability: Can an LLM generate constitutionally-
compliant code with basic context?

Constitutional Principles:
- reason_with_purpose: Validate capability before building infrastructure
- safe_by_default: All generated code written to work/ directory first
- separation_of_concerns: Pure generation, no execution or validation

Phase 0 Strategy:
- Uses existing CognitiveService for LLM access
- Uses existing semantic search for context
- NO semantic enhancements (saving for Phase 1)
- NO policy vectorization (saving for Phase 1)
- NO architectural anchors (saving for Phase 1)

Success Criteria:
If this agent achieves ≥70% constitutional compliance with basic context,
then semantic infrastructure (Phase 1) will push it to 85%+.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shared.logger import getLogger

from will.orchestration.cognitive_service import CognitiveService

logger = getLogger(__name__)


@dataclass
# ID: ed06186c-8d23-44ca-8e08-f297c0474db1
class GenerationConstraints:
    """
    Constraints for code generation.

    Attributes:
        target_location: Where the generated code should be placed
        difficulty: Task complexity ("simple" | "medium" | "complex")
        max_tokens: Maximum tokens for generation
        temperature: LLM temperature (lower = more deterministic)
    """

    target_location: Path
    difficulty: str
    max_tokens: int = 2000
    temperature: float = 0.2  # Low temp for consistency


@dataclass
# ID: 93175df8-ad46-4b78-8499-2d47ae660738
class GeneratedArtifact:
    """
    Result of code generation.

    Attributes:
        code: The generated Python code
        location: Target file path
        metadata: Additional information about generation
    """

    code: str
    location: Path
    metadata: dict[str, Any]


# ID: ad783ba9-46f9-4dc2-ad00-b183be6175cf
class CoderAgentV0:
    """
    Minimal code generation agent for Phase 0 validation.

    Responsibilities:
    - Generate Python code from high-level goals
    - Use existing context infrastructure (semantic search)
    - Follow CORE constitutional requirements
    - Return structured artifacts for validation

    Does NOT (Phase 1 features):
    - Vectorize policies for semantic search
    - Use module-level architectural context
    - Validate semantic placement
    - Execute or commit generated code

    Usage:
        agent = CoderAgentV0(core_context, cognitive_service)

        constraints = GenerationConstraints(
            target_location=Path("src/shared/utils/markdown.py"),
            difficulty="simple"
        )

        artifact = await agent.generate(
            goal="Create markdown header extractor",
            constraints=constraints
        )
    """

    def __init__(
        self,
        repo_root: Path,
        cognitive_service: CognitiveService,
    ):
        """
        Initialize the coder agent.

        Args:
            repo_root: Path to CORE repository root
            cognitive_service: Service for LLM access and semantic search
        """
        self.repo_root = repo_root
        self.cognitive_service = cognitive_service

        logger.info("CoderAgentV0 initialized")

    # ID: c2450292-0f77-4f9a-ac4e-68065914e53c
    async def generate(
        self,
        goal: str,
        constraints: GenerationConstraints,
    ) -> GeneratedArtifact:
        """
        Generate code for the given goal.

        Process:
        1. Gather context using existing semantic search
        2. Build generation prompt with constitutional requirements
        3. Call LLM via CognitiveService
        4. Extract and clean code from response
        5. Return artifact with metadata

        Args:
            goal: High-level description of what to generate
            constraints: Generation constraints (location, difficulty, etc.)

        Returns:
            GeneratedArtifact with code, location, and metadata

        Raises:
            Exception: If generation fails at any step
        """
        logger.info(f"Generating code for goal: {goal}")
        logger.info(f"Target location: {constraints.target_location}")
        logger.info(f"Difficulty: {constraints.difficulty}")

        # Step 1: Gather context
        context = await self._gather_context(goal, constraints)
        logger.info(
            f"Gathered context with {len(context.get('related_symbols', []))} related symbols"
        )

        # Step 2: Build prompt
        prompt = self._build_generation_prompt(goal, constraints, context)
        logger.debug(f"Generated prompt length: {len(prompt)} characters")

        # Step 3: Generate code
        generated_text = await self._call_llm(prompt, constraints)
        logger.info(f"LLM returned {len(generated_text)} characters")

        # Step 4: Extract clean code
        code = self._extract_code(generated_text)
        logger.info(f"Extracted {len(code)} characters of clean code")

        # Step 5: Build artifact
        artifact = GeneratedArtifact(
            code=code,
            location=constraints.target_location,
            metadata={
                "goal": goal,
                "difficulty": constraints.difficulty,
                "context_items": len(context.get("related_symbols", [])),
                "context_files": len(context.get("related_files", {})),
                "raw_response_length": len(generated_text),
                "extracted_code_length": len(code),
            },
        )

        logger.info(f"Generation complete for {constraints.target_location.name}")
        return artifact

    async def _gather_context(
        self,
        goal: str,
        constraints: GenerationConstraints,
    ) -> dict[str, Any]:
        """
        Gather relevant context using existing CORE services.

        Uses:
        - Semantic search to find related symbols (OPTIONAL - Phase 0 can work without it)
        - File content retrieval for related code
        - Module structure information

        Args:
            goal: The generation goal
            constraints: Generation constraints

        Returns:
            Dictionary with context information:
                - goal: The original goal
                - target_module: Parent module path
                - related_symbols: List of related symbol metadata
                - related_files: Dict of file paths to content
        """
        logger.info("Gathering context via semantic search (optional for Phase 0)")

        # Try semantic search, but don't fail if unavailable
        related_symbols = []
        related_files = {}

        try:
            search_results = await self.cognitive_service.search_capabilities(
                query=goal, limit=5
            )

            # Process search results
            for result in search_results:
                symbol_info = {
                    "name": result.get("symbol_name", "unknown"),
                    "type": result.get("symbol_type", "unknown"),
                    "file": result.get("file_path", "unknown"),
                    "docstring": result.get("intent", "")[:200],
                }
                related_symbols.append(symbol_info)

                if result.get("file_path"):
                    related_files.add(result["file_path"])

            logger.info(f"Semantic search found {len(related_symbols)} related symbols")

        except Exception as e:
            # Semantic search failed - this is OK for Phase 0
            # We're validating if LLMs can generate code WITHOUT perfect context
            logger.warning(f"Semantic search unavailable (expected for Phase 0): {e}")
            logger.info(
                "Proceeding without semantic context - pure LLM generation test"
            )

        # Read content of related files (if any found)
        file_contents = {}
        for file_path in list(related_files)[:3]:  # Max 3 files
            try:
                full_path = self.repo_root / file_path
                if full_path.exists() and full_path.is_file():
                    content = full_path.read_text(encoding="utf-8")
                    if len(content) > 1500:
                        content = content[:1500] + "\n\n... (truncated for brevity)"
                    file_contents[file_path] = content
            except Exception as e:
                logger.warning(f"Could not read {file_path}: {e}")

        context = {
            "goal": goal,
            "target_module": str(constraints.target_location.parent),
            "target_layer": self._identify_layer(constraints.target_location),
            "related_symbols": related_symbols,
            "related_files": file_contents,
        }

        logger.info(
            f"Context gathered: {len(related_symbols)} symbols, "
            f"{len(file_contents)} files"
        )

        return context

    def _identify_layer(self, path: Path) -> str:
        """
        Identify which architectural layer the target belongs to.

        Args:
            path: Target file path

        Returns:
            Layer name: "shared", "domain", "features", "will", "system", etc.
        """
        parts = path.parts
        if "shared" in parts:
            return "shared"
        elif "domain" in parts:
            return "domain"
        elif "features" in parts:
            return "features"
        elif "will" in parts:
            return "will"
        elif "system" in parts:
            return "system"
        elif "core" in parts:
            return "core"
        else:
            return "unknown"

    def _build_generation_prompt(
        self,
        goal: str,
        constraints: GenerationConstraints,
        context: dict[str, Any],
    ) -> str:
        """
        Build the generation prompt for the LLM.

        Includes:
        - Clear goal statement
        - Target location and layer context
        - Related code examples from semantic search
        - CORE's constitutional requirements
        - Explicit formatting instructions

        Args:
            goal: The generation goal
            constraints: Generation constraints
            context: Gathered context information

        Returns:
            Complete prompt string for LLM
        """
        layer = context.get("target_layer", "unknown")

        # Build layer-specific guidance
        layer_guidance = self._get_layer_guidance(layer)

        # Format related code examples
        related_code = self._format_related_code(context)

        prompt = f"""You are generating Python code for the CORE autonomous development system.

GOAL:
{goal}

TARGET LOCATION:
{constraints.target_location}

ARCHITECTURAL LAYER:
{layer} layer
{layer_guidance}

CONSTITUTIONAL REQUIREMENTS (CRITICAL):
1. ALL functions and classes MUST have docstrings
   - Use triple-quoted strings: \"\"\"Docstring here\"\"\"
   - Include purpose, parameters, returns, raises
   - Provide usage examples for complex functions

2. ALL parameters and return values MUST have type hints
   - Use modern Python 3.10+ type hints
   - Example: def func(param: str, count: int) -> bool:
   - Use list[str] not List[str], dict[str, int] not Dict[str, int]

3. Follow CORE's existing patterns and conventions
   - Use existing utilities (Path, logger, yaml_processor)
   - Follow naming: snake_case for functions, PascalCase for classes
   - Import from correct locations based on layer

4. Include proper error handling
   - Validate inputs at function entry
   - Use try-except for operations that can fail
   - Return structured results (dataclasses) not tuples

5. Write clear, readable code (clarity_first principle)
   - Short functions (< 50 lines)
   - Descriptive variable names
   - Comments only for complex logic

RELATED CODE FOR REFERENCE:
{related_code}

GENERATION INSTRUCTIONS:
- Generate ONLY the code for this module
- Do NOT include import statements (we'll add those)
- Do NOT include test code (tests go in separate files)
- Do NOT include example usage (put in docstring)
- Do NOT add explanatory comments outside the code
- Start directly with the code

Output format:
```python
# Your complete, working code here
```

Begin generation:
"""

        return prompt

    def _get_layer_guidance(self, layer: str) -> str:
        """
        Get layer-specific architectural guidance.

        Args:
            layer: The architectural layer name

        Returns:
            Guidance text for that layer
        """
        guidance = {
            "shared": """
The shared layer contains utilities and helpers used across all other layers.
- Keep functions pure and stateless
- No business logic or domain knowledge
- Examples: path utilities, JSON validators, string helpers
""",
            "domain": """
The domain layer contains business logic and validation.
- Use dataclasses for domain models
- Return ValidationResult for validators
- No external dependencies (no API calls, no file I/O)
- Examples: validators, domain models, business rules
""",
            "features": """
The features layer implements high-level system capabilities.
- Can use services, domain logic, and utilities
- Async methods for I/O operations
- Return structured results (dataclasses)
- Examples: code formatters, diff generators, introspection services
""",
            "will": """
The will layer contains AI agents and orchestration.
- Agents inherit from base Agent classes
- Integrate with CognitiveService for LLM access
- Use async methods throughout
- Return structured reports/results
- Examples: PlannerAgent, ExecutionAgent, CoderAgent
""",
            "core": """
The core layer contains action handlers and low-level operations.
- Action handlers follow ActionHandler base pattern
- Register with ActionRegistry
- Include risk_level metadata
- Return ActionResult with success status
""",
        }

        return guidance.get(layer, "No specific layer guidance available.")

    def _format_related_code(self, context: dict[str, Any]) -> str:
        """
        Format related code examples for the prompt.

        Args:
            context: Context dictionary with related symbols and files

        Returns:
            Formatted string with related code examples
        """
        related_symbols = context.get("related_symbols", [])
        related_files = context.get("related_files", {})

        if not related_symbols and not related_files:
            return "(No directly related code found via semantic search)"

        output = []

        if related_symbols:
            output.append("Related Symbols Found:")
            for sym in related_symbols[:5]:  # Max 5 symbols
                output.append(f"  - {sym['name']} ({sym['type']}) in {sym['file']}")
                if sym.get("docstring"):
                    # Show first line of docstring
                    first_line = sym["docstring"].split("\n")[0]
                    output.append(f"    Purpose: {first_line}")

        if related_files:
            output.append("\nRelated Code Examples:")
            for file_path, content in list(related_files.items())[:2]:  # Max 2 files
                output.append(f"\n## From {file_path}:")
                output.append(content)

        return "\n".join(output)

    async def _call_llm(
        self,
        prompt: str,
        constraints: GenerationConstraints,
    ) -> str:
        """
        Call LLM via CognitiveService to generate code.

        Args:
            prompt: The generation prompt
            constraints: Generation constraints (max_tokens, temperature)

        Returns:
            Raw LLM response text

        Raises:
            Exception: If LLM call fails
        """
        logger.info("Calling LLM for code generation")

        try:
            # Get client for code generation role
            client = await self.cognitive_service.aget_client_for_role("Coder")

            # Generate code using make_request_async (CORE's API)
            response = await client.make_request_async(
                prompt=prompt, user_id="phase0_validation"
            )

            logger.info("LLM generation successful")
            return response

        except Exception as e:
            logger.error(f"LLM generation failed: {e}", exc_info=True)
            raise

    def _extract_code(self, generated_text: str) -> str:
        """
        Extract clean Python code from LLM response.

        Handles:
        - Markdown code blocks (```python ... ```)
        - Generic code blocks (``` ... ```)
        - Plain text responses
        - Multiple code blocks (takes first one)
        - Whitespace cleanup

        Args:
            generated_text: Raw LLM response

        Returns:
            Cleaned Python code
        """
        logger.debug("Extracting code from LLM response")

        text = generated_text.strip()

        # Look for ```python code block
        if "```python" in text:
            start = text.find("```python") + len("```python")
            end = text.find("```", start)
            if end != -1:
                code = text[start:end].strip()
                logger.debug("Extracted code from ```python block")
                return code

        # Look for generic ``` code block
        if "```" in text:
            start = text.find("```") + 3
            # Skip language identifier if present
            newline = text.find("\n", start)
            if newline != -1:
                start = newline + 1
            end = text.find("```", start)
            if end != -1:
                code = text[start:end].strip()
                logger.debug("Extracted code from generic ``` block")
                return code

        # No code block markers, assume entire response is code
        # This handles cases where LLM follows instructions perfectly
        logger.debug("No code block markers found, using entire response")
        return text
