"""ContextCache — file_handler DI propagation (ADR-126 Stage 1).

Pins that the file_handler injected at construction is forwarded to
ContextSerializer.to_yaml() on every cache write.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from shared.infrastructure.context.cache import ContextCache


# ID: ac2da7c7-8b57-4979-aed9-71694eef3f8d
def test_cache_set_propagates_none_file_handler(tmp_path: Path) -> None:
    """set() with no file_handler must not raise; serializer receives None."""
    cache = ContextCache(cache_dir=str(tmp_path))

    with patch(
        "shared.infrastructure.context.cache.ContextSerializer.to_yaml"
    ) as mock_to_yaml:
        cache.set("key1", {"evidence": []})
        _packet, _path, fh_arg = mock_to_yaml.call_args[0]
        assert fh_arg is None


# ID: db0b32e9-9d39-4c78-bf98-4413693bcf24
def test_cache_set_propagates_injected_file_handler(tmp_path: Path) -> None:
    """set() must forward the injected FileHandler to ContextSerializer."""
    mock_fh = MagicMock()
    cache = ContextCache(cache_dir=str(tmp_path), file_handler=mock_fh)

    with patch(
        "shared.infrastructure.context.cache.ContextSerializer.to_yaml"
    ) as mock_to_yaml:
        cache.set("key2", {"evidence": []})
        _packet, _path, fh_arg = mock_to_yaml.call_args[0]
        assert fh_arg is mock_fh
