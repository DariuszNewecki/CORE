from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mind.logic.engines.cli_gate.engine import CliGateEngine
from shared.audit.model import AuditFinding, AuditorContext
from shared.engine.model import EngineResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_path_resolver():
    """Return a MagicMock that satisfies PathResolver protocol."""
    return MagicMock()


@pytest.fixture
def engine(mock_path_resolver):
    """Return a fully initialised CliGateEngine instance."""
    return CliGateEngine(path_resolver=mock_path_resolver)


# ---------------------------------------------------------------------------
# __init__ tests
# ---------------------------------------------------------------------------


class TestInit:
    """Cover __init__ — construction, path_resolver storage, check registration."""

    def test_creates_all_named_checks(self, mock_path_resolver):
        """Ensure _checks dict contains every known check_type literal."""
        engine = CliGateEngine(path_resolver=mock_path_resolver)
        expected_check_types = {
            "resource_first",
            "no_layer_exposure",
            "standard_verbs",
            "dangerous_explicit",
            "async_execution",
            "help_required",
            "no_duplicates",
            "discovery_strict",
        }
        assert set(engine._checks.keys()) == expected_check_types

    def test_injects_path_resolver_into_discovery_strict(self, mock_path_resolver):
        """The DiscoveryStrictCheck stored under 'discovery_strict' must
        receive the path_resolver."""
        engine = CliGateEngine(path_resolver=mock_path_resolver)
        discovery_check = engine._checks["discovery_strict"]
        assert discovery_check._path_resolver is mock_path_resolver


# ---------------------------------------------------------------------------
# is_context_level_for tests
# ---------------------------------------------------------------------------


class TestIsContextLevelFor:
    """Class method that answers whether a check_type is context-level."""

    def test_known_check_types_return_true(self):
        """All check_types defined in _CONTEXT_CHECK_TYPES return True."""
        known_context = [
            "resource_first",
            "no_layer_exposure",
            "standard_verbs",
            "dangerous_explicit",
            "async_execution",
            "help_required",
            "no_duplicates",
            "discovery_strict",
        ]
        for ct in known_context:
            assert CliGateEngine.is_context_level_for(ct) is True

    def test_none_parameter_returns_false(self):
        """Passing None returns False — not in the context set."""
        assert CliGateEngine.is_context_level_for(None) is False

    def test_unknown_check_type_returns_false(self):
        """Any arbitrary string that is not one of the known types returns False."""
        assert CliGateEngine.is_context_level_for("nonexistent_thing") is False

    def test_empty_string_returns_false(self):
        assert CliGateEngine.is_context_level_for("") is False


# ---------------------------------------------------------------------------
# verify tests  (per-file verify, never really used)
# ---------------------------------------------------------------------------


class TestVerify:
    """per-file verify method (should never be reached at runtime)."""

    @pytest.mark.asyncio
    async def test_returns_safe_engine_result(self, engine):
        result = await engine.verify(
            Path("/fake/path.py"), {"check_type": "resource_first"}
        )
        assert isinstance(result, EngineResult)
        assert result.ok is True
        assert result.violations == []
        assert result.engine_id == "cli_gate"
        assert "context-level" in result.message


# ---------------------------------------------------------------------------
# _walk_registry tests
# ---------------------------------------------------------------------------


