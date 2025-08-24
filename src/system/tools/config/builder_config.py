# src/system/tools/config/builder_config.py
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set

from shared.config_loader import load_config
from shared.logger import getLogger

log = getLogger(__name__)


@dataclass
class BuilderConfig:
    """Centralized configuration for the knowledge graph builder."""

    root_path: Path
    src_root: Path
    exclude_patterns: List[str]
    domain_map: Dict[str, str]
    cli_entry_points: Set[str]
    patterns: List[Dict]

    @classmethod
    def from_project(cls, root_path: Path) -> "BuilderConfig":
        """Factory method to load configuration from project files."""
        root_path = root_path.resolve()
        src_root = root_path / "src"

        return cls(
            root_path=root_path,
            src_root=src_root,
            exclude_patterns=cls._load_exclude_patterns(),
            domain_map=cls._load_domain_map(root_path, src_root),
            cli_entry_points=cls._load_cli_entry_points(root_path),
            patterns=cls._load_patterns(root_path),
        )

    @staticmethod
    def _load_exclude_patterns() -> List[str]:
        """Load default exclude patterns."""
        return ["venv", ".venv", "__pycache__", ".git", "tests", "work"]

    @staticmethod
    def _load_patterns(root_path: Path) -> List[Dict]:
        """Load entry point detection patterns from configuration."""
        patterns_path = root_path / ".intent/knowledge/entry_point_patterns.yaml"
        if not patterns_path.exists():
            log.warning("entry_point_patterns.yaml not found.")
            return []
        return load_config(patterns_path, "yaml").get("patterns", [])

    @staticmethod
    def _load_cli_entry_points(root_path: Path) -> Set[str]:
        """Parse pyproject.toml to find declared command-line entry points."""
        pyproject_path = root_path / "pyproject.toml"
        if not pyproject_path.exists():
            return set()

        try:
            content = pyproject_path.read_text(encoding="utf-8")
            match = re.search(r"\[tool\.poetry\.scripts\]([^\[]*)", content, re.DOTALL)
            if match:
                return set(re.findall(r'=\s*"[^"]+:(\w+)"', match.group(1)))
        except Exception as e:
            log.error(f"Error parsing pyproject.toml: {e}")

        return set()

    @staticmethod
    def _load_domain_map(root_path: Path, src_root: Path) -> Dict[str, str]:
        """Load domain-to-path mapping from configuration."""
        path = root_path / ".intent/knowledge/source_structure.yaml"
        data = load_config(path, "yaml")
        structure = data.get("structure")

        if not structure:
            return BuilderConfig._infer_domains_from_directory_structure(src_root)

        return {
            Path(e["path"]).as_posix(): e["domain"]
            for e in structure
            if "path" in e and "domain" in e
        }

    @staticmethod
    def _infer_domains_from_directory_structure(src_root: Path) -> Dict[str, str]:
        """Heuristic to guess domains from directory structure."""
        log.warning(
            "source_structure.yaml not found. Falling back to directory-based domain inference."
        )

        if not src_root.is_dir():
            log.warning("`src` directory not found. Cannot infer domains.")
            return {}

        domain_map = {}
        for item in src_root.iterdir():
            if item.is_dir() and not item.name.startswith(("_", ".")):
                domain_name = item.name
                domain_path = Path("src") / domain_name
                domain_map[domain_path.as_posix()] = domain_name

        log.info(f"Inferred {len(domain_map)} domains from `src/` directory structure.")
        return domain_map
