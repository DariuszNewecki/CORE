# src/shared/infrastructure/validation/schema_registry.py

"""
Typed construction of a `referencing.Registry` with a retrieve callback.

`Registry` declares its retrieve callback as the attrs field `_retrieve`
with `alias="retrieve"`; `Registry(retrieve=...)` is the library's
documented call and works at runtime, but mypy's attrs plugin does not see
the alias and reports an unexpected keyword. This is the one place that
call is made, so callers stay fully type-checked.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from referencing import Registry, Resource


# ID: bdae64a9-8469-483a-ab2f-ffa5f5d8a630
def registry_with_retrieve(retrieve: Callable[[str], Resource]) -> Registry:
    """Return an empty Registry that resolves unknown URIs with `retrieve`."""
    factory = cast(Callable[..., Registry[Any]], Registry)
    return factory(retrieve=retrieve)
