# src/will/tools/anchor_builder.py

"""
Builds anchor payloads for layers and modules.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from qdrant_client.models import PointStruct

from shared.universal import get_deterministic_id
from will.tools.module_descriptor import ModuleDescriptor

from .layers import LAYERS


# ID: d5f30c14-103d-413d-99b6-c3e06a73060b
def build_layer_anchor(layer_name: str, embedding: list[float]) -> PointStruct:
    """Build a PointStruct for a layer anchor."""
    layer_purpose = LAYERS[layer_name]
    description = (
        f"Layer: {layer_name}\n\n"
        f"Purpose: {layer_purpose}\n\n"
        f"This is a top-level architectural layer in CORE's Mind-Body-Will structure."
    )

    return PointStruct(
        id=get_deterministic_id(f"layer_{layer_name}"),
        vector=embedding,
        payload={
            "type": "layer",
            "name": layer_name,
            "path": f"src/{layer_name}/",
            "purpose": layer_purpose,
            "description": description,
        },
    )


# ID: 6c26ed3e-5fc0-489f-aa9b-4257888ddd4a
def build_module_anchor(
    module_path: Path,
    module_info: dict[str, Any],
    embedding: list[float],
) -> PointStruct:
    """Build a PointStruct for a module anchor."""
    layer = module_info["layer"]
    files = module_info["python_files"]

    module_description = ModuleDescriptor.generate(
        str(module_path), module_path.name, layer, files
    )

    description = (
        f"Module: {module_path}\n"
        f"Architectural Layer: {layer}\n"
        f"Layer Purpose: {LAYERS[layer]}\n\n"
        f"Module Purpose: {module_description}\n\n"
        f"Example Files: {', '.join(files[:3])}"
    )

    return PointStruct(
        id=get_deterministic_id(f"module_{module_path}"),
        vector=embedding,
        payload={
            "type": "module",
            "name": module_path.name,
            "path": f"src/{module_path}/",
            "layer": layer,
            "purpose": module_description,
            "description": description,
            "file_count": module_info["file_count"],
            "example_files": files,
        },
    )


# ID: ed1a2aa4-ca1c-440c-89df-efdee8690c6d
def get_layer_description_for_embedding(layer_name: str) -> str:
    """Get layer description text for embedding generation."""
    layer_purpose = LAYERS[layer_name]
    return (
        f"Layer: {layer_name}\n\n"
        f"Purpose: {layer_purpose}\n\n"
        f"This is a top-level architectural layer in CORE's Mind-Body-Will structure."
    )


# ID: b0b990a8-9888-4af7-88f9-b72a9890e4fa
def get_module_description_for_embedding(
    module_path: Path,
    module_info: dict[str, Any],
) -> str:
    """Get module description text for embedding generation."""
    layer = module_info["layer"]
    files = module_info["python_files"]

    module_description = ModuleDescriptor.generate(
        str(module_path), module_path.name, layer, files
    )

    return (
        f"Module: {module_path}\n"
        f"Architectural Layer: {layer}\n"
        f"Layer Purpose: {LAYERS[layer]}\n\n"
        f"Module Purpose: {module_description}\n\n"
        f"Example Files: {', '.join(files[:3])}"
    )
