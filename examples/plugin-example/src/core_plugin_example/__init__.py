"""Example CORE plug-in (ADR-177).

The manifest is plain data, checked against CORE's plugin_manifest.schema.json.
The plug-in's name and version come from its package metadata (pyproject.toml).
"""

from __future__ import annotations


MANIFEST = {
    "format_version": 1,
    "core_engine_api": "1",
    "engines": ["core_plugin_example.engines:NoTodoGate"],
    "catalogs": "catalogs",
}
