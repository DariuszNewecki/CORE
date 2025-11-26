"""
Test suite for CoderAgentV1 class.

This module tests the enhanced code generation agent with semantic infrastructure.
"""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from will.agents.coder_agent_v1 import CoderAgentV1
from will.tools.architectural_context_builder import ArchitecturalContext


class TestCoderAgentV1Initialization:
    """Test CoderAgentV1 initialization."""

    @pytest.fixture
    def mock_repo_root(self):
        """Return mock repository root."""
        return Path("/mock/repo")

    @pytest.fixture
    def mock_cognitive_service(self):
        """Return mock cognitive service."""
        return Mock()

    @pytest.fixture
    def mock_qdrant_service(self):
        """Return mock Qdrant service."""
        return Mock()

    def test_initialization_creates_components(
        self, mock_repo_root, mock_cognitive_service, mock_qdrant_service
    ):
        """Test that initialization creates all required components."""
        agent = CoderAgentV1(
            repo_root=mock_repo_root,
            cognitive_service=mock_cognitive_service,
            qdrant_service=mock_qdrant_service,
        )

        assert agent.repo_root == mock_repo_root
        assert agent.cognitive_service == mock_cognitive_service
        assert agent.qdrant_service == mock_qdrant_service
        assert hasattr(agent, "policy_vectorizer")
        assert hasattr(agent, "module_anchor_generator")
        assert hasattr(agent, "context_builder")

    def test_initialization_with_auditor_context(
        self, mock_repo_root, mock_cognitive_service, mock_qdrant_service
    ):
        """Test initialization with optional auditor context."""
        mock_auditor = Mock()

        agent = CoderAgentV1(
            repo_root=mock_repo_root,
            cognitive_service=mock_cognitive_service,
            qdrant_service=mock_qdrant_service,
            auditor_context=mock_auditor,
        )

        assert agent.auditor_context == mock_auditor

    @patch("will.agents.coder_agent_v1.logger")
    def test_initialization_logs_message(
        self, mock_logger, mock_repo_root, mock_cognitive_service, mock_qdrant_service
    ):
        """Test that initialization logs info message."""
        CoderAgentV1(
            repo_root=mock_repo_root,
            cognitive_service=mock_cognitive_service,
            qdrant_service=mock_qdrant_service,
        )

        mock_logger.info.assert_called_with(
            "CoderAgentV1 initialized with semantic infrastructure"
        )


class TestCoderAgentV1Generate:
    """Test CoderAgentV1.generate method."""

    @pytest.fixture
    def mock_agent(self):
        """Create mock agent with mocked dependencies."""
        agent = Mock(spec=CoderAgentV1)
        agent.context_builder = Mock()
        agent.cognitive_service = Mock()

        # Bind the actual methods to the mock
        agent.generate = CoderAgentV1.generate.__get__(agent, CoderAgentV1)
        agent._build_enhanced_prompt = CoderAgentV1._build_enhanced_prompt.__get__(
            agent, CoderAgentV1
        )
        agent._call_llm = CoderAgentV1._call_llm.__get__(agent, CoderAgentV1)
        agent._extract_code = CoderAgentV1._extract_code.__get__(agent, CoderAgentV1)

        return agent

    @pytest.fixture
    def mock_arch_context(self):
        """Create mock architectural context."""
        return ArchitecturalContext(
            goal="Create a validator",
            target_layer="domain",
            layer_purpose="Business logic and domain rules",
            layer_patterns=["Pure functions", "No side effects"],
            placement_score=0.85,
            placement_confidence="high",
            relevant_policies=[{"content": "test policy"}],
            best_module_path="src/domain",
        )

    @pytest.mark.asyncio
    async def test_generate_calls_context_builder(self, mock_agent, mock_arch_context):
        """Test that generate calls context builder."""
        mock_agent.context_builder.build_context = AsyncMock(
            return_value=mock_arch_context
        )
        mock_agent.context_builder.format_for_prompt = Mock(return_value="# Context\n")
        mock_agent.cognitive_service.aget_client_for_role = AsyncMock()
        mock_client = AsyncMock()
        mock_client.make_request_async = AsyncMock(return_value="def test(): pass")
        mock_agent.cognitive_service.aget_client_for_role.return_value = mock_client

        result = await mock_agent.generate(
            goal="Create a validator",
            target_file="src/domain/validator.py",
        )

        mock_agent.context_builder.build_context.assert_called_once_with(
            goal="Create a validator",
            target_file="src/domain/validator.py",
        )

    @pytest.mark.asyncio
    async def test_generate_returns_code_string(self, mock_agent, mock_arch_context):
        """Test that generate returns extracted code."""
        mock_agent.context_builder.build_context = AsyncMock(
            return_value=mock_arch_context
        )
        mock_agent.context_builder.format_for_prompt = Mock(return_value="# Context\n")
        mock_agent.cognitive_service.aget_client_for_role = AsyncMock()
        mock_client = AsyncMock()
        mock_client.make_request_async = AsyncMock(
            return_value="```python\ndef validator(): pass\n```"
        )
        mock_agent.cognitive_service.aget_client_for_role.return_value = mock_client

        result = await mock_agent.generate(
            goal="Create a validator",
            target_file="src/domain/validator.py",
        )

        assert isinstance(result, str)
        assert "def validator():" in result

    @pytest.mark.asyncio
    async def test_generate_with_symbol_name(self, mock_agent, mock_arch_context):
        """Test generate with optional symbol_name parameter."""
        mock_agent.context_builder.build_context = AsyncMock(
            return_value=mock_arch_context
        )
        mock_agent.context_builder.format_for_prompt = Mock(return_value="# Context\n")
        mock_agent.cognitive_service.aget_client_for_role = AsyncMock()
        mock_client = AsyncMock()
        mock_client.make_request_async = AsyncMock(return_value="def validate(): pass")
        mock_agent.cognitive_service.aget_client_for_role.return_value = mock_client

        result = await mock_agent.generate(
            goal="Create a validator",
            target_file="src/domain/validator.py",
            symbol_name="validate_email",
        )

        assert isinstance(result, str)


