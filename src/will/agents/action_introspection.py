# src/will/agents/action_introspection.py
# ID: 757f6273-c945-4724-8c41-33cc9b372dfc

"""
Action Parameter Introspection

Extracts parameter requirements from action function signatures.
This allows the Planner to dynamically discover what parameters
each action needs, without hardcoding.

Constitutional Principle: Actions own their contracts through function signatures.
"""

from __future__ import annotations

import inspect
from typing import Any, get_type_hints

from body.atomic.registry import ActionDefinition
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 272fd882-8987-4715-b5ee-7bf4a9e4b1d4
# ID: 21b4b319-0ad6-412c-b7f9-e9253e62d30b
def introspect_action_parameters(action: ActionDefinition) -> dict[str, Any]:
    """
    Extract parameter requirements from an action's function signature.

    Returns dict with:
    - required_params: List of parameter names that MUST be provided
    - optional_params: List of parameter names that have defaults
    - param_types: Dict mapping parameter names to their type hints

    Excludes internal parameters that are injected by ActionExecutor:
    - core_context
    - write
    - self, cls
    - **kwargs
    """
    try:
        sig = inspect.signature(action.executor)

        # Try to resolve type hints
        try:
            type_hints = get_type_hints(action.executor)
        except Exception:
            type_hints = {}

        required = []
        optional = []
        param_types = {}

        # List of params that are injected by executor, not provided by planner
        injected_params = {"core_context", "write", "self", "cls", "kwargs"}

        for name, param in sig.parameters.items():
            # Skip injected parameters
            if name in injected_params:
                continue

            # Skip **kwargs
            if param.kind == inspect.Parameter.VAR_KEYWORD:
                continue

            # Get type hint
            annotation = type_hints.get(name, param.annotation)
            if annotation != inspect.Parameter.empty:
                param_types[name] = _format_type_hint(annotation)
            else:
                param_types[name] = "any"

            # Check if required or optional
            if param.default == inspect.Parameter.empty:
                required.append(name)
            else:
                optional.append(name)

        return {
            "required_params": required,
            "optional_params": optional,
            "param_types": param_types,
        }

    except Exception as e:
        logger.warning(
            "Failed to introspect parameters for %s: %s", action.action_id, e
        )
        return {
            "required_params": [],
            "optional_params": [],
            "param_types": {},
        }


def _format_type_hint(annotation: Any) -> str:
    """Format a type annotation into a readable string."""
    if hasattr(annotation, "__name__"):
        return annotation.__name__

    # Handle typing module types
    annotation_str = str(annotation)

    # Clean up common patterns
    if "typing." in annotation_str:
        annotation_str = annotation_str.replace("typing.", "")

    return annotation_str


# ID: 34ad1033-8321-4ef5-875d-076212d43055
# ID: 6a59b172-7569-4bfe-ab6b-94d98f32d657
def build_action_schema_for_llm(action: ActionDefinition) -> dict[str, Any]:
    """
    Build a complete schema for an action that can be provided to the LLM.

    Returns:
        Dict suitable for JSON serialization with all info LLM needs
    """
    params_info = introspect_action_parameters(action)

    schema = {
        "action_id": action.action_id,
        "description": action.description,
        "impact": action.impact_level,
        "category": action.category.value,
        "required_params": params_info["required_params"],
        "optional_params": params_info["optional_params"],
    }

    # Add param types as hints
    if params_info["param_types"]:
        schema["param_types"] = params_info["param_types"]

    return schema


# ID: ab792d2f-f67f-4e58-9356-d7421b63f945
# ID: 98edc49b-c1be-43a9-9cb6-d866ba64a31a
def get_all_action_schemas(actions: list[ActionDefinition]) -> list[dict[str, Any]]:
    """
    Build schemas for all actions.

    This is what gets passed to the Planner LLM.
    """
    return [build_action_schema_for_llm(action) for action in actions]
