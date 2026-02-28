# src/cli/logic/interactive_test/session.py
# ID: 81af2623-d91d-40b6-8aa4-04018d46edc7

"""
Interactive test generation session management.
All mutations route through FileHandler (governed mutation surface).
"""

from __future__ import annotations

import difflib
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console

from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger


logger = getLogger(__name__)
console = Console()


# ID: 81af2623-d91d-40b6-8aa4-04018d46edc7
class InteractiveSession:
    """
    Manages an interactive test generation session.
    Saves all artifacts using the governed FileHandler mutation surface.
    """

    def __init__(self, target_file: str, repo_root: Path):
        """Initialize interactive session."""
        self.target_file = target_file
        self.repo_root = repo_root

        self.file_handler = FileHandler(str(repo_root))

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.rel_session_dir = f"work/interactive/{timestamp}"
        self.session_dir = repo_root / self.rel_session_dir

        self.file_handler.ensure_dir(self.rel_session_dir)

        self.artifacts: dict[str, Path] = {}
        self.decisions: list[dict[str, Any]] = []

        logger.info("📂 Interactive session created: %s", self.session_dir)

    # ID: 57038d43-1323-4e53-abe6-cc9a06c6ec46
    def save_artifact(self, name: str, content: str) -> Path:
        """Save an artifact using the governed FileHandler."""
        rel_path = f"{self.rel_session_dir}/{name}"
        self.file_handler.write_runtime_text(rel_path, content)
        path = self.repo_root / rel_path
        self.artifacts[name] = path
        logger.info("💾 Saved artifact: %s", name)
        return path

    # ID: dc36e9dc-6e01-4ab4-a69b-d04f776cbabe
    def save_decision(self, step: str, choice: str, metadata: dict[str, Any]) -> None:
        """Record a user decision."""
        self.decisions.append(
            {
                "timestamp": datetime.now().isoformat(),
                "step": step,
                "choice": choice,
                "metadata": metadata,
            }
        )

    # ID: 083e0dc8-9f3b-4935-8a09-6f68cef50031
    def generate_diff(self, old_name: str, new_name: str) -> str:
        """Generate and save diff between two artifacts."""
        old_path = self.artifacts.get(old_name)
        new_path = self.artifacts.get(new_name)

        if not old_path or not new_path:
            return "Diff not available (missing artifacts)"

        old_lines = old_path.read_text(encoding="utf-8").splitlines(keepends=True)
        new_lines = new_path.read_text(encoding="utf-8").splitlines(keepends=True)

        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=old_name,
            tofile=new_name,
        )

        diff_content = "".join(diff)
        rel_diff_path = f"{self.rel_session_dir}/{old_name}_to_{new_name}.diff"
        self.file_handler.write_runtime_text(rel_diff_path, diff_content)

        return diff_content

    # ID: ed6926b4-a3a3-4e21-9bc2-4b399a70fb19
    def finalize(self) -> None:
        """Save final session metadata via FileHandler."""
        rel_decisions_path = f"{self.rel_session_dir}/decisions.json"
        self.file_handler.write_runtime_json(rel_decisions_path, self.decisions)

        rel_summary_path = f"{self.rel_session_dir}/session.log"
        summary = [
            "Interactive Test Generation Session",
            f"Target: {self.target_file}",
            f"Started: {self.decisions[0]['timestamp'] if self.decisions else 'none'}",
            f"Completed: {datetime.now().isoformat()}",
            "",
            "Artifacts:",
        ]
        for name, path in self.artifacts.items():
            summary.append(f"  - {name}: {path}")

        self.file_handler.write_runtime_text(rel_summary_path, "\n".join(summary))

        console.print(
            f"\n📂 Session artifacts saved to: [cyan]{self.session_dir}[/cyan]"
        )
