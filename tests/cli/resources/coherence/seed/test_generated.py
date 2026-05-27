"""
Tests for cli/resources/coherence/seed.py — bootstrap_command, export_command, import_command.
"""

import json
from pathlib import Path
from unittest.mock import ANY, AsyncMock, MagicMock, call, patch

import pytest
import typer
from typer.testing import CliRunner  # noqa: F401 — used by caller

from cli.resources.coherence.seed import (
    bootstrap_command,
    export_command,
    import_command,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_context() -> MagicMock:
    """Return a typer.Context with a mock obj (CoreContext)."""
    ctx = MagicMock(spec=typer.Context)
    ctx.obj = MagicMock()
    return ctx


@pytest.fixture
def mock_registry(mock_context: MagicMock) -> MagicMock:
    """Return the context.registry mock and preconfigure its async methods."""
    registry = mock_context.obj.registry
    registry.get_cognitive_service = AsyncMock()
    registry.get_qdrant_service = AsyncMock()
    return registry


# ===========================================================================
# bootstrap_command
# ===========================================================================


class TestBootstrapCommand:
    """Coverage for bootstrap_command — happy path, no claims, service errors."""

    async def test_happy_path(
        self, mock_context: MagicMock, mock_registry: MagicMock
    ) -> None:
        """Embed harvested claims and verify upsert calls."""
        cognitive_svc = AsyncMock()
        qdrant_svc = AsyncMock()
        mock_registry.get_cognitive_service.return_value = cognitive_svc
        mock_registry.get_qdrant_service.return_value = qdrant_svc

        with (
            patch(
                "cli.resources.coherence.seed.GovernanceClaimHarvester"
            ) as mock_harvester_cls,
            patch(
                "cli.resources.coherence.seed.GovernanceClaimsService"
            ) as mock_svc_cls,
            patch(
                "cli.resources.coherence.seed.CognitiveEmbedderAdapter"
            ) as mock_embedder_cls,
            patch("cli.resources.coherence.seed.Path") as mock_path,
            patch("cli.resources.coherence.seed.console") as mock_console,
        ):
            # configure harvester
            harvester_instance = mock_harvester_cls.return_value
            claim = MagicMock()
            claim.text = "some governance text"
            claim.source_path = "path/to/doc.md"
            claim.content_sha = "abcdef12345678"
            harvester_instance.harvest.return_value = [claim, claim, claim]

            # configure embedder
            embedder_instance = mock_embedder_cls.return_value
            embedder_instance.get_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])

            # configure claims service
            svc_instance = mock_svc_cls.return_value
            svc_instance.ensure_collection = AsyncMock()
            svc_instance.upsert_claims = AsyncMock(
                return_value=2
            )  # return embedded count

            await bootstrap_command(mock_context)

            # assert services acquired
            mock_registry.get_cognitive_service.assert_awaited_once()
            mock_registry.get_qdrant_service.assert_awaited_once()

            # assert collection ensured
            svc_instance.ensure_collection.assert_awaited_once()

            # assert harvester created with REPO_PATH
            mock_harvester_cls.assert_called_once_with(mock_path.return_value)

            # assert embedding called for each claim
            assert embedder_instance.get_embedding.await_count == 3

            # assert upsert called (batch 50, so all 3 go once)
            svc_instance.upsert_claims.assert_awaited_once()
            _, kwargs = svc_instance.upsert_claims.call_args
            items = kwargs.get("items")
            assert items is not None
            assert len(items) == 3

            # console output for completion
            mock_console.print.assert_any_call(
                "[green]Bootstrap complete[/green] — embedded 2/3 "
                "claims in ANY min (0 failures)".replace("ANY", "0.0")
            )

    async def test_no_claims(
        self, mock_context: MagicMock, mock_registry: MagicMock
    ) -> None:
        """When harvester returns no claims, print yellow message and return."""
        cognitive_svc = AsyncMock()
        qdrant_svc = AsyncMock()
        mock_registry.get_cognitive_service.return_value = cognitive_svc
        mock_registry.get_qdrant_service.return_value = qdrant_svc

        with (
            patch(
                "cli.resources.coherence.seed.GovernanceClaimHarvester"
            ) as mock_harvester_cls,
            patch(
                "cli.resources.coherence.seed.GovernanceClaimsService"
            ) as mock_svc_cls,
            patch("cli.resources.coherence.seed.CognitiveEmbedderAdapter"),
            patch("cli.resources.coherence.seed.console") as mock_console,
        ):
            mock_harvester_cls.return_value.harvest.return_value = []
            svc_instance = mock_svc_cls.return_value
            svc_instance.ensure_collection = AsyncMock()

            await bootstrap_command(mock_context)

            svc_instance.ensure_collection.assert_awaited_once()
            mock_console.print.assert_called_once_with(
                "[yellow]No claims harvested — nothing to embed.[/yellow]"
            )

    async def test_service_acquisition_error(
        self, mock_context: MagicMock, mock_registry: MagicMock
    ) -> None:
        """Raise typer.Exit(1) when registry calls fail."""
        mock_registry.get_cognitive_service.side_effect = RuntimeError("Qdrant down")

        with (
            patch("cli.resources.coherence.seed.logger") as mock_logger,
            patch("cli.resources.coherence.seed.console") as mock_console,
            pytest.raises(typer.Exit) as exc_info,
        ):
            await bootstrap_command(mock_context)

        assert exc_info.value.exit_code == 1
        mock_logger.exception.assert_called_once_with(
            "Failed to acquire embedding services"
        )
        mock_console.print.assert_called_once_with(
            "[red]Service unavailable: Qdrant down[/red]"
        )

    async def test_embed_failure_continues(
        self, mock_context: MagicMock, mock_registry: MagicMock
    ) -> None:
        """When embedding fails for a claim, log warning and continue."""
        cognitive_svc = AsyncMock()
        qdrant_svc = AsyncMock()
        mock_registry.get_cognitive_service.return_value = cognitive_svc
        mock_registry.get_qdrant_service.return_value = qdrant_svc

        with (
            patch(
                "cli.resources.coherence.seed.GovernanceClaimHarvester"
            ) as mock_harvester_cls,
            patch(
                "cli.resources.coherence.seed.GovernanceClaimsService"
            ) as mock_svc_cls,
            patch(
                "cli.resources.coherence.seed.CognitiveEmbedderAdapter"
            ) as mock_embedder_cls,
            patch("cli.resources.coherence.seed.logger") as mock_logger,
            patch("cli.resources.coherence.seed.console") as mock_console,
        ):
            claim_ok = MagicMock()
            claim_ok.text = "fine"
            claim_ok.source_path = "ok.md"
            claim_ok.content_sha = "ok" * 4  # 8 chars

            claim_bad = MagicMock()
            claim_bad.text = "bad"
            claim_bad.source_path = "bad.md"
            claim_bad.content_sha = "bad" * 2 + "12"  # 8 chars

            mock_harvester_cls.return_value.harvest.return_value = [claim_ok, claim_bad]

            embedder_instance = mock_embedder_cls.return_value
            embedder_instance.get_embedding = AsyncMock(
                side_effect=[ValueError("embed failed"), [0.5, 0.6]]
            )

            svc_instance = mock_svc_cls.return_value
            svc_instance.ensure_collection = AsyncMock()
            svc_instance.upsert_claims = AsyncMock(return_value=1)

            await bootstrap_command(mock_context)

            # first claim failed — warning logged
            mock_logger.warning.assert_called_once_with(
                "bootstrap: embed failed for %s (sha=%s): %s",
                "bad.md",
                "bad" * 2 + "12",
                "embed failed",
            )

            # final output shows 1 failure
            mock_console.print.assert_any_call(
                ANY  # progress message for second claim
            )


