# src/will/phases/planning_phase.py
from shared.logger import getLogger


logger = getLogger(__name__)
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


logger = logging.getLogger(__name__)


@dataclass
# ID: 7923b8d1-e226-4a21-8418-638ac5d02f0e
class PlanStep:
    """Represents a single step in an execution plan."""

    action: str
    parameters: dict[str, Any]
    description: str
    dependencies: list[str] = None

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


# ID: 3969e529-7e45-4670-9dbb-581019fe4e68
class PlanValidator(ABC):
    """Abstract base class for plan validation strategies."""

    @abstractmethod
    # ID: 8d583684-39a0-4aef-9c82-ccf136b5badb
    def validate(self, plan: list[PlanStep]) -> bool:
        """Validate the given plan."""
        pass


# ID: 070ec97d-e7de-40e3-a1a0-983f204493c7
class BasicPlanValidator(PlanValidator):
    """Basic plan validator that checks for required fields and dependencies."""

    # ID: 24a336f9-33a4-44ec-9b6d-31b36345bdfd
    def validate(self, plan: list[PlanStep]) -> bool:
        """Validate plan structure and dependencies."""
        if not plan:
            logger.warning("Plan is empty")
            return False
        step_ids = [step.action for step in plan]
        for step in plan:
            if not step.action or not step.description:
                logger.error("Step missing required fields: %s", step)
                return False
            for dep in step.dependencies:
                if dep not in step_ids:
                    logger.error(
                        "Dependency '%s' not found in plan for step '%s'",
                        dep,
                        step.action,
                    )
                    return False
        logger.debug("Plan validation passed")
        return True


# ID: 7030bced-0c58-46fc-aa38-2fb2d0831ebb
class PlanOptimizer:
    """Optimizes plan execution order based on dependencies."""

    @staticmethod
    # ID: 03534a87-fc32-4313-85ec-1798810dfc02
    def topological_sort(plan: list[PlanStep]) -> list[PlanStep]:
        """Sort plan steps based on dependencies using topological sort."""
        graph: dict[str, list[str]] = {}
        in_degree: dict[str, int] = {}
        step_map: dict[str, PlanStep] = {}
        for step in plan:
            step_id = step.action
            step_map[step_id] = step
            graph[step_id] = []
            in_degree[step_id] = 0
        for step in plan:
            for dep in step.dependencies:
                if dep in graph:
                    graph[dep].append(step.action)
                    in_degree[step.action] += 1
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
    # ID: e931ec2e-760a-432b-ba27-f2b0cd44a9b5
    def remove_redundant_steps(plan: list[PlanStep]) -> list[PlanStep]:
        """Remove duplicate steps from the plan."""
        seen_actions = set()
        filtered_plan: list[PlanStep] = []
        for step in plan:
            if step.action not in seen_actions:
                seen_actions.add(step.action)
                filtered_plan.append(step)
            else:
                logger.debug("Removing duplicate step: %s", step.action)
        return filtered_plan


# ID: e9f53516-712a-4f49-b270-93d49407e5dd
class PlanningPhase:
    """Main planning phase class that orchestrates plan creation and validation."""

    def __init__(self, validator: PlanValidator | None = None):
        self.validator = validator or BasicPlanValidator()
        self.optimizer = PlanOptimizer()

    # ID: 2a2211fd-69d5-4828-b107-9d3be7eeacde
    def create_plan(
        self, objectives: list[str], context: dict[str, Any]
    ) -> list[PlanStep]:
        """Create an execution plan based on objectives and context."""
        logger.info("Creating plan for objectives: %s", objectives)
        plan: list[PlanStep] = []
        for i, objective in enumerate(objectives):
            step = PlanStep(
                action=f"objective_{i}",
                parameters={"goal": objective, "context": context},
                description=f"Achieve objective: {objective}",
                dependencies=self._calculate_dependencies(i, plan),
            )
            plan.append(step)
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
        return [current_plan[-1].action] if current_plan else []

    # ID: f77f8342-bc9e-4b0c-a713-fb646c8536d3
    def validate_and_optimize(self, plan: list[PlanStep]) -> list[PlanStep] | None:
        """Validate and optimize the given plan."""
        if not self.validator.validate(plan):
            logger.error("Plan validation failed")
            return None
        optimized_plan = self.optimizer.remove_redundant_steps(plan)
        sorted_plan = self.optimizer.topological_sort(optimized_plan)
        logger.info("Plan optimized: %s steps", len(sorted_plan))
        return sorted_plan

    # ID: b1a21ddf-ae08-4644-8497-4e5a257788cd
    def execute_planning(
        self, objectives: list[str], context: dict[str, Any]
    ) -> list[PlanStep] | None:
        """Main entry point: create, validate, and optimize a plan."""
        try:
            plan = self.create_plan(objectives, context)
            return self.validate_and_optimize(plan)
        except Exception as e:
            logger.error("Planning phase failed: %s", e)
            return None