class TestCoderAgentV1ExtractCode:
    """Test CoderAgentV1._extract_code method."""

    @pytest.fixture
    def mock_agent(self):
        """Create minimal mock agent."""
        agent = Mock(spec=CoderAgentV1)
        agent._extract_code = CoderAgentV1._extract_code.__get__(agent, CoderAgentV1)
        return agent

    def test_extract_code_from_python_block(self, mock_agent):
        """Test extraction from ```python block."""
        response = """Here's the code:

```python
def test():
    pass
```"""
        result = mock_agent._extract_code(response)
        assert result == "def test():\n    pass"

    def test_extract_code_from_generic_block(self, mock_agent):
        """Test extraction from generic ``` block."""
        response = """```
def test():
    pass
```"""
        result = mock_agent._extract_code(response)
        assert result == "def test():\n    pass"

    def test_extract_code_plain_text(self, mock_agent):
        """Test extraction from plain code without blocks."""
        response = "def test():\n    pass"
        result = mock_agent._extract_code(response)
        assert result == "def test():\n    pass"

    def test_extract_code_strips_whitespace(self, mock_agent):
        """Test that extraction strips leading/trailing whitespace."""
        response = """

        def test():
            pass

        """
        result = mock_agent._extract_code(response)
        assert result == "def test():\n            pass"


class TestCoderAgentV1BuildPrompt:
    """Test CoderAgentV1._build_enhanced_prompt method."""

    @pytest.fixture
    def mock_agent(self):
        """Create mock agent with context builder."""
        agent = Mock(spec=CoderAgentV1)
        agent.context_builder = Mock()
        agent.context_builder.format_for_prompt = Mock(
            return_value="# Architectural Context\n"
        )
        agent._build_enhanced_prompt = CoderAgentV1._build_enhanced_prompt.__get__(
            agent, CoderAgentV1
        )
        return agent

    @pytest.fixture
    def mock_arch_context(self):
        """Create mock architectural context."""
        return ArchitecturalContext(
            goal="Create a validator",
            target_layer="domain",
            layer_purpose="Business logic and domain rules",
            layer_patterns=["Pure functions", "No side effects"],
            placement_score=0.85,
            placement_confidence="high",
            relevant_policies=[],
            best_module_path="src/domain",
        )

    def test_build_prompt_includes_task(self, mock_agent, mock_arch_context):
        """Test that prompt includes task description."""
        prompt = mock_agent._build_enhanced_prompt(
            goal="Create a validator",
            arch_context=mock_arch_context,
            symbol_name=None,
            context_hints=None,
        )

        assert "## Task" in prompt
        assert "Create a validator" in prompt

    def test_build_prompt_includes_symbol_name(self, mock_agent, mock_arch_context):
        """Test that prompt includes symbol name when provided."""
        prompt = mock_agent._build_enhanced_prompt(
            goal="Create a validator",
            arch_context=mock_arch_context,
            symbol_name="validate_email",
            context_hints=None,
        )

        assert "validate_email" in prompt

    def test_build_prompt_includes_code_standards(self, mock_agent, mock_arch_context):
        """Test that prompt includes code standards."""
        prompt = mock_agent._build_enhanced_prompt(
            goal="Create a validator",
            arch_context=mock_arch_context,
            symbol_name=None,
            context_hints=None,
        )

        assert "## Code Standards" in prompt
        assert "Docstrings" in prompt
        assert "Type Hints" in prompt

    def test_build_prompt_includes_context_hints(self, mock_agent, mock_arch_context):
        """Test that prompt includes context hints when provided."""
        hints = {"similar_code": "examples.py", "dependencies": "validator"}

        prompt = mock_agent._build_enhanced_prompt(
            goal="Create a validator",
            arch_context=mock_arch_context,
            symbol_name=None,
            context_hints=hints,
        )

        assert "## Additional Context" in prompt
        assert "similar_code" in prompt
        assert "examples.py" in prompt