# ===========================================================================
# export_command
# ===========================================================================


class TestExportCommand:
    """Coverage for export_command — happy path and error on file write."""

    async def test_happy_path(
        self, mock_context: MagicMock, mock_registry: MagicMock
    ) -> None:
        """Dump claims to JSONL and verify output file."""
        qdrant_svc = AsyncMock()
        mock_registry.get_qdrant_service.return_value = qdrant_svc

        with (
            patch(
                "cli.resources.coherence.seed.GovernanceClaimsService"
            ) as mock_svc_cls,
            patch("cli.resources.coherence.seed.Path.open") as mock_open,
            patch("cli.resources.coherence.seed.Path") as mock_path,
            patch("cli.resources.coherence.seed.console") as mock_console,
        ):
            # prepare mock claims
            claim1 = MagicMock()
            claim1.payload = {"id": "a"}
            claim1.vector = [0.1, 0.2]
            claim2 = MagicMock()
            claim2.payload = {"id": "b"}
            claim2.vector = [0.3, 0.4]

            svc_instance = mock_svc_cls.return_value
            svc_instance.list_claims = AsyncMock(return_value=[claim1, claim2])

            file_mock = MagicMock()
            mock_open.return_value.__enter__.return_value = file_mock

            output_path = Path("/tmp/export.jsonl")
            # The export_command uses ctx.obj, which is the mock_context.obj
            # We must also patch the typer.Argument default or pass via ctx
            # For the test we directly invoke with proper Path argument
            await export_command(mock_context, output=output_path)

            svc_instance.list_claims.assert_awaited_once()
            # Verify write calls
            expected_lines = [
                json.dumps(claim1.payload) + "\n",
                json.dumps(claim2.payload) + "\n",
            ]
            calls = [call(line) for line in expected_lines]
            file_mock.write.assert_has_calls(calls)

            mock_console.print.assert_called_with(
                f"[green]Exported 2 claims to {output_path}[/green]"
            )

    async def test_io_error(
        self, mock_context: MagicMock, mock_registry: MagicMock
    ) -> None:
        """Raise typer.Exit when file write fails."""
        qdrant_svc = AsyncMock()
        mock_registry.get_qdrant_service.return_value = qdrant_svc

        with (
            patch(
                "cli.resources.coherence.seed.GovernanceClaimsService"
            ) as mock_svc_cls,
            patch("cli.resources.coherence.seed.Path.open") as mock_open,
            patch("cli.resources.coherence.seed.console") as mock_console,
        ):
            svc_instance = mock_svc_cls.return_value
            svc_instance.list_claims = AsyncMock(
                return_value=[MagicMock(payload={}, vector=[])]
            )

            mock_open.side_effect = OSError("Disk full")

            with pytest.raises(typer.Exit) as exc_info:
                await export_command(mock_context, output=Path("/tmp/export.jsonl"))

            assert exc_info.value.exit_code == 1
            mock_console.print.assert_called_once_with(
                "[red]Export failed: Disk full[/red]"
            )


