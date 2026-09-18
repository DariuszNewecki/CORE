# src/shared/_prompts/__init__.py
# Package marker -- lets importlib.resources.files("shared._prompts") resolve the
# bundled prompt corpus as package data from an installed wheel (#909).
#
# This directory is the wheel-side MIRROR of the prompt corpus, not its source
# of truth. The source is the repository's prompt root (PathResolver.prompts_dir,
# today var/prompts/). Every governed prompt change updates source and mirror in
# the same commit; tests/infra/test_prompts_ship_in_wheel.py enforces byte parity
# and prints the one rsync line that resyncs. Nothing writes here at runtime.
