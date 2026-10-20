from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mind.governance.audit_context import AuditorContext
from mind.logic.engines.base import EngineResult
from mind.logic.engines.cli_gate.engine import CliGateEngine
from shared.models import AuditFinding


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
# ID: 2e0bb105-e18e-4b87-b748-35cb5907e3bc
def mock_path_resolver():
    """Return a MagicMock that satisfies PathResolver protocol.

    repo_root is this repository, whose CLI is the importable one: the
    engine refuses to walk a tree whose CLI is not (#965).
    """
    resolver = MagicMock()
    resolver.repo_root = Path(__file__).resolve().parents[6]
    return resolver


@pytest.fixture
# ID: b0f75496-7662-4ed9-bdee-d0c7531b556f
def engine(mock_path_resolver):
    """Return a fully initialised CliGateEngine instance."""
    return CliGateEngine(path_resolver=mock_path_resolver)


# ---------------------------------------------------------------------------
# __init__ tests
# ---------------------------------------------------------------------------


# ID: 7b3dcbb6-ff71-4121-9466-27e5953a61c6
class TestInit:
    """Cover __init__ — construction, path_resolver storage, check registration."""

    # ID: 2895144d-9028-4593-b4a2-37347f2e834b
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
            "reference_current",
            "docs_no_phantom_commands",
        }
        assert set(engine._checks.keys()) == expected_check_types

    # ID: 978aec9e-9d7f-4e42-8cbf-f5517b1a1939
    def test_injects_path_resolver_into_discovery_strict(self, mock_path_resolver):
        """The DiscoveryStrictCheck stored under 'discovery_strict' must
        receive the path_resolver."""
        engine = CliGateEngine(path_resolver=mock_path_resolver)
        discovery_check = engine._checks["discovery_strict"]
        assert discovery_check._path_resolver is mock_path_resolver


# ---------------------------------------------------------------------------
# is_context_level_for tests
# ---------------------------------------------------------------------------


# ID: 1433ed71-b246-45c1-a602-2a260d444632
class TestIsContextLevelFor:
    """Class method that answers whether a check_type is context-level."""

    # ID: 05b3cdb7-5fc1-480d-97a1-037260ad666b
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

    # ID: 8831ecf7-12ab-4fce-a292-444686021fb5
    def test_none_parameter_returns_false(self):
        """Passing None returns False — not in the context set."""
        assert CliGateEngine.is_context_level_for(None) is False

    # ID: 503762a9-6196-446e-9808-3303e18aa232
    def test_unknown_check_type_returns_false(self):
        """Any arbitrary string that is not one of the known types returns False."""
        assert CliGateEngine.is_context_level_for("nonexistent_thing") is False

    # ID: e31cac2d-c7ec-41fe-a2db-b718bfe9c57b
    def test_empty_string_returns_false(self):
        assert CliGateEngine.is_context_level_for("") is False


# ---------------------------------------------------------------------------
# verify tests  (per-file verify, never really used)
# ---------------------------------------------------------------------------


# ID: a3e5acdd-86d2-4f9b-ae39-0faa038fb1d1
class TestVerify:
    """per-file verify method (should never be reached at runtime)."""

    # ID: a2d680da-5eec-4f1f-ac47-7eae59d09967
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


# ID: 41c55aa6-4f81-4991-b115-8ed5bb64695b
class TestWalkRegistry:
    """Cover the lazy import and call to walk_typer_app.

    Source's ``_walk_registry`` does deferred imports inside the method
    (``from cli.admin_cli import app as main_app`` and
    ``from shared.cli.app_introspection import walk_typer_app``) — the
    module attribute path the autogen vintage patched
    (``mind.logic.engines.cli_gate.engine.main_app``) does not exist on the
    engine module, so the patches were no-ops and the tests collected three
    "no-fixture" errors at probe time. Patch the deferred-import targets
    where they live so the lookup inside ``_walk_registry`` resolves to
    the mock."""

    @patch("shared.cli.app_introspection.walk_typer_app")
    @patch("cli.admin_cli.app")
    # ID: 3a7f6ecc-4d25-44da-80ae-77cb22b97fb0
    def test_lazy_import_and_walk_called(self, mock_main_app, mock_walk, engine):
        """_walk_registry imports admin_cli app and delegates to walk_typer_app."""
        mock_walk.return_value = [{"name": "foo"}]
        result = engine._walk_registry()
        mock_walk.assert_called_once_with(mock_main_app, include_missing_handlers=True)
        assert result == [{"name": "foo"}]

    @patch("shared.cli.app_introspection.walk_typer_app")
    @patch("cli.admin_cli.app")
    # ID: 4cbd3c14-8777-4e59-b6f6-2171edc66d99
    def test_returns_list_of_dicts(self, mock_main_app, mock_walk, engine):
        """The returned value from walk_typer_app is passed through unchanged."""
        sample = [{"cmd": "test", "handler": "<function>"}]
        mock_walk.return_value = sample
        assert engine._walk_registry() == sample

    @patch("shared.cli.app_introspection.walk_typer_app")
    @patch("cli.admin_cli.app")
    # ID: aebb259f-8d36-4d4b-b35b-87cf37b1e7c7
    def test_walk_failure_raises(self, mock_main_app, mock_walk, engine):
        mock_walk.side_effect = RuntimeError("boom")
        with pytest.raises(RuntimeError, match="boom"):
            engine._walk_registry()


