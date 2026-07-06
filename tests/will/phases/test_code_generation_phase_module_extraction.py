# tests/will/phases/test_code_generation_phase_module_extraction.py
"""Tests for CodeGenerationPhase._extract_module_sources (fix for #753)."""
from __future__ import annotations

from pathlib import Path

from will.phases.code_generation_phase import CodeGenerationPhase


# ID: b5ef4276-46f4-4f37-ae66-b74103b03bff
class TestExtractModuleSources:
    """_extract_module_sources parses ImportError / TypeError tracebacks."""

    # ID: 113edb3c-dcc9-4f04-bcc9-136cd7207042
    def test_import_error_module_resolved(self, tmp_path: Path) -> None:
        src = tmp_path / "src" / "will" / "agents" / "effects.py"
        src.parent.mkdir(parents=True)
        src.write_text("def persist_campaign(): pass\n")

        pain = (
            "ImportError: cannot import name 'apply_code_modification_effects' "
            "from 'will.agents.effects'"
        )
        result = CodeGenerationPhase._extract_module_sources(pain, tmp_path)

        assert result is not None
        assert "persist_campaign" in result
        assert "will/agents/effects.py" in result

    # ID: 1b59c36e-52b1-4df6-8b8a-d59589958e21
    def test_no_match_returns_none(self, tmp_path: Path) -> None:
        pain = "TypeError: InterpretPhase.__init__() missing 1 required positional argument"
        result = CodeGenerationPhase._extract_module_sources(pain, tmp_path)
        assert result is None

    def test_traceback_file_line_resolved(self, tmp_path: Path) -> None:
        src = tmp_path / "src" / "will" / "interpret_phase.py"
        src.parent.mkdir(parents=True)
        src.write_text("class InterpretPhase:\n    def __init__(self, context): ...\n")

        pain = f'File "{src}", line 5, in <module>'
        result = CodeGenerationPhase._extract_module_sources(pain, tmp_path)

        assert result is not None
        assert "InterpretPhase" in result

    def test_missing_module_file_skipped_gracefully(self, tmp_path: Path) -> None:
        pain = "ImportError: cannot import name 'X' from 'will.nonexistent.module'"
        result = CodeGenerationPhase._extract_module_sources(pain, tmp_path)
        assert result is None

    def test_multiple_sources_combined(self, tmp_path: Path) -> None:
        for name in ("alpha", "beta"):
            f = tmp_path / "src" / "pkg" / f"{name}.py"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(f"def {name}_fn(): pass\n")

        pain = (
            "ImportError: cannot import name 'x' from 'pkg.alpha'\n"
            f'File "{tmp_path}/src/pkg/beta.py", line 1, in <module>'
        )
        result = CodeGenerationPhase._extract_module_sources(pain, tmp_path)

        assert result is not None
        assert "alpha_fn" in result
        assert "beta_fn" in result
