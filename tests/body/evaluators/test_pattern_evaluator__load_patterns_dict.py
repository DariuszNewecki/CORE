"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/body/evaluators/pattern_evaluator.py
- Symbol: load_patterns_dict
- Status: 7 tests passed, some failed
- Passing tests: test_load_patterns_dict_empty_when_directory_missing, test_load_patterns_dict_loads_single_file, test_load_patterns_dict_uses_file_stem_when_id_missing, test_load_patterns_dict_loads_multiple_files, test_load_patterns_dict_ignores_non_matching_files, test_load_patterns_dict_continues_on_invalid_yaml, test_load_patterns_dict_complex_yaml_structure
- Generated: 2026-01-11 03:19:40
"""

import tempfile
from pathlib import Path

import yaml

from body.evaluators.pattern_evaluator import load_patterns_dict


def test_load_patterns_dict_empty_when_directory_missing():
    """Test that empty dict is returned when patterns directory doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        result = load_patterns_dict(repo_root)
        assert result == {}


def test_load_patterns_dict_loads_single_file():
    """Test loading a single patterns YAML file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        patterns_dir = Path(tmpdir) / ".intent" / "charter" / "patterns"
        patterns_dir.mkdir(parents=True)
        pattern_data = {
            "id": "test_category",
            "patterns": ["test pattern 1", "test pattern 2"],
        }
        pattern_file = patterns_dir / "test_patterns.yaml"
        with open(pattern_file, "w") as f:
            yaml.dump(pattern_data, f)
        result = load_patterns_dict(Path(tmpdir))
        assert result == {"test_category": pattern_data}


def test_load_patterns_dict_uses_file_stem_when_id_missing():
    """Test that file stem is used as category when 'id' field is missing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        patterns_dir = Path(tmpdir) / ".intent" / "charter" / "patterns"
        patterns_dir.mkdir(parents=True)
        pattern_data = {"patterns": ["pattern without id"]}
        pattern_file = patterns_dir / "custom_patterns.yaml"
        with open(pattern_file, "w") as f:
            yaml.dump(pattern_data, f)
        result = load_patterns_dict(Path(tmpdir))
        assert result == {"custom_patterns": pattern_data}


def test_load_patterns_dict_loads_multiple_files():
    """Test loading multiple patterns files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        patterns_dir = Path(tmpdir) / ".intent" / "charter" / "patterns"
        patterns_dir.mkdir(parents=True)
        pattern_data1 = {"id": "category1", "patterns": ["p1"]}
        pattern_data2 = {"id": "category2", "patterns": ["p2"]}
        with open(patterns_dir / "cat1_patterns.yaml", "w") as f:
            yaml.dump(pattern_data1, f)
        with open(patterns_dir / "cat2_patterns.yaml", "w") as f:
            yaml.dump(pattern_data2, f)
        result = load_patterns_dict(Path(tmpdir))
        assert result == {"category1": pattern_data1, "category2": pattern_data2}


def test_load_patterns_dict_ignores_non_matching_files():
    """Test that only files matching '*_patterns.yaml' are loaded."""
    with tempfile.TemporaryDirectory() as tmpdir:
        patterns_dir = Path(tmpdir) / ".intent" / "charter" / "patterns"
        patterns_dir.mkdir(parents=True)
        pattern_data = {"id": "valid", "patterns": ["valid"]}
        with open(patterns_dir / "valid_patterns.yaml", "w") as f:
            yaml.dump(pattern_data, f)
        with open(patterns_dir / "other.yaml", "w") as f:
            yaml.dump({"id": "ignored"}, f)
        with open(patterns_dir / "patterns.txt", "w") as f:
            f.write("text file")
        result = load_patterns_dict(Path(tmpdir))
        assert result == {"valid": pattern_data}


def test_load_patterns_dict_continues_on_invalid_yaml():
    """Test that function continues processing other files when one has invalid YAML."""
    with tempfile.TemporaryDirectory() as tmpdir:
        patterns_dir = Path(tmpdir) / ".intent" / "charter" / "patterns"
        patterns_dir.mkdir(parents=True)
        with open(patterns_dir / "invalid_patterns.yaml", "w") as f:
            f.write("invalid: yaml: [")
        valid_data = {"id": "valid", "patterns": ["ok"]}
        with open(patterns_dir / "valid_patterns.yaml", "w") as f:
            yaml.dump(valid_data, f)
        result = load_patterns_dict(Path(tmpdir))
        assert result == {"valid": valid_data}


def test_load_patterns_dict_complex_yaml_structure():
    """Test loading YAML with complex nested structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        patterns_dir = Path(tmpdir) / ".intent" / "charter" / "patterns"
        patterns_dir.mkdir(parents=True)
        complex_data = {
            "id": "complex",
            "patterns": [
                {"name": "pattern1", "regex": "\\d+"},
                {"name": "pattern2", "regex": "[a-z]+"},
            ],
            "metadata": {"author": "test", "version": 1.0},
        }
        with open(patterns_dir / "complex_patterns.yaml", "w") as f:
            yaml.dump(complex_data, f)
        result = load_patterns_dict(Path(tmpdir))
        assert result == {"complex": complex_data}
