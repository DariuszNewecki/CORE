# src/shared/cli/__init__.py

"""CLI-adjacent primitives shared between the CLI layer and Body services
that introspect it (e.g. command_sync_service). Sits in shared/ to avoid a
Body → CLI import inversion while keeping the types out of shared.models
(which holds domain models, not CLI metadata)."""
