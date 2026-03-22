# src/will/phases/planning_phase.py
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


logger = logging.getLogger(__name__)


@dataclass
# ID: 2c5980ff-1938-4917-bec5-58aa97d5369a
class PlanStep:
    """Represents a single step in an execution plan."""

    action: str
    parameters: dict[str, Any]
    description: str
    dependencies: list[str] = None

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


# ID: e52b90ef-71e9-4ed0-ad66-143538c6135e
class PlanValidator(ABC):
    """Abstract base class for plan validation strategies."""

    @abstractmethod
    # ID: b6dde360-7b43-435c-a199-f39b93104180
    def validate(self, plan: list[PlanStep]) -> bool:
        """Validate the given plan."""
        pass


# ID: 95733a19-aae9-47bf-917c-4ac440bcec13
class BasicPlanValidator(PlanValidator):
    """Basic plan validator that checks for required fields and dependencies."""

    # ID: be089088-f23c-4c90-b26f-4789a5046659
    def validate(self, plan: list[PlanStep]) -> bool:
        """Validate plan structure and dependencies."""
        if not plan:
            logger.warning("Plan is empty")
            return False

        step_ids = [step.action for step in plan]

        for step in plan:
            if not step.action or not step.description:
                logger.error(f"Step missing required fields: {step}")
                return False

            for dep in step.dependencies:
                if dep not in step_ids:
                    logger.error(
                        f"Dependency '{dep}' not found in plan for step '{step.action}'"
                    )
                    return False

        logger.debug("Plan validation passed")
        return True


# ID: 64907894-6354-4d19-9c16-2c44188b0d07
class PlanOptimizer:
    """Optimizes plan execution order based on dependencies."""

    @staticmethod
    # ID: 41771791-1516-482a-8c43-5a36026019dd
    def topological_sort(plan: list[PlanStep]) -> list[PlanStep]:
        """Sort plan steps based on dependencies using topological sort."""
        graph: dict[str, list[str]] = {}
        in_degree: dict[str, int] = {}
        step_map: dict[str, PlanStep] = {}

        # Initialize data structures
        for step in plan:
            step_id = step.action
            step_map[step_id] = step
            graph[step_id] = []
            in_degree[step_id] = 0

        # Build graph and calculate in-degrees
        for step in plan:
            for dep in step.dependencies:
                if dep in graph:
                    graph[dep].append(step.action)
                    in_degree[step.action] += 1

        # Perform topological sort
        result: list[PlanStep] = []
        queue = [step_id for step_id in in_degree if in_degree[step_id] == 0]

        while queue:
            current = queue.pop(0)
            result.append(step_map[current])

            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(result) != len(plan):
            logger.warning(
                "Cycle detected in plan dependencies, returning original order"
            )
            return plan

        return result

    @staticmethod
    # ID: 8c22f51f-12c3-42a8-b903-b2f1ba7e6d50
    def remove_redundant_steps(plan: list[PlanStep]) -> list[PlanStep]:
        """Remove duplicate steps from the plan."""
        seen_actions = set()
        filtered_plan: list[PlanStep] = []

        for step in plan:
            if step.action not in seen_actions:
                seen_actions.add(step.action)
                filtered_plan.append(step)
            else:
                logger.debug(f"Removing duplicate step: {step.action}")

        return filtered_plan


# ID: 9803f30c-f59d-43c3-9a56-cbcd171876fd
class PlanningPhase:
    """Main planning phase class that orchestrates plan creation and validation."""

    def __init__(self, validator: PlanValidator | None = None):
        self.validator = validator or BasicPlanValidator()
        self.optimizer = PlanOptimizer()

    # ID: 9ade3d26-ecc3-4d28-b310-f6a92fc73d05
    def create_plan(
        self, objectives: list[str], context: dict[str, Any]
    ) -> list[PlanStep]:
        """Create an execution plan based on objectives and context."""
        logger.info(f"Creating plan for objectives: {objectives}")

        plan: list[PlanStep] = []

        for i, objective in enumerate(objectives):
            step = PlanStep(
                action=f"objective_{i}",
                parameters={"goal": objective, "context": context},
                description=f"Achieve objective: {objective}",
                dependencies=self._calculate_dependencies(i, plan),
            )
            plan.append(step)

        # Add finalization step if needed
        if plan:
            final_step = PlanStep(
                action="finalize",
                parameters={"summary": True},
                description="Finalize execution plan",
                dependencies=[step.action for step in plan],
            )
            plan.append(final_step)

        return plan

    def _calculate_dependencies(
        self, index: int, current_plan: list[PlanStep]
    ) -> list[str]:
        """Calculate dependencies for a new plan step."""
        if index == 0:
            return []

        # Simple dependency: each step depends on the previous one
        return [current_plan[-1].action] if current_plan else []

    # ID: af7dc16d-516c-4fb1-aa7b-37b15578f4fb
    def validate_and_optimize(self, plan: list[PlanStep]) -> list[PlanStep] | None:
        """Validate and optimize the given plan."""
        if not self.validator.validate(plan):
            logger.error("Plan validation failed")
            return None

        # Remove redundant steps
        optimized_plan = self.optimizer.remove_redundant_steps(plan)

        # Sort by dependencies
        sorted_plan = self.optimizer.topological_sort(optimized_plan)

        logger.info(f"Plan optimized: {len(sorted_plan)} steps")
        return sorted_plan

    # ID: 63c31d6a-a006-4ab6-8935-225119eb4458
    def execute_planning(
        self, objectives: list[str], context: dict[str, Any]
    ) -> list[PlanStep] | None:
        """Main entry point: create, validate, and optimize a plan."""
        try:
            plan = self.create_plan(objectives, context)
            return self.validate_and_optimize(plan)
        except Exception as e:
            logger.error(f"Planning phase failed: {e}")
            return None
