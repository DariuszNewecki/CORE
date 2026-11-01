# src/shared/_prompts/__init__.py
# Package marker -- lets importlib.resources.files("shared._prompts") resolve the
# prompt corpus as package data from an installed wheel (#909).
#
# This directory is the prompt corpus's one source (#1387): CORE's law points its
# prompt root here (prompts.root in governance_paths.yaml) and the wheel ships it.
# An adopter may override a prompt under its own var/prompts/. Nothing writes here
# at runtime.
