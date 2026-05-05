"""ADR-025: CoderAgent.__init__ pass-through of context_builder to CodeGenerator.

Verifies the boundary contract: when CoderAgent is constructed with a
non-None context_builder, that instance reaches its internal CodeGenerator
and CodeGenerator.semantic_enabled becomes True. The test does NOT exercise
build_context() or any LLM path — it asserts the wiring only.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

# body.atomic must finish loading before will.workers / will.agents pulls
# in will.autonomy.proposal — pre-existing body.atomic ↔ will.autonomy
# circular import surfaces during isolated collection otherwise.
import body.atomic  # noqa: F401  -- import-order side effect, not a usage
from will.agents.coder_agent import CoderAgent


_REPO_ROOT = Path(__file__).resolve().parents[3]


# ID: efe31f65-c4fc-4ff7-85c4-8524b6ef2be8
def test_coder_agent_passes_context_builder_to_code_generator() -> None:
    """A non-None context_builder reaches CodeGenerator and flips semantic_enabled."""
    sentinel_builder = MagicMock(name="ArchitecturalContextBuilder")

    coder = CoderAgent(
        cognitive_service=MagicMock(name="CognitiveProtocol"),
        executor=MagicMock(name="ActionExecutorProtocol"),
        prompt_pipeline=MagicMock(name="PromptPipeline"),
        auditor_context=MagicMock(name="AuditorContext"),
        repo_root=_REPO_ROOT,
        context_builder=sentinel_builder,
    )

    assert coder.context_builder is sentinel_builder
    assert coder.code_generator.context_builder is sentinel_builder
    assert coder.code_generator.semantic_enabled is True


# ID: 8fe7c3a2-02e0-4075-a637-2b43637805c7
def test_coder_agent_default_context_builder_leaves_semantic_disabled() -> None:
    """Omitting context_builder keeps the legacy fallback path intact."""
    coder = CoderAgent(
        cognitive_service=MagicMock(name="CognitiveProtocol"),
        executor=MagicMock(name="ActionExecutorProtocol"),
        prompt_pipeline=MagicMock(name="PromptPipeline"),
        auditor_context=MagicMock(name="AuditorContext"),
        repo_root=_REPO_ROOT,
    )

    assert coder.context_builder is None
    assert coder.code_generator.context_builder is None
    assert coder.code_generator.semantic_enabled is False