# ---------------------------------------------------------------------------
# verify_context tests
# ---------------------------------------------------------------------------


# ID: 3ac46be1-313b-4ace-bbce-9dad867a190a
class TestVerifyContext:
    """Primary dispatch for context-level cli_gate checks."""

    @pytest.fixture
    # ID: 0e011480-3684-4e01-8fd9-c2c472edab49
    def context(self):
        # AuditorContext.__init__ takes repo_path (not project_root as the
        # autogen vintage assumed). The other args default to None /
        # session-less; verify_context tests do not exercise them.
        return AuditorContext(repo_path=Path("/proj"))

    # ID: 2af3b42c-668f-41d0-974c-e588dfe707ca
    async def test_missing_check_type_returns_block(self, engine, context):
        findings = await engine.verify_context(context, {"check_type": None})
        assert len(findings) == 1
        assert findings[0].severity.name == "BLOCK"
        assert "Missing 'check_type'" in findings[0].message
        assert findings[0].file_path == "none"

    # ID: 9ffd3a98-6b19-4308-893b-77eec6046925
    async def test_missing_check_type_key_returns_block(self, engine, context):
        findings = await engine.verify_context(context, {})
        assert len(findings) == 1
        assert findings[0].severity.name == "BLOCK"
        assert "Missing 'check_type'" in findings[0].message

    # ID: 77a863f6-641b-4d4d-a899-0c431f9013e9
    async def test_unregistered_check_type_returns_block(self, engine, context):
        findings = await engine.verify_context(
            context, {"check_type": "does_not_exist"}
        )
        assert len(findings) == 1
        assert findings[0].severity.name == "BLOCK"
        assert "has no implementation" in findings[0].message
        assert "does_not_exist" in findings[0].message

    # ID: 9b60dfe5-dffd-4f11-94d7-8a9ec6c946f3
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

    # ID: eda13082-63e0-411a-a8c1-7e2e8d4df8f3
    async def test_walk_registry_exception_returns_block(self, engine, context):
        """If _walk_registry raises, verify_context returns a BLOCK."""

        # ID: 37fde913-ce5f-4fc0-8eb0-6a799e2f72d6
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

    # ID: 50d347d3-9e97-4c49-a89f-48c4bc3913cf
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


import pytest


@pytest.mark.asyncio
# ID: 2049b64a-69a0-45f0-a424-8cacb2a3cde0
async def test_CliGateEngine_verify() -> None:
    path_resolver = MagicMock()
    engine = CliGateEngine(path_resolver=path_resolver)

    file_path = Path("/tmp/some_file.py")
    params: dict = {}

    result = await engine.verify(file_path, params)

    assert result.ok is True
    assert result.violations == []
    assert result.engine_id == engine.engine_id
    assert "context-level" in result.message


from typing import Any
from unittest.mock import patch


# ID: 277482f2-254f-437b-8326-a20b75f3de4f
async def test_CliGateEngine_verify_context() -> None:
    path_resolver = MagicMock()
    engine = CliGateEngine(path_resolver=path_resolver)

    expected_findings = [MagicMock(name="finding")]
    mock_check = MagicMock()
    mock_check.check_type = "standard_verbs"
    mock_check.verify = MagicMock(return_value=expected_findings)
    engine._checks = {"standard_verbs": mock_check}

    mock_commands = [MagicMock(name="command")]
    engine._walk_registry = MagicMock(return_value=mock_commands)

    context = MagicMock()
    params: dict[str, Any] = {"check_type": "standard_verbs"}

    result = await engine.verify_context(context, params)

    assert result is expected_findings
    engine._walk_registry.assert_called_once_with()
    mock_check.verify.assert_called_once_with(mock_commands, params)
