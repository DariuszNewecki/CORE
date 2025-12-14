# src/will/orchestration/prompt_pipeline.py
"""
PromptPipeline — CORE's Unified Directive Processor

A single pipeline that processes all [[directive:...]] blocks in a user prompt.
Responsible for:
- Injecting context (e.g., file contents)
- Expanding includes
- Adding analysis from introspection tools
- Enriching with manifest data

This is the central "pre-processor" for all LLM interactions.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml


# --- FIX: Define a constant for a reasonable file size limit (1MB) ---
MAX_FILE_SIZE_BYTES = 1 * 1024 * 1024


# ID: 55fc4bff-0f88-435c-b988-23861ee401e8
class PromptPipeline:
    """
    Processes and enriches user prompts by resolving directives like
    [[include:...]] and [[analysis:...]]. Ensures the LLM receives full
    context before generating code.
    """

    def __init__(self, repo_path: Path):
        """
        Initialize PromptPipeline with repository root.

        Args:
            repo_path (Path): Root path of the repository.
        """
        self.repo_path = Path(repo_path).resolve()

        # Regex patterns for directive matching
        self.context_pattern = re.compile(r"\[\[context:(.+?)\]\]")
        self.include_pattern = re.compile(r"\[\[include:(.+?)\]\]")
        self.analysis_pattern = re.compile(r"\[\[analysis:(.+?)\]\]")
        self.manifest_pattern = re.compile(r"\[\[manifest:(.+?)\]\]")

    def _replace_context_match(self, match: re.Match) -> str:
        """
        Dynamically replaces a [[context:...]] regex match with file content
        or an error message if the file is missing, unreadable, or exceeds
        size limits.
        """
        file_path = match.group(1).strip()
        abs_path = self.repo_path / file_path
        if abs_path.exists() and abs_path.is_file():
            # --- FIX: Add file size check to prevent memory bloat ---
            if abs_path.stat().st_size > MAX_FILE_SIZE_BYTES:
                return (
                    f"\n❌ Could not include {file_path}: "
                    f"File size exceeds 1MB limit.\n"
                )
            try:
                content = abs_path.read_text(encoding="utf-8")
                return (
                    f"\n--- CONTEXT: {file_path} ---\n{content}\n--- END CONTEXT ---\n"
                )
            except Exception as e:
                return f"\n❌ Could not read {file_path}: {str(e)}\n"
        return f"\n❌ File not found: {file_path}\n"

    def _inject_context(self, prompt: str) -> str:
        """Replaces [[context:file.py]] directives with actual file content."""
        return self.context_pattern.sub(self._replace_context_match, prompt)

    def _replace_include_match(self, match: re.Match) -> str:
        """
        Dynamically replaces an [[include:...]] regex match with file content
        or an error message if the file is missing, unreadable, or exceeds
        size limits.
        """
        file_path = match.group(1).strip()
        abs_path = self.repo_path / file_path
        if abs_path.exists() and abs_path.is_file():
            # --- FIX: Add file size check to prevent memory bloat ---
            if abs_path.stat().st_size > MAX_FILE_SIZE_BYTES:
                return (
                    f"\n❌ Could not include {file_path}: "
                    f"File size exceeds 1MB limit.\n"
                )
            try:
                content = abs_path.read_text(encoding="utf-8")
                return (
                    f"\n--- INCLUDED: {file_path} ---\n{content}\n--- END INCLUDE ---\n"
                )
            except Exception as e:
                return f"\n❌ Could not read {file_path}: {str(e)}\n"
        return f"\n❌ File not found: {file_path}\n"

    def _inject_includes(self, prompt: str) -> str:
        """Replaces [[include:file.py]] directives with file content."""
        return self.include_pattern.sub(self._replace_include_match, prompt)

    def _replace_analysis_match(self, match: re.Match) -> str:
        """
        Dynamically replaces an [[analysis:...]] regex match with a
        placeholder analysis message for the given file path.
        """
        file_path = match.group(1).strip()
        # This functionality is a placeholder.
        return f"\n--- ANALYSIS FOR {file_path} (DEFERRED) ---\n"

    def _inject_analysis(self, prompt: str) -> str:
        """Replaces [[analysis:file.py]] directives with code analysis."""
        return self.analysis_pattern.sub(self._replace_analysis_match, prompt)

    def _replace_manifest_match(self, match: re.Match) -> str:
        """
        Dynamically replaces a [[manifest:...]] regex match with
        manifest data or an error.
        """
        manifest_path = self.repo_path / ".intent" / "project_manifest.yaml"
        if not manifest_path.exists():
            return f"\n❌ Manifest file not found at {manifest_path}\n"

        try:
            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return f"\n❌ Could not parse manifest file at {manifest_path}\n"

        field = match.group(1).strip()
        value = manifest
        # Improved logic for nested key access
        for key in field.split("."):
            value = value.get(key) if isinstance(value, dict) else None
            if value is None:
                break

        if value is None:
            return f"\n❌ Manifest field not found: {field}\n"

        # Pretty print for better context
        if isinstance(value, (dict, list)):
            value_str = yaml.dump(value, indent=2)
        else:
            value_str = str(value)

        return f"\n--- MANIFEST: {field} ---\n{value_str}\n--- END MANIFEST ---\n"

    def _inject_manifest(self, prompt: str) -> str:
        """
        Replaces [[manifest:field]] directives with data from
        project_manifest.yaml.
        """
        return self.manifest_pattern.sub(self._replace_manifest_match, prompt)

    # ID: 05c566aa-d219-49bd-8b74-daa023b81e46
    def process(self, prompt: str) -> str:
        """
        Processes the full prompt by sequentially resolving all directives.
        This is the main entry point for prompt enrichment.
        """
        prompt = self._inject_context(prompt)
        prompt = self._inject_includes(prompt)
        prompt = self._inject_analysis(prompt)
        prompt = self._inject_manifest(prompt)
        return prompt
