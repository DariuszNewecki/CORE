import abc
import re
from typing import Any, Dict, List, Optional

from ..core.base_agent import BaseAgent


class BasePlanner(BaseAgent, abc.ABC):
    """Base class for planner agents with common prompt building and plan parsing logic."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.plan_history: List[Dict[str, Any]] = []

    def build_plan_prompt(
        self,
        objective: str,
        context: Optional[str] = None,
        constraints: Optional[List[str]] = None,
        available_tools: Optional[List[str]] = None,
        plan_history: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Build a standardized prompt for planning tasks."""

        prompt_parts = []

        # Add objective
        prompt_parts.append(f"OBJECTIVE:\n{objective}\n")

        # Add context if provided
        if context:
            prompt_parts.append(f"CONTEXT:\n{context}\n")

        # Add constraints if provided
        if constraints:
            constraints_text = "\n".join(
                [f"- {constraint}" for constraint in constraints]
            )
            prompt_parts.append(f"CONSTRAINTS:\n{constraints_text}\n")

        # Add available tools if provided
        if available_tools:
            tools_text = "\n".join([f"- {tool}" for tool in available_tools])
            prompt_parts.append(f"AVAILABLE TOOLS:\n{tools_text}\n")

        # Add plan history if provided
        if plan_history:
            history_text = self._format_plan_history(plan_history)
            prompt_parts.append(f"PREVIOUS PLAN HISTORY:\n{history_text}\n")

        # Add planning instructions
        planning_instructions = self._get_planning_instructions()
        prompt_parts.append(f"PLANNING INSTRUCTIONS:\n{planning_instructions}\n")

        return "\n".join(prompt_parts)

    def parse_plan_response(self, response: str) -> Dict[str, Any]:
        """Parse the plan from the agent's response."""

        # Extract plan steps
        steps = self._extract_plan_steps(response)

        # Extract reasoning
        reasoning = self._extract_reasoning(response)

        # Extract confidence if present
        confidence = self._extract_confidence(response)

        # Extract any additional metadata
        metadata = self._extract_metadata(response)

        plan = {
            "steps": steps,
            "reasoning": reasoning,
            "confidence": confidence,
            "raw_response": response,
            "metadata": metadata,
        }

        # Validate the parsed plan
        self._validate_plan(plan)

        # Add to history
        self.plan_history.append(plan)

        return plan

    def _format_plan_history(self, plan_history: List[Dict[str, Any]]) -> str:
        """Format plan history for inclusion in prompts."""
        if not plan_history:
            return "No previous plans."

        history_lines = []
        for i, plan in enumerate(plan_history[-3:], 1):  # Show last 3 plans
            history_lines.append(f"Plan {i}:")
            history_lines.append(f"  Steps: {len(plan.get('steps', []))}")
            if plan.get("reasoning"):
                history_lines.append(f"  Reasoning: {plan['reasoning'][:100]}...")
            history_lines.append("")

        return "\n".join(history_lines)

    def _extract_plan_steps(self, response: str) -> List[Dict[str, str]]:
        """Extract plan steps from the response."""
        steps = []

        # Look for numbered steps
        step_pattern = r"(\d+\.|\-|\*)\s*(.+?)(?=\n\s*(?:\d+\.|\-|\*)|\n\n|$)"
        matches = re.findall(step_pattern, response, re.DOTALL | re.IGNORECASE)

        for match in matches:
            step_text = match[1].strip()
            if step_text and len(step_text) > 5:  # Basic validation
                steps.append({"description": step_text, "type": "action"})

        # If no numbered steps found, try to extract from structured formats
        if not steps:
            steps = self._extract_structured_steps(response)

        return steps

    def _extract_structured_steps(self, response: str) -> List[Dict[str, str]]:
        """Extract steps from structured formats like JSON or XML."""
        steps = []

        # Try to find JSON-like structures
        json_pattern = r'\{[^{}]*"steps?"[^{}]*\[[^]]*\][^{}]*\}'
        json_matches = re.findall(json_pattern, response, re.DOTALL)

        # This is a simplified extraction - subclasses should override for complex cases
        for match in json_matches:
            # Look for step descriptions in the JSON
            desc_pattern = r'"description?"\s*:\s*"([^"]+)"'
            desc_matches = re.findall(desc_pattern, match)
            for desc in desc_matches:
                steps.append({"description": desc, "type": "action"})

        return steps

    def _extract_reasoning(self, response: str) -> str:
        """Extract reasoning from the response."""
        reasoning_patterns = [
            r"REASONING:\s*(.+?)(?=PLAN:|STEPS:|$|\n\n)",
            r"THOUGHT PROCESS:\s*(.+?)(?=PLAN:|STEPS:|$|\n\n)",
            r"RATIONALE:\s*(.+?)(?=PLAN:|STEPS:|$|\n\n)",
        ]

        for pattern in reasoning_patterns:
            match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()

        # If no specific reasoning section, take the first paragraph
        paragraphs = response.split("\n\n")
        if paragraphs and len(paragraphs[0]) > 50:  # Reasonable length for reasoning
            return paragraphs[0].strip()

        return ""

    def _extract_confidence(self, response: str) -> float:
        """Extract confidence score from response."""
        confidence_patterns = [
            r"CONFIDENCE:\s*(\d+(?:\.\d+)?)",
            r"confidence:\s*(\d+(?:\.\d+)?)",
            r"certainty:\s*(\d+(?:\.\d+)?)",
        ]

        for pattern in confidence_patterns:
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                try:
                    confidence = float(match.group(1))
                    return min(max(confidence, 0.0), 1.0)  # Clamp to [0,1]
                except ValueError:
                    continue

        return 0.5  # Default confidence

    def _extract_metadata(self, response: str) -> Dict[str, Any]:
        """Extract additional metadata from response."""
        metadata = {}

        # Extract estimated duration if present
        duration_pattern = r"DURATION:\s*(\d+)\s*(minutes?|hours?|days?)"
        duration_match = re.search(duration_pattern, response, re.IGNORECASE)
        if duration_match:
            metadata["estimated_duration"] = (
                f"{duration_match.group(1)} {duration_match.group(2)}"
            )

        # Extract complexity if present
        complexity_pattern = r"COMPLEXITY:\s*(low|medium|high)"
        complexity_match = re.search(complexity_pattern, response, re.IGNORECASE)
        if complexity_match:
            metadata["complexity"] = complexity_match.group(1).lower()

        return metadata

    def _validate_plan(self, plan: Dict[str, Any]):
        """Validate the parsed plan structure."""
        if not plan.get("steps"):
            raise ValueError("Plan must contain at least one step")

        for step in plan["steps"]:
            if not step.get("description"):
                raise ValueError("Each plan step must have a description")

    def _get_planning_instructions(self) -> str:
        """Get standardized planning instructions."""
        return """Please create a detailed, step-by-step plan to achieve the objective. Follow these guidelines:

1. Break down the objective into clear, actionable steps
2. Each step should be specific and measurable
3. Consider dependencies between steps
4. Include any necessary validation or verification steps
5. Estimate the complexity and required resources
6. Provide reasoning for your approach

Format your response as:
REASONING: <your reasoning here>
PLAN:
1. First step description
2. Second step description
..."""

    def clear_history(self):
        """Clear the plan history."""
        self.plan_history.clear()
