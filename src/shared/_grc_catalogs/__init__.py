# src/shared/_grc_catalogs/__init__.py
# Package marker -- lets importlib.resources.files("shared._grc_catalogs")
# resolve the bundled public GRC catalogs as package data from an installed
# wheel (ADR-116 D6, amended 2026-10-03: the public tier ships in the wheel;
# licensed and internal catalogs never do).
#
# This directory is the wheel-side MIRROR of the repository's grc-catalogs/
# public tier plus its inventory.yaml, not their source of truth. Every
# catalog change updates source and mirror in the same commit;
# tests/infra/test_grc_catalogs_ship_in_wheel.py enforces byte parity and
# prints the one rsync line that resyncs. Nothing writes here at runtime.
