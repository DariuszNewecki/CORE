"""Tests for `core-admin database migrate` (src/cli/resources/database/migrate.py).

ADR-162 D1/D3 (U4): ``--write`` is the mutation flag, ``--apply`` a deprecated
alias for one release, ``--adopt-baseline TAG`` verifies (and with ``--write``
records) a declared baseline, and ``--bootstrap`` is gone. The service layer
is mocked; the real ``core_command`` wrapper is exercised for the dry-run
banner (``cli.command.dangerous_marking`` -- the gate was inert while the flag
was named ``--apply``).
"""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, patch

import pytest
import typer

from cli.resources.database.migrate import migrate_database
from cli.utils import decorators
from cli.utils.decorators import COMMAND_REGISTRY
from shared.infrastructure.repositories.db.ledger_engine import (
    MigrationOutcome,
    MigrationResult,
)
from shared.infrastructure.repositories.db.migration_service import (
    AdoptionReport,
    MigrationReport,
    MigrationServiceError,
)


_MOD = "cli.resources.database.migrate"


def _run(**kwargs: object) -> None:
    """Call the undecorated command with every flag defaulted unless given."""
    defaults: dict[str, object] = {
        "write": False,
        "apply": False,
        "adopt_baseline_tag": None,
    }
    defaults.update(kwargs)
    return migrate_database.__wrapped__(None, **defaults)  # type: ignore[attr-defined]


# ── flag surface ─────────────────────────────────────────────────────────────


def test_bootstrap_flag_is_retired_and_write_is_the_mutation_flag() -> None:
    params = inspect.signature(migrate_database.__wrapped__).parameters  # type: ignore[attr-defined]
    assert "bootstrap" not in params
    assert "write" in params
    assert params["write"].default.default is False  # typer.Option default
    assert "apply" in params  # deprecated alias, one release
    assert "adopt_baseline_tag" in params


def test_command_is_dangerous_so_the_write_gate_is_effective() -> None:
    meta = COMMAND_REGISTRY["migrate_database"]
    assert meta.dangerous is True
    # The wrapper only prints the dry-run banner when the command actually
    # has a `write` parameter (#504) -- that is what makes dangerous=True real.
    assert "write" in inspect.signature(migrate_database.__wrapped__).parameters  # type: ignore[attr-defined]


def test_dry_run_banner_is_printed_without_write() -> None:
    """The real core_command wrapper around the real command."""
    with (
        patch.object(decorators.console, "print") as banner,
        patch(
            f"{_MOD}.migrate_db", new=AsyncMock(return_value=MigrationReport([], False))
        ),
        patch(f"{_MOD}.console"),
    ):
        migrate_database(None, write=False, apply=False, adopt_baseline_tag=None)
    banner.assert_any_call(
        "[bold yellow]⚠️  DRY RUN MODE[/bold yellow]\n"
        "   No changes will be made. Use [cyan]--write[/cyan] to apply.\n"
    )


# ── migrate ──────────────────────────────────────────────────────────────────


async def test_default_is_a_dry_run() -> None:
    report = MigrationReport(["001_a.sql"], write=False)
    with (
        patch(f"{_MOD}.migrate_db", new=AsyncMock(return_value=report)) as svc,
        patch(f"{_MOD}.adopt_baseline", new=AsyncMock()) as adopt,
        patch(f"{_MOD}.console") as console,
    ):
        await _run()
    svc.assert_awaited_once_with(write=False)
    adopt.assert_not_called()
    printed = " ".join(str(c.args[0]) for c in console.print.call_args_list)
    assert "Dry run" in printed and "001_a.sql" in printed


async def test_write_applies_and_reports_counts() -> None:
    report = MigrationReport(
        ["001_a.sql", "002_b.sql"],
        write=True,
        results=[
            MigrationResult("001_a.sql", MigrationOutcome.APPLIED, 3),
            MigrationResult("002_b.sql", MigrationOutcome.RECONCILED, 0),
        ],
    )
    with (
        patch(f"{_MOD}.migrate_db", new=AsyncMock(return_value=report)) as svc,
        patch(f"{_MOD}.console") as console,
    ):
        await _run(write=True)
    svc.assert_awaited_once_with(write=True)
    printed = " ".join(str(c.args[0]) for c in console.print.call_args_list)
    assert "1 applied, 1 reconciled, 0 skipped" in printed


async def test_apply_is_a_deprecated_alias_for_write() -> None:
    report = MigrationReport([], write=True)
    with (
        patch(f"{_MOD}.migrate_db", new=AsyncMock(return_value=report)) as svc,
        patch(f"{_MOD}.console") as console,
    ):
        await _run(apply=True)
    svc.assert_awaited_once_with(write=True)
    printed = " ".join(str(c.args[0]) for c in console.print.call_args_list)
    assert "deprecated" in printed


async def test_service_refusal_exits_with_its_code() -> None:
    with (
        patch(
            f"{_MOD}.migrate_db",
            new=AsyncMock(
                side_effect=MigrationServiceError("Refused: nope", exit_code=1)
            ),
        ),
        patch(f"{_MOD}.console") as console,
        pytest.raises(typer.Exit) as exc_info,
    ):
        await _run(write=True)
    assert exc_info.value.exit_code == 1
    printed = " ".join(str(c.args[0]) for c in console.print.call_args_list)
    assert "Refused: nope" in printed


# ── adopt-baseline ───────────────────────────────────────────────────────────


async def test_adopt_baseline_without_write_only_verifies() -> None:
    adoption = AdoptionReport(
        "v2.9.1", "20260628_x.sql", write=False, to_record=["a", "b"]
    )
    with (
        patch(f"{_MOD}.adopt_baseline", new=AsyncMock(return_value=adoption)) as adopt,
        patch(f"{_MOD}.migrate_db", new=AsyncMock()) as svc,
        patch(f"{_MOD}.console") as console,
    ):
        await _run(adopt_baseline_tag="v2.9.1")
    adopt.assert_awaited_once_with("v2.9.1", write=False)
    svc.assert_not_called()
    printed = " ".join(str(c.args[0]) for c in console.print.call_args_list)
    assert "verified" in printed and "2 ledger row(s) would be recorded" in printed


async def test_adopt_baseline_with_write_records() -> None:
    adoption = AdoptionReport(
        "v2.9.1", "20260628_x.sql", write=True, to_record=["a"], recorded=["a"]
    )
    with (
        patch(f"{_MOD}.adopt_baseline", new=AsyncMock(return_value=adoption)) as adopt,
        patch(f"{_MOD}.console") as console,
    ):
        await _run(adopt_baseline_tag="v2.9.1", write=True)
    adopt.assert_awaited_once_with("v2.9.1", write=True)
    printed = " ".join(str(c.args[0]) for c in console.print.call_args_list)
    assert "adopted" in printed and "1 ledger row(s) recorded" in printed


async def test_adopt_baseline_refusal_exits_one() -> None:
    with (
        patch(
            f"{_MOD}.adopt_baseline",
            new=AsyncMock(
                side_effect=MigrationServiceError("Refused: probe 3/7 does not hold")
            ),
        ),
        patch(f"{_MOD}.console"),
        pytest.raises(typer.Exit) as exc_info,
    ):
        await _run(adopt_baseline_tag="v2.10.1", write=True)
    assert exc_info.value.exit_code == 1