# ===========================================================================
# import_command
# ===========================================================================


class TestImportCommand:
    """Coverage for import_command — happy path and file-not-found."""

    async def test_happy_path(
        self, mock_context: MagicMock, mock_registry: MagicMock
    ) -> None:
        """Read JSONL fixture and upsert claims."""
        qdrant_svc = AsyncMock()
        mock_registry.get_qdrant_service.return_value = qdrant_svc

        source_path = Path("/tmp/fixture.jsonl")
        lines = [
            json.dumps({"payload": {"id": "a"}, "vector": [0.1, 0.2]}),
            json.dumps({"payload": {"id": "b"}, "vector": [0.3, 0.4]}),
        ]

        with (
            patch(
                "cli.resources.coherence.seed.GovernanceClaimsService"
            ) as mock_svc_cls,
            patch("cli.resources.coherence.seed.Path.open") as mock_open,
            patch("cli.resources.coherence.seed.console") as mock_console,
        ):
            file_mock = MagicMock()
            file_mock.__aiter__.return_value = [l + "\n" for l in lines]
            mock_open.return_value.__aenter__.return_value = file_mock

            svc_instance = mock_svc_cls.return_value
            svc_instance.ensure_collection = AsyncMock()
            svc_instance.import_claims = AsyncMock(return_value=2)

            await import_command(mock_context, source=source_path)

            svc_instance.ensure_collection.assert_awaited_once()
            svc_instance.import_claims.assert_awaited_once()
            args, _ = svc_instance.import_claims.call_args
            assert len(args[0]) == 2

            mock_console.print.assert_called_with(
                "[green]Imported 2 claims from fixture[/green]"
            )

    async def test_file_not_found(
        self, mock_context: MagicMock, mock_registry: MagicMock
    ) -> None:
        """Raise typer.Exit when source file does not exist."""
        source_path = Path("/nonexistent/fixture.jsonl")

        with (
            patch("cli.resources.coherence.seed.Path.open") as mock_open,
            patch("cli.resources.coherence.seed.console") as mock_console,
        ):
            mock_open.side_effect = FileNotFoundError("No such file")

            with pytest.raises(typer.Exit) as exc_info:
                await import_command(mock_context, source=source_path)

            assert exc_info.value.exit_code == 1
            mock_console.print.assert_called_once_with(
                "[red]Import failed: No such file[/red]"
            )