class TestCoderAgentV1CallLLM:
    """Test CoderAgentV1._call_llm method."""

    @pytest.fixture
    def mock_agent(self):
        """Create mock agent with cognitive service."""
        agent = Mock(spec=CoderAgentV1)
        agent.cognitive_service = Mock()
        agent._call_llm = CoderAgentV1._call_llm.__get__(agent, CoderAgentV1)
        return agent

    @pytest.mark.asyncio
    async def test_call_llm_success(self, mock_agent):
        """Test successful LLM call."""
        mock_client = AsyncMock()
        mock_client.make_request_async = AsyncMock(return_value="def test(): pass")
        mock_agent.cognitive_service.aget_client_for_role = AsyncMock(
            return_value=mock_client
        )

        result = await mock_agent._call_llm("Generate code")

        assert result == "def test(): pass"
        mock_agent.cognitive_service.aget_client_for_role.assert_called_once_with(
            "Coder"
        )

    @pytest.mark.asyncio
    async def test_call_llm_failure(self, mock_agent):
        """Test LLM call failure handling."""
        mock_agent.cognitive_service.aget_client_for_role = AsyncMock(
            side_effect=Exception("LLM error")
        )

        with pytest.raises(Exception, match="LLM error"):
            await mock_agent._call_llm("Generate code")


class TestArchitecturalContextDataclass:
    """Test ArchitecturalContext dataclass."""

    def test_architectural_context_creation(self):
        """Test creating an ArchitecturalContext instance."""
        from will.tools.architectural_context_builder import ArchitecturalContext

        context = ArchitecturalContext(
            goal="Test goal",
            target_layer="domain",
            layer_purpose="Business logic",
            layer_patterns=["pattern1", "pattern2"],
            relevant_policies=[{"id": "policy1"}],
            placement_confidence="high",
            best_module_path="src/domain",
            placement_score=0.95,
        )

        assert context.goal == "Test goal"
        assert context.target_layer == "domain"
        assert context.layer_purpose == "Business logic"
        assert len(context.layer_patterns) == 2
        assert len(context.relevant_policies) == 1
        assert context.placement_confidence == "high"
        assert context.best_module_path == "src/domain"
        assert context.placement_score == 0.95

    def test_architectural_context_with_empty_lists(self):
        """Test ArchitecturalContext with empty policy and pattern lists."""
        from will.tools.architectural_context_builder import ArchitecturalContext

        context = ArchitecturalContext(
            goal="Test goal",
            target_layer="shared",
            layer_purpose="Utilities",
            layer_patterns=[],
            relevant_policies=[],
            placement_confidence="low",
            best_module_path="src/shared",
            placement_score=0.2,
        )

        assert context.layer_patterns == []
        assert context.relevant_policies == []
        assert context.placement_confidence == "low"


class TestCoderAgentV1EdgeCases:
    """Test edge cases and error conditions."""

    @pytest.fixture
    def mock_agent(self):
        """Create mock agent."""
        agent = Mock(spec=CoderAgentV1)
        agent._extract_code = CoderAgentV1._extract_code.__get__(agent, CoderAgentV1)
        return agent

    def test_extract_code_with_nested_blocks(self, mock_agent):
        """Test extraction with nested code blocks."""
        response = """Here's the code:

```python
def outer():
    '''Docstring with ``` inside'''
    return "test"
```"""
        result = mock_agent._extract_code(response)
        assert "def outer():" in result

    def test_extract_code_with_multiple_blocks(self, mock_agent):
        """Test extraction with multiple code blocks (takes first)."""
        response = """```python
def first():
    pass
```

```python
def second():
    pass
```"""
        result = mock_agent._extract_code(response)
        assert "def first():" in result
        assert "def second():" not in result

    def test_extract_code_empty_string(self, mock_agent):
        """Test extraction with empty string."""
        result = mock_agent._extract_code("")
        assert result == ""

    def test_extract_code_whitespace_only(self, mock_agent):
        """Test extraction with whitespace only."""
        result = mock_agent._extract_code("   \n\n   ")
        assert result == ""

    def test_extract_code_no_markers(self, mock_agent):
        """Test extraction when no code block markers present."""
        code = "def simple():\n    pass"
        result = mock_agent._extract_code(code)
        assert result == code
