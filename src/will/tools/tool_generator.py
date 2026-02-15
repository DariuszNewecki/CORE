# src/will/tools/tool_generator.py
# ID: 0b465fc3-b02d-4c58-9684-c4a8ba658479
"""
Transforms Python functions into LLM Tool Definitions per Standard.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from pathlib import Path
from typing import Any, Union, get_type_hints
from uuid import UUID


# ID: 4fdb9833-ace2-4f72-a2fc-772f260c4ae0
def python_type_to_json_type(py_type: Any) -> str:
    """
    Map Python types to JSON Schema types used by LLMs.
    """
    # Handle Optional[T] -> T
    if hasattr(py_type, "__origin__") and py_type.__origin__ is Union:
        args = py_type.__args__
        # If NoneType is in args, it's Optional. Grab the first non-None type.
        non_none = [a for a in args if a is not type(None)]
        if non_none:
            return python_type_to_json_type(non_none[0])

    # Fix: Use 'is' for type comparisons (Ruff E721 compliance)
    if py_type is str:
        return "string"
    if py_type is int:
        return "integer"
    if py_type is float:
        return "number"
    if py_type is bool:
        return "boolean"
    if py_type is Path:
        return "string"  # Annotated as file-path usually
    if py_type is UUID:
        return "string"  # Annotated as uuid

    # Fallback for complex types (List, Dict, etc)
    return "string"


# ID: 44a5fb0c-6b66-43bb-b9f3-7b025aeba2cc
def generate_tool_definition(func: Callable) -> dict[str, Any]:
    """
    Introspects a @core_command or @atomic_action function
    and generates an OpenAI-compatible tool definition.
    """
    sig = inspect.signature(func)

    # Resolve forward references in type hints if possible
    try:
        type_hints = get_type_hints(func)
    except Exception:
        # Fallback if types can't be resolved (e.g. circular imports)
        type_hints = {}

    doc = inspect.getdoc(func) or "No description provided."

    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    for name, param in sig.parameters.items():
        # Exclude internal injection parameters
        if name in ["self", "cls", "context"]:
            continue

        # Determine type
        annotation = type_hints.get(name, param.annotation)

        # If annotation is empty/missing, default to str
        if annotation is inspect.Parameter.empty:
            annotation = str

        json_type = python_type_to_json_type(annotation)

        param_info = {"type": json_type}

        # Add description if we could parse docstrings (future improvement)
        # For now, we just set the type.
        param_info["description"] = f"Parameter: {name}"

        parameters["properties"][name] = param_info

        # Determine required status
        # If no default value is set, it is required
        if param.default == inspect.Parameter.empty:
            parameters["required"].append(name)

    return {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": doc,
            "parameters": parameters,
        },
    }
