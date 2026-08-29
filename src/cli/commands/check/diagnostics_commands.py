# src/cli/commands/check/diagnostics_commands.py
"""
Diagnostic and contract verification commands.

Thin client over /v1/quality/policy-coverage (ADR-055 D6 Batch C3);
policy coverage executes server-side, this module renders the response.
"""

from __future__ import annotations

import logging

import typer

from cli.logic.diagnostics_policy import policy_coverage
from cli.utils import core_command


logger = logging.getLogger(__name__)


@core_command(dangerous=False)
# ID: 2d3aad66-4285-48c7-b65d-f32ab7f86a01
async def diagnostics_cmd(ctx: typer.Context) -> None:
    """
    Audit the constitution for policy coverage and structural integrity.
    """
    _ = ctx
    await policy_coverage()
