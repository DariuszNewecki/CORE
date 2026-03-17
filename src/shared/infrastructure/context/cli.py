# src/shared/infrastructure/context/cli.py

"""
CLI commands for context packet construction and export.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import typer

from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.infrastructure.context.models import ContextBuildRequest
from shared.infrastructure.context.serializers import ContextSerializer
from shared.infrastructure.context.service import ContextService
from shared.infrastructure.context.validator import ContextValidator


app = typer.Typer(
    name="context",
    help="Build, validate, and inspect governed context packets.",
    no_args_is_help=True,
)


_PHASE_BY_TASK: dict[str, str] = {
    "code_modification": "execution",
    "code_review": "audit",
    "code_analysis": "audit",
    "investigation": "runtime",
    "workflow_execution": "execution",
    "workflow_design": "load",
}


def _resolve_phase(task: str) -> str:
    return _PHASE_BY_TASK.get(task, "audit")


def _render_packet_markdown(packet: dict[str, Any]) -> str:
    lines: list[str] = []

    header = packet.get("header", {})
    lines.append("# CORE Context Packet")
    lines.append("")
    lines.append(f"- **Goal:** {header.get('goal', '')}")
    lines.append(f"- **Trigger:** {header.get('trigger', '')}")
    lines.append(f"- **Phase:** {packet.get('phase', '')}")
    lines.append(f"- **Mode:** {header.get('mode', '')}")
    lines.append("")

    constitution = packet.get("constitution", {})
    if constitution:
        lines.append("## Constitution")
        lines.append("")
        lines.append("```json")
        lines.append(_json_dump(constitution))
        lines.append("```")
        lines.append("")

    policy = packet.get("policy", {})
    if policy:
        lines.append("## Policy")
        lines.append("")
        lines.append("```json")
        lines.append(_json_dump(policy))
        lines.append("```")
        lines.append("")

    constraints = packet.get("constraints", {})
    if constraints:
        lines.append("## Constraints")
        lines.append("")
        lines.append("```json")
        lines.append(_json_dump(constraints))
        lines.append("```")
        lines.append("")

    runtime = packet.get("runtime", {})
    if runtime:
        lines.append("## Runtime")
        lines.append("")
        lines.append("```json")
        lines.append(_json_dump(runtime))
        lines.append("```")
        lines.append("")

    evidence = packet.get("evidence", [])
    lines.append("## Evidence")
    lines.append("")

    if not evidence:
        lines.append("_No evidence collected._")
        lines.append("")
    else:
        for idx, item in enumerate(evidence, start=1):
            lines.append(f"### Evidence {idx}: {item.get('name', 'unknown')}")
            lines.append("")
            lines.append(f"- **Type:** {item.get('item_type', '')}")
            lines.append(f"- **Source:** {item.get('source', '')}")
            if item.get("path"):
                lines.append(f"- **Path:** `{item['path']}`")
            if item.get("signature"):
                lines.append(f"- **Signature:** `{item['signature']}`")
            if item.get("summary"):
                lines.append("")
                lines.append(item["summary"])
            if item.get("content"):
                lines.append("")
                lines.append("```python")
                lines.append(item["content"])
                lines.append("```")
            lines.append("")

    provenance = packet.get("provenance", {})
    if provenance:
        lines.append("## Provenance")
        lines.append("")
        lines.append("```json")
        lines.append(_json_dump(provenance))
        lines.append("```")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def _json_dump(data: Any) -> str:
    import json

    return json.dumps(data, indent=2, sort_keys=True, default=str)


@app.command("build")
# ID: a77fc9e0-cbff-494d-b680-bd061092079a
async def build_cmd(
    file: list[Path] = typer.Option(
        None,
        "--file",
        help="Target source file(s) to include in context.",
    ),
    task: str = typer.Option(
        ...,
        "--task",
        help="Task type, e.g. code_modification.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        help="Output file path (.md or .yaml).",
    ),
    trigger: str = typer.Option(
        "cli",
        "--trigger",
        help="Invocation trigger.",
    ),
    workflow_id: str | None = typer.Option(None, "--workflow-id"),
    stage_id: str | None = typer.Option(None, "--stage-id"),
    include_constitution: bool = typer.Option(
        True, "--include-constitution/--no-include-constitution"
    ),
    include_policy: bool = typer.Option(True, "--include-policy/--no-include-policy"),
    include_symbols: bool = typer.Option(
        True, "--include-symbols/--no-include-symbols"
    ),
    include_vectors: bool = typer.Option(
        True, "--include-vectors/--no-include-vectors"
    ),
    include_runtime: bool = typer.Option(
        True, "--include-runtime/--no-include-runtime"
    ),
) -> None:
    result = await _build_internal(
        task=task,
        files=file or [],
        output=output,
        trigger=trigger,
        workflow_id=workflow_id,
        stage_id=stage_id,
        include_constitution=include_constitution,
        include_policy=include_policy,
        include_symbols=include_symbols,
        include_vectors=include_vectors,
        include_runtime=include_runtime,
    )
    if not result.ok:
        raise typer.Exit(code=1)


@app.command("validate")
# ID: 5dd8ffea-ce85-4350-b21d-5853f054da6f
def validate_cmd(
    file: Path = typer.Option(
        ..., "--file", exists=True, help="Path to context packet YAML"
    ),
) -> None:
    packet = ContextSerializer.from_yaml(str(file))
    result = ContextValidator().validate(packet)
    if not result.ok:
        raise typer.Exit(code=1)


@app.command("show")
# ID: d8e54905-b56d-49f0-a82e-1cdfc10d6931
def show_cmd(
    file: Path = typer.Option(
        ..., "--file", exists=True, help="Path to context packet YAML"
    ),
) -> None:
    packet = ContextSerializer.from_yaml(str(file))
    typer.echo(f"packet_id: {packet.get('header', {}).get('packet_id', '')}")
    typer.echo(f"goal: {packet.get('header', {}).get('goal', '')}")
    typer.echo(f"phase: {packet.get('phase', '')}")
    typer.echo(f"evidence_count: {len(packet.get('evidence', []))}")


@atomic_action(
    action_id="context.build",
    intent="Build a governed context packet for agent consumption",
    impact=ActionImpact.WRITE_DATA,
    policies=["atomic_actions", "data_governance"],
    category="context",
)
async def _build_internal(
    task: str,
    files: list[Path],
    output: Path | None,
    trigger: str,
    workflow_id: str | None,
    stage_id: str | None,
    include_constitution: bool,
    include_policy: bool,
    include_symbols: bool,
    include_vectors: bool,
    include_runtime: bool,
) -> ActionResult:
    start_time = time.time()

    try:
        request = ContextBuildRequest(
            goal=task,
            trigger=trigger,  # type: ignore[arg-type]
            phase=_resolve_phase(task),  # type: ignore[arg-type]
            workflow_id=workflow_id,
            stage_id=stage_id,
            target_files=[str(p) for p in files],
            include_constitution=include_constitution,
            include_policy=include_policy,
            include_symbols=include_symbols,
            include_vectors=include_vectors,
            include_runtime=include_runtime,
        )

        service = ContextService(project_root=".")
        packet_obj = await service.build(request)
        packet = {
            "header": packet_obj.header,
            "phase": packet_obj.request.phase,
            "constitution": packet_obj.constitution,
            "policy": packet_obj.policy,
            "constraints": packet_obj.constraints,
            "evidence": packet_obj.evidence,
            "runtime": packet_obj.runtime,
            "provenance": packet_obj.provenance,
        }

        output_path = output
        if output_path is None:
            output_path = Path("var/context_packet.yaml")

        if output_path.suffix.lower() == ".md":
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(_render_packet_markdown(packet), encoding="utf-8")
        else:
            ContextSerializer.to_yaml(packet, str(output_path))

        return ActionResult(
            action_id="context.build",
            ok=True,
            data={
                "task": task,
                "phase": request.phase,
                "output_path": str(output_path),
                "evidence_count": len(packet.get("evidence", [])),
            },
            duration_sec=time.time() - start_time,
            impact=ActionImpact.WRITE_DATA,
        )

    except Exception as e:
        return ActionResult(
            action_id="context.build",
            ok=False,
            data={"task": task, "error": str(e)},
            duration_sec=time.time() - start_time,
            impact=ActionImpact.READ_ONLY,
            warnings=[f"Build failed: {e!s}"],
        )
