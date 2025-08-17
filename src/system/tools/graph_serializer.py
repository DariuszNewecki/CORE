# src/system/tools/graph_serializer.py
"""
Handles serialization of the knowledge graph to JSON format.
"""
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from filelock import FileLock

from shared.logger import getLogger
from system.tools.models import FunctionInfo

log = getLogger(__name__)


class GraphSerializer:
    """Handles serialization of knowledge graph data."""

    @staticmethod
    def serialize_functions(functions: Dict[str, FunctionInfo]) -> Dict[str, Any]:
        """Convert FunctionInfo objects to serializable dictionaries."""
        serializable_functions = {
            key: asdict(
                info, dict_factory=lambda x: {k: v for (k, v) in x if v is not None}
            )
            for key, info in functions.items()
        }

        # Sort calls for consistent output
        for data in serializable_functions.values():
            data["calls"] = sorted(list(data["calls"]))

        return serializable_functions

    @staticmethod
    def build_graph_data(
        functions: Dict[str, FunctionInfo], files_scanned: int
    ) -> Dict[str, Any]:
        """Build the complete knowledge graph data structure."""
        serializable_functions = GraphSerializer.serialize_functions(functions)

        return {
            "schema_version": "2.0.0",
            "metadata": {
                "files_scanned": files_scanned,
                "total_symbols": len(functions),
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            },
            "symbols": serializable_functions,
        }

    @staticmethod
    def save_to_file(graph_data: Dict[str, Any], output_path: Path) -> None:
        """Save the knowledge graph to a JSON file with file locking."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with FileLock(str(output_path) + ".lock"):
            output_path.write_text(json.dumps(graph_data, indent=2), encoding="utf-8")

        log.info(f"✅ Knowledge graph saved to {output_path}")
        log.info(
            f"   -> {graph_data['metadata']['files_scanned']} files, "
            f"{graph_data['metadata']['total_symbols']} symbols"
        )