class TestWalkRegistry:
    """Cover the lazy import and call to walk_typer_app."""

    @patch("mind.logic.engines.cli_gate.engine.walk_typer_app")
    @patch("mind.logic.engines.cli_gate.engine.main_app")
    async def test_lazy_import_and_walk_called(self, mock_main_app, mock_walk, engine):
        """_walk_registry imports admin_cli app and delegates to walk_typer_app."""
        mock_walk.return_value = [{"name": "foo"}]
        result = engine._walk_registry()
        mock_walk.assert_called_once_with(mock_main_app, include_missing_handlers=True)
        assert result == [{"name": "foo"}]

    @patch("mind.logic.engines.cli_gate.engine.walk_typer_app")
    @patch("mind.logic.engines.cli_gate.engine.main_app")
    async def test_returns_list_of_dicts(self, mock_main_app, mock_walk, engine):
        """The returned value from walk_typer_app is passed through unchanged."""
        sample = [{"cmd": "test", "handler": "<function>"}]
        mock_walk.return_value = sample
        assert engine._walk_registry() is sample

    @patch("mind.logic.engines.cli_gate.engine.walk_typer_app")
    @patch("mind.logic.engines.cli_gate.engine.main_app")
    async def test_walk_failure_raises(self, mock_main_app, mock_walk, engine):
        mock_walk.side_effect = RuntimeError("boom")
        with pytest.raises(RuntimeError, match="boom"):
            engine._walk_registry()


# ---------------------------------------------------------------------------
# verify_context tests
# ---------------------------------------------------------------------------


class TestVerifyContext:
    """Primary dispatch for context-level cli_gate checks."""

    @pytest.fixture
    def context(self):
        return AuditorContext(project_root=Path("/proj"))

    @pytest.mark.asyncio
    async def test_missing_check_type_returns_block(self, engine, context):
        findings = await engine.verify_context(context, {"check_type": None})
        assert len(findings) == 1
        assert findings[0].severity.name == "BLOCK"
        assert "Missing 'check_type'" in findings[0].message
        assert findings[0].file_path == "none"

    @pytest.mark.asyncio
    async def test_missing_check_type_key_returns_block(self, engine, context):
        findings = await engine.verify_context(context, {})
        assert len(findings) == 1
        assert findings[0].severity.name == "BLOCK"
        assert "Missing 'check_type'" in findings[0].message

    @pytest.mark.asyncio
    async def test_unregistered_check_type_returns_block(self, engine, context):
        findings = await engine.verify_context(
            context, {"check_type": "does_not_exist"}
        )
        assert len(findings) == 1
        assert findings[0].severity.name == "BLOCK"
        assert "has no implementation" in findings[0].message
        assert "does_not_exist" in findings[0].message

    @pytest.mark.asyncio
    async def test_registered_check_delegates_and_returns_findings(
        self, engine, context
    ):
        """A known check_type delegates to the matching CliCheck.verify and
        returns its result."""
        engine._walk_registry = MagicMock(return_value=[{"cmd": "x"}])

        mock_check = MagicMock()
        mock_check.verify.return_value = [
            AuditFinding(
                check_id="cli_gate.resource_first",
                severity="INFO",
                message="ok",
                file_path="none",
            )
        ]
        engine._checks["resource_first"] = mock_check

        findings = await engine.verify_context(
            context, {"check_type": "resource_first"}
        )
        mock_check.verify.assert_called_once_with(
            [{"cmd": "x"}], {"check_type": "resource_first"}
        )
        assert len(findings) == 1
        assert findings[0].check_id == "cli_gate.resource_first"

    @pytest.mark.asyncio
    async def test_walk_registry_exception_returns_block(self, engine, context):
        """If _walk_registry raises, verify_context returns a BLOCK."""

        def raiser(*a, **kw):
            raise ValueError("registry corrupted")

        engine._walk_registry = raiser

        check = MagicMock()
        engine._checks["resource_first"] = check

        findings = await engine.verify_context(
            context, {"check_type": "resource_first"}
        )
        assert len(findings) == 1
        assert findings[0].severity.name == "BLOCK"
        assert "registry corrupted" in findings[0].message
        check.verify.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_verify_exception_returns_block(self, engine, context):
        """If the CliCheck.verify itself raises, a BLOCK is emitted."""
        engine._walk_registry = MagicMock(return_value=[])

        faulty_check = MagicMock()
        faulty_check.verify.side_effect = RuntimeError("check bug")
        engine._checks["standard_verbs"] = faulty_check

        findings = await engine.verify_context(
            context, {"check_type": "standard_verbs"}
        )
        assert len(findings) == 1
        assert findings[0].severity.name == "BLOCK"
        assert "check bug" in findings[0].message
