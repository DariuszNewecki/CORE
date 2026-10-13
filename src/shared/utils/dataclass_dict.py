# src/shared/utils/dataclass_dict.py
"""One ``to_dict`` for dataclasses that serialise as ``dataclasses.asdict``."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any


# ID: f1aee3d5-33e8-4717-bbd6-17ee36af3c78
class DataclassDict:
    """Mixin: ``to_dict()`` is ``dataclasses.asdict(self)``, JSON-ready when
    the fields are."""

    # ID: 63c33251-9e2c-4fef-8ddc-745b0ec5c5c4
    def to_dict(self) -> dict[str, Any]:
        """The dataclass as a plain dict (nested dataclasses included)."""
        return asdict(self)  # type: ignore[call-overload]
