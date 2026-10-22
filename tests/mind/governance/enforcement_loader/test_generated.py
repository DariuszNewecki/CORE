from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from mind.governance.enforcement_loader import EnforcementMappingLoader


# ID: d777a10d-ce7e-4eb1-a11f-04a08126b1a5
def test_EnforcementMappingLoader_get_stats():
    loader = EnforcementMappingLoader(intent_root=Path("/tmp/intent"))

    mock_load = MagicMock()
    loader.load_all_mappings = mock_load

    loader._mappings_cache = {
        "map.a": {"engine": "sql"},
        "map.b": {"engine": "sql"},
        "map.c": {"engine": "grep"},
    }
    loader._loaded_files = {
        Path("/tmp/intent/enforcement/a.yaml"),
        Path("/tmp/intent/enforcement/b.yaml"),
    }
    loader._presets = {"preset1": {}}

    stats = loader.get_stats()

    mock_load.assert_not_called()
    assert stats == {
        "total_mappings": 3,
        "total_files": 2,
        "total_presets": 1,
        "engines_used": 2,
    }
