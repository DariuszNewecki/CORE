"""ADR-126 canonical import path regression.

Verifies that FileHandler lives at body.infrastructure.storage.file_handler
(the permanent home after Stage 3) and that the old shared.* shim is gone.
"""

from __future__ import annotations

import importlib

import pytest

from body.infrastructure.storage.file_handler import FileHandler, FileOpResult


# ID: a8f7159d-da02-4ccf-ac1d-ec336b97237f
def test_file_handler_importable_from_body_path() -> None:
    """FileHandler must be importable from its canonical body path."""
    mod = importlib.import_module("body.infrastructure.storage.file_handler")
    assert hasattr(mod, "FileHandler")
    assert hasattr(mod, "FileOpResult")


# ID: de2f53e6-e0a0-499b-9e4f-8a116f10ea8e
def test_shared_shim_is_gone() -> None:
    """Stage 3 removes the re-export shim — old path must not resolve."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("shared.infrastructure.storage.file_handler")


# ID: b6615ee9-d03a-4ffe-aa73-46a8d08e3902
def test_file_handler_constructible(tmp_path: pytest.TempPathFactory) -> None:
    """FileHandler can be instantiated from the canonical path."""
    fh = FileHandler(str(tmp_path))
    assert fh is not None


# ID: 3b819b92-6e87-4532-86e5-747dc1729095
def test_file_op_result_is_exported() -> None:
    """FileOpResult is part of the public API at the canonical path."""
    assert FileOpResult is not None
