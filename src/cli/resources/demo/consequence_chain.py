# src/cli/resources/demo/consequence_chain.py
"""
`core-admin demo consequence-chain` — the ADR-155 public surface (Phase 3).

This module is a thin CLI shell over the accepted Phase 2 orchestration
(`cli.logic.demo.consequence_chain.run_consequence_chain`). It owns only what
a command line owns: option parsing, the D9 operator-confirmation gate, D12
evidence rendering, the optional `--output` export, and the ADR-155 §5 exit-code
mapping. It introduces no audit, proposal, execution, or evidence path of its
own — every governance fact it prints is read back from the exact chain response
the real production chain produced (D6).

Exit codes (ADR-155 §5):

- ``0``   every scenario assertion and cleanup assertion passed;
- ``2``   pre-flight/configuration failure — the scenario did not start;
- ``64``  scenario, evidence, isolation, or cleanup failure;
- ``130`` operator interruption; bounded infrastructure cleanup was attempted.
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

import typer
from rich.console import Console

from body.infrastructure.storage.file_handler import FileHandler
from cli.logic.demo.consequence_chain import run_consequence_chain
from cli.logic.demo.models import PhaseResult, RunIdentity
from cli.resources.demo.rendering import (
    build_json_report,
    build_markdown_report,
    render_summary,
)
from cli.utils.decorators import core_command
from cli.utils.exit_codes import EXIT_CONFIG_ERROR, EXIT_OK
from cli.utils.prompts import confirm_action
from shared.cli.command_meta import (
    CommandBehavior,
    CommandExposure,
    CommandLayer,
    command_meta,
)
from shared.config import settings
from shared.logger import getLogger

from .hub import app


logger = getLogger(__name__)
console = Console()

# ADR-155 §5 exit-code table. The shared ``0``/``2`` codes come from the CLI's
# canonical set; ``64`` (scenario/evidence/isolation/cleanup failure) and ``130``
# (operator interruption) are this command's contract-specific outcomes.
_EXIT_SCENARIO_FAILURE = 64
_EXIT_INTERRUPTED = 130

_CONFIRM_PROMPT = (
    "[bold]The isolated proposal is policy-approved as safe.[/bold]\n"
    "Continue with execution in the disposable repository?"
)


# ID: cb17211f-067e-4443-8555-d4b67880b48b
def _resolve_output_target(repo_root: Path, output: str) -> tuple[str, str]:
    """Resolve ``--output`` to repo-relative Markdown + JSON companion paths.

    Follows the sanctioned CLI ``--output`` pattern (``context explain``):
    an operator-chosen path, resolved against the invoking repo root, that must
    stay inside the repository boundary so the write can route through
    ``FileHandler`` rather than an ad-hoc out-of-repo write. Raises ``ValueError``
    when the target escapes the boundary — the caller maps that to exit ``2``.
    """
    output_path = Path(output)
    resolved = (
        (repo_root / output_path).resolve()
        if not output_path.is_absolute()
        else output_path.resolve()
    )
    if not resolved.is_relative_to(repo_root):
        raise ValueError(f"Output path is outside repository boundary: {output}")
    md_rel = resolved.relative_to(repo_root).as_posix()
    json_rel = resolved.with_suffix(".json").relative_to(repo_root).as_posix()
    return md_rel, json_rel


# ID: 3d107646-70a5-4abd-8844-450a45a1fd34
def _write_report(
    repo_root: Path,
    md_rel: str,
    json_rel: str,
    result: PhaseResult,
    confirmation_mode: str,
) -> None:
    """Write the D12 Markdown report and its JSON companion (U14 matching ids)."""
    handler = FileHandler(str(repo_root))
    handler.write_runtime_text(md_rel, build_markdown_report(result, confirmation_mode))
    handler.write_runtime_text(json_rel, build_json_report(result, confirmation_mode))


# ID: a9d96378-0c11-4123-92a4-72d25fb00021
def _render_interrupt(identity: RunIdentity | None) -> None:
    """Report a SIGINT-interrupted run (exit 130) with its retained path (D11)."""
    console.print()
    console.print("[bold yellow]Interrupted.[/bold yellow] Infrastructure cleanup attempted.")
    if identity is not None:
        console.print(
            f"  workspace RETAINED at {identity.state_dir}\n"
            f"  remove with: core-admin demo cleanup {identity.run_id}"
        )


@app.command("consequence-chain")
@command_meta(
    # VALIDATE, not MUTATE (ADR-155 Phase 4, governor-approved 2026-07-24): this
    # command validates the governance consequence chain entirely inside
    # run-scoped disposable infrastructure and cannot mutate the invoking
    # repository or any governed production state — the same principle by which
    # `context build` is READ despite writing `--output`. The D9 confirmation
    # below remains as an operator-safety gate, unchanged.
    canonical_name="demo.consequence-chain",
    behavior=CommandBehavior.VALIDATE,
    layer=CommandLayer.BODY,
    exposure=CommandExposure.USER_FACING,
    summary="Run the isolated, genuine governance consequence-chain demonstration.",
)
@core_command(dangerous=False, requires_context=True, requires_brain_services=False)
# ID: 79023b37-a793-4e50-830b-4afd8a51874d
async def consequence_chain_cmd(
    ctx: typer.Context,
    output: str | None = typer.Option(
        None,
        "--output",
        help="Write a Markdown report and JSON companion to this repo-relative path.",
    ),
    keep_workspace: bool = typer.Option(
        False,
        "--keep-workspace",
        help="Retain the disposable clone on success (it is always kept on failure).",
    ),
    simulate_confirmation: bool = typer.Option(
        False,
        "--simulate-confirmation",
        help="Skip the interactive operator prompt (CI/cold-room). Reported as simulated.",
    ),
    timeout_seconds: int | None = typer.Option(
        None,
        "--timeout-seconds",
        help="Bound the disposable-infrastructure and scenario waits.",
    ),
) -> None:
    """Demonstrate one genuine, isolated governance consequence chain (ADR-155).

    Seeds a real violation into a disposable clone, lets the *real* sensor,
    remediator, proposal route, executor, and consequence service run it to a
    committed change and a resolved finding, renders the exact chain as evidence,
    then tears down all disposable resources — never touching the invoking
    checkout, its database, or its daemon.
    """
    core_context = ctx.obj
    repo_root = Path(core_context.git_service.repo_path).resolve()

    # Pre-flight (exit 2): Docker present, and a valid --output target if given.
    if shutil.which("docker") is None:
        console.print(
            "[bold red]Docker is required for the isolated demo but was not found on PATH.[/bold red]"
        )
        raise typer.Exit(EXIT_CONFIG_ERROR)

    md_rel: str | None = None
    json_rel: str | None = None
    if output is not None:
        try:
            md_rel, json_rel = _resolve_output_target(repo_root, output)
        except ValueError as exc:
            console.print(f"[bold red]{exc}[/bold red]")
            raise typer.Exit(EXIT_CONFIG_ERROR) from exc

    # D9 operator confirmation — consent to continue the demonstration, NOT a
    # proposal-approval event. Declining before anything is created is a clean
    # no-op (exit 0). `--simulate-confirmation` records the mode as simulated.
    if simulate_confirmation:
        confirmation_mode = "simulated"
    else:
        if not confirm_action(_CONFIRM_PROMPT, abort_message="Demonstration cancelled."):
            raise typer.Exit(EXIT_OK)
        confirmation_mode = "human"

    identity_box: dict[str, RunIdentity] = {}

    try:
        result = await run_consequence_chain(
            core_context.git_service,
            settings.CORE_DEMO_STATE_DIR,
            keep_workspace=keep_workspace,
            timeout_seconds=float(timeout_seconds) if timeout_seconds else None,
            on_identity=lambda identity: identity_box.__setitem__("id", identity),
        )
    except (KeyboardInterrupt, asyncio.CancelledError):
        # Bounded infra cleanup already ran in the orchestration's `finally`;
        # the disposable filesystem is retained for inspection (D11).
        _render_interrupt(identity_box.get("id"))
        raise typer.Exit(_EXIT_INTERRUPTED)

    render_summary(console, result, confirmation_mode)

    if output is not None and md_rel is not None and json_rel is not None:
        _write_report(repo_root, md_rel, json_rel, result, confirmation_mode)
        console.print(f"[green]Report written to {output} (+ JSON companion).[/green]")

    raise typer.Exit(EXIT_OK if result.ok else _EXIT_SCENARIO_FAILURE)
