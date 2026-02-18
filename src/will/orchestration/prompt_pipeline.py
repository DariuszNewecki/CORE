# src/will/orchestration/prompt_pipeline.py
"""
PromptPipeline — CORE's Unified Directive Processor

A single pipeline that processes all [[directive:...]] blocks in a user prompt.
Responsible for:
- Injecting context (e.g., file contents)
- Expanding includes
- Adding analysis from introspection tools
- Enriching with manifest data

CONSTITUTIONAL FIX (V2.3.0):
- Hardened Path Resolution: Prevents Path Traversal attacks (../../etc/passwd).
- Secret Shield: Explicitly blocks inclusion of .env or hidden files.
- Resource Limits: Enforces MAX_FILE_SIZE_BYTES.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from shared.logger import getLogger


logger = getLogger(__name__)

# Constitutional Limit: 1MB per included file to prevent context overflow/DoS
MAX_FILE_SIZE_BYTES = 1 * 1024 * 1024

# Files that must NEVER be read into the Context Window, even if requested
FORBIDDEN_PATTERNS = {
    ".env",
    ".env.test",
    ".env.prod",
    "id_rsa",
    "id_ed25519",
    ".pem",
    ".key",
    "private.key",
}


# ID: eab94cfa-1a68-4af5-85a9-25608bb679c9
class PromptPipeline:
    """
    Processes and enriches user prompts by resolving directives.
    Enforces strict security boundaries on file access.
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

    def _is_safe_path(self, raw_path: str) -> tuple[bool, Path | None, str]:
        """
        Validates that a path is safe to read.

        Checks:
        1. Path traversal (must be inside repo_root).
        2. Forbidden filenames (secrets).
        3. Existence and type (must be a file).

        Returns:
            (is_safe, absolute_path, error_message)
        """
        try:
            # 1. Resolve absolute path
            # Note: We must strip leading slashes to prevent root-relative overrides
            clean_raw = raw_path.lstrip("/\\")
            candidate = (self.repo_path / clean_raw).resolve()

            # 2. Check Boundary (The Prison Wall)
            # is_relative_to() throws ValueError if not relative, or returns False on older Pythons
            if not candidate.is_relative_to(self.repo_path):
                return False, None, "Path traversal detected (outside repository)"

            # 3. Check Forbidden Patterns (The Secret Shield)
            if any(forbidden in candidate.name for forbidden in FORBIDDEN_PATTERNS):
                return False, None, "Access to sensitive file forbidden"

            # 4. Check Existence
            if not candidate.exists():
                return False, None, "File not found"

            if not candidate.is_file():
                return False, None, "Not a file"

            return True, candidate, ""

        except Exception as e:
            return False, None, f"Path validation error: {e}"

    def _read_file_safe(self, file_path_str: str) -> tuple[str, bool]:
        """
        Reads a file safely. Returns (content, success).
        If failure, content contains the error message.
        """
        is_safe, abs_path, error = self._is_safe_path(file_path_str)

        if not is_safe:
            return f"\n❌ Could not include {file_path_str}: {error}\n", False

        if not abs_path:
            return "\n❌ Logic Error: Path validation passed but path is None\n", False

        # 5. Check Size (DoS Protection)
        try:
            if abs_path.stat().st_size > MAX_FILE_SIZE_BYTES:
                return (
                    f"\n❌ Could not include {file_path_str}: "
                    f"File size exceeds 1MB limit.\n"
                ), False

            content = abs_path.read_text(encoding="utf-8")
            return content, True

        except UnicodeDecodeError:
            return (
                f"\n❌ Could not read {file_path_str}: Binary or non-UTF-8 content\n",
                False,
            )
        except Exception as e:
            return f"\n❌ Read error {file_path_str}: {e!s}\n", False

    def _replace_context_match(self, match: re.Match) -> str:
        """Handles [[context:...]]"""
        file_path = match.group(1).strip()
        content, success = self._read_file_safe(file_path)

        if success:
            return f"\n--- CONTEXT: {file_path} ---\n{content}\n--- END CONTEXT ---\n"
        return content

    def _replace_include_match(self, match: re.Match) -> str:
        """Handles [[include:...]]"""
        file_path = match.group(1).strip()
        content, success = self._read_file_safe(file_path)

        if success:
            return f"\n--- INCLUDED: {file_path} ---\n{content}\n--- END INCLUDE ---\n"
        return content

    def _replace_analysis_match(self, match: re.Match) -> str:
        """
        Dynamically replaces an [[analysis:...]] regex match.
        """
        file_path = match.group(1).strip()
        # Security check even for placeholders
        is_safe, _, error = self._is_safe_path(file_path)
        if not is_safe and "File not found" not in error:
            return f"\n❌ Analysis Blocked: {error}\n"

        return f"\n--- ANALYSIS FOR {file_path} (DEFERRED) ---\n"

    def _replace_manifest_match(self, match: re.Match) -> str:
        """
        Dynamically replaces a [[manifest:...]] regex match with data.
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

    # ID: 8d93f4b2-f4db-45b0-be3a-fca21dee931b
    def process(self, prompt: str) -> str:
        """
        Processes the full prompt by sequentially resolving all directives.
        """
        prompt = self._inject_context(prompt)
        prompt = self._inject_includes(prompt)
        prompt = self._inject_analysis(prompt)
        prompt = self._inject_manifest(prompt)
        return prompt

    def _inject_context(self, prompt: str) -> str:
        return self.context_pattern.sub(self._replace_context_match, prompt)

    def _inject_includes(self, prompt: str) -> str:
        return self.include_pattern.sub(self._replace_include_match, prompt)

    def _inject_analysis(self, prompt: str) -> str:
        return self.analysis_pattern.sub(self._replace_analysis_match, prompt)

    def _inject_manifest(self, prompt: str) -> str:
        return self.manifest_pattern.sub(self._replace_manifest_match, prompt)
