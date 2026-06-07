"""Tests for cli/resources/coherence/seed.py — bootstrap, export, import commands.

Source uses lazy imports inside each command (so patches must target the
classes at their canonical source paths, not the seed module namespace).
Service shape: GovernanceClaimsService.ensure_collection / is_seeded;
qdrant.scroll_all_points / upsert_points. No list_claims / import_claims
methods exist on the live surface.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import typer

from cli.resources.coherence.seed import (
    bootstrap_command,
    export_command,
    import_command,
)


@pytest.fixture
def mock_context() -> MagicMock:
    ctx = MagicMock(spec=typer.Context)
    ctx.obj = MagicMock()
    return ctx


@pytest.fixture
def mock_registry(mock_context: MagicMock) -> MagicMock:
    registry = mock_context.obj.registry
    registry.get_cognitive_service = AsyncMock()
    registry.get_qdrant_service = AsyncMock()
    return registry


class TestBootstrapCommand:
    """bootstrap_command — harvester → batch-embed → upsert flow."""

    async def test_no_claims_yields_yellow_message(
        self, mock_context: MagicMock, mock_registry: MagicMock
    ) -> None:
        """Empty harvest short-circuits with a yellow notice and a clean return."""
        with (
            patch(
                "shared.governance.coherence_harvester.GovernanceClaimHarvester"
            ) as mock_harvester_cls,
            patch(
                "body.services.governance_claims_service.GovernanceClaimsService"
            ) as mock_svc_cls,
            patch(
                "shared.infrastructure.vector.cognitive_adapter.CognitiveEmbedderAdapter"
            ),
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

    async def test_service_acquisition_error_exits_with_red_message(
        self, mock_context: MagicMock, mock_registry: MagicMock
    ) -> None:
        """Registry failure surfaces as red error + typer.Exit(1)."""
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


class TestExportCommand:
    """export_command — is_seeded() gate then scroll_all_points() → JSONL."""

    async def test_unseeded_collection_exits_with_yellow(
        self,
        mock_context: MagicMock,
        mock_registry: MagicMock,
        tmp_path: Path,
    ) -> None:
        """If governance_claims has no points, print yellow + exit non-zero."""
        with (
            patch(
                "body.services.governance_claims_service.GovernanceClaimsService"
            ) as mock_svc_cls,
            patch("cli.resources.coherence.seed.console") as mock_console,
            pytest.raises(typer.Exit) as exc_info,
        ):
            svc_instance = mock_svc_cls.return_value
            svc_instance.is_seeded = AsyncMock(return_value=False)

            await export_command(mock_context, output=tmp_path / "export.jsonl")

        assert exc_info.value.exit_code == 1
        mock_console.print.assert_called_once_with(
            "[yellow]governance_claims is empty or absent — nothing to export.[/yellow]"
        )


class TestImportCommand:
    """import_command — exists() check, JSONL read, qdrant.upsert_points."""

    async def test_fixture_not_found_exits_with_red(
        self, mock_context: MagicMock, mock_registry: MagicMock
    ) -> None:
        """Missing source path → red error + typer.Exit(1) before any service call."""
        nonexistent = Path("/nonexistent/fixture.jsonl")

        with (
            patch("cli.resources.coherence.seed.console") as mock_console,
            pytest.raises(typer.Exit) as exc_info,
        ):
            await import_command(mock_context, source=nonexistent)

        assert exc_info.value.exit_code == 1
        mock_console.print.assert_called_once_with(
            f"[red]Fixture not found: {nonexistent}[/red]"
        )

    async def test_happy_path_upserts_points_from_jsonl(
        self,
        mock_context: MagicMock,
        mock_registry: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Real JSONL fixture → qdrant.upsert_points called with constructed PointStructs."""
        source = tmp_path / "fixture.jsonl"
        source.write_text(
            json.dumps(
                {"id": "claim-a", "payload": {"text": "x"}, "vector": [0.1, 0.2, 0.3]}
            )
            + "\n"
        )

        qdrant_svc = AsyncMock()
        mock_registry.get_qdrant_service.return_value = qdrant_svc

        with (
            patch(
                "body.services.governance_claims_service.GovernanceClaimsService"
            ) as mock_svc_cls,
            patch("cli.resources.coherence.seed.console") as mock_console,
        ):
            svc_instance = mock_svc_cls.return_value
            svc_instance.ensure_collection = AsyncMock()
            svc_instance.collection_name = "governance_claims"

            await import_command(mock_context, source=source)

            svc_instance.ensure_collection.assert_awaited_once()
            qdrant_svc.upsert_points.assert_awaited_once()
            call_args = qdrant_svc.upsert_points.await_args
            assert call_args.args[0] == "governance_claims"
            points = call_args.args[1]
            assert len(points) == 1
            assert points[0].id == "claim-a"
            assert points[0].vector == [0.1, 0.2, 0.3]
            mock_console.print.assert_called_with(
                f"[green]Imported[/green] 1 claims from [bold]{source}[/bold]"
            )
