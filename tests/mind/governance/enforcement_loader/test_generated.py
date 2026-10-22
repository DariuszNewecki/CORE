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


from unittest.mock import patch


# ID: 0625abb6-f5c9-46b4-921b-35ce9ce63937
def test_EnforcementMappingLoader_get_enforcement_strategy():
    from mind.governance.enforcement_loader import EnforcementMappingLoader

    loader = EnforcementMappingLoader(intent_root=Path("/fake/.intent"))

    # Pre-populate the mappings cache so load_all_mappings() is NOT triggered,
    # isolating the happy-path behavior of get_enforcement_strategy.
    expected = {"strategy": "block", "level": "hard"}
    loader._mappings_cache = {"architecture.max_file_size": expected}

    with patch.object(loader, "load_all_mappings", MagicMock()) as mock_load:
        result = loader.get_enforcement_strategy("architecture.max_file_size")

    assert result == expected
    assert result is expected

    # Cache was non-empty, so loader should not have reloaded.
    mock_load.assert_not_called()

    # Unmapped rule returns None.
    assert loader.get_enforcement_strategy("unknown.rule") is None


# ID: 932c1ec8-f85d-45e7-b8cd-f7be6069e91c
def test_EnforcementMappingLoader_load_all_mappings(tmp_path: Path) -> None:
    intent_root = tmp_path / ".intent"
    enforcement_dir = intent_root / "enforcement"
    mappings_dir = enforcement_dir / "mappings"
    domain_dir = mappings_dir / "domain_a"
    domain_dir.mkdir(parents=True)

    yaml_file = domain_dir / "rules.yaml"
    yaml_file.write_text("placeholder: true\n", encoding="utf-8")

    loader = EnforcementMappingLoader(intent_root)

    fake_mappings = {
        "rule.one": {"strategy": "implement", "handler": "h1"},
        "rule.two": {"strategy": "declared_only"},
    }

    with patch.object(
        loader, "_load_mapping_file", return_value=fake_mappings
    ) as mock_load:
        result = loader.load_all_mappings()

    mock_load.assert_called_once_with(yaml_file)
    assert result == fake_mappings
    assert result is loader._mappings_cache
    assert yaml_file in loader._loaded_files




# ID: fada0b5f-f9ec-4b3a-91c0-99f67ee506dd
def test_EnforcementMappingLoader(tmp_path: Path) -> None:
    from mind.governance.enforcement_loader import EnforcementMappingLoader

    intent_root = tmp_path / ".intent"
    enforcement_dir = intent_root / "enforcement"
    mappings_dir = enforcement_dir / "mappings"
    presets_dir = enforcement_dir / "presets"
    mappings_dir.mkdir(parents=True)
    presets_dir.mkdir(parents=True)

    mapping_file = mappings_dir / "domain.yaml"
    mapping_file.write_text("mappings: {}\n")
    preset_file = presets_dir / "python_source.yaml"
    preset_file.write_text("name: python_source\napplies_to:\n  - 'src/**/*.py'\n")

    loader = EnforcementMappingLoader(intent_root)

    preset = {"name": "python_source", "applies_to": ["src/**/*.py"]}
    mapping_data = {
        "presets": {"python_source": "python_source"},
        "mappings": {
            "architecture.max_file_size": {
                "engine": "ast",
                "scope": "!ref python_source",
            },
            "architecture.no_cycles": {
                "engine": "graph",
                "scope": {"applies_to": ["src/**/*.py"]},
            },
        },
    }

    mock_processor = MagicMock()
    mock_processor.load_strict.side_effect = [mapping_data, preset]

    with patch(
        "mind.governance.enforcement_loader.strict_yaml_processor",
        mock_processor,
    ):
        result = loader.load_all_mappings()

        assert "architecture.max_file_size" in result
        assert result["architecture.max_file_size"]["engine"] == "ast"
        assert result["architecture.max_file_size"]["scope"] == preset
        assert "architecture.no_cycles" in result
        assert result["architecture.no_cycles"]["engine"] == "graph"

        assert (
            loader.get_enforcement_strategy("architecture.max_file_size")
            == result["architecture.max_file_size"]
        )

        stats = loader.get_stats()
        assert stats["total_mappings"] == 2
        assert stats["total_files"] == 1
        assert "engines_used" in stats
