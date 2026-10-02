# src/shared/_packs/__init__.py
# Package marker -- lets importlib.resources.files("shared._packs") resolve the
# bundled governance packs as package data from an installed wheel.
#
# This directory is the wheel-side MIRROR of the pack registry, not its source
# of truth. The source is the repository's top-level packs/ (ADR-149). Every
# governed pack change updates source and mirror in the same commit;
# tests/infra/test_packs_ship_in_wheel.py enforces byte parity and prints the
# one rsync line that resyncs. Nothing writes here at runtime.
