#!/usr/bin/env python3
"""
Build conversion clusters from artifacts/cli_inventory.json.

Outputs:
- artifacts/cli_conversion_clusters.md
- artifacts/cli_conversion_clusters.json
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = REPO_ROOT / "artifacts"
INV_PATH = ARTIFACTS / "cli_inventory.json"
OUT_MD = ARTIFACTS / "cli_conversion_clusters.md"
OUT_JSON = ARTIFACTS / "cli_conversion_clusters.json"


@dataclass(frozen=True)
class NeedsConversionItem:
    command: str
    module: str
    handler: str
    group: str  # first token after entrypoint
    target_resource: str
    action: str


def load_inventory() -> dict[str, Any]:
    return json.loads(INV_PATH.read_text(encoding="utf-8"))


def first_group(command: str) -> str:
    # "core-admin <group> <sub> ..."
    parts = command.split()
    if len(parts) >= 2:
        return parts[1]
    return "(root)"


def infer_action(command: str) -> str:
    parts = command.split()
    # "core-admin group action ..."
    if len(parts) >= 3:
        return parts[2]
    return "(unknown)"


def build_clusters(
    inv: dict[str, Any],
) -> tuple[list[NeedsConversionItem], dict[str, Any]]:
    items: list[NeedsConversionItem] = []
    backlog = inv.get("conversion_backlog", []) or []

    # Build a quick lookup from command -> recommendation (since backlog already includes it)
    rec_map: dict[str, dict[str, Any]] = {
        b.get("command", ""): b for b in backlog if b.get("command")
    }

    for ep in inv.get("entrypoints", []):
        for cmd in ep.get("non_resource_commands", []):
            if cmd.get("classification") != "needs_conversion":
                continue

            command = cmd.get("command", "")
            group = first_group(command)
            action = infer_action(command)

            rec = rec_map.get(command, {})
            target_resource = rec.get("recommended_target_resource") or "(unset)"

            items.append(
                NeedsConversionItem(
                    command=command,
                    module=cmd.get("module", ""),
                    handler=cmd.get("handler", ""),
                    group=group,
                    target_resource=target_resource,
                    action=action,
                )
            )

    # Cluster stats
    by_group = defaultdict(list)
    for it in items:
        by_group[it.group].append(it)

    group_sizes = {g: len(v) for g, v in by_group.items()}
    target_counts = Counter([it.target_resource for it in items])

    summary = {
        "needs_conversion_total": len(items),
        "clusters_total": len(by_group),
        "clusters_by_size_desc": sorted(
            group_sizes.items(), key=lambda x: (-x[1], x[0])
        ),
        "targets": dict(target_counts),
    }

    return items, {"summary": summary, "clusters": by_group}


def write_outputs(
    items: list[NeedsConversionItem], clusters_obj: dict[str, Any]
) -> None:
    # JSON
    json_out = {
        "summary": clusters_obj["summary"],
        "clusters": {
            k: [it.__dict__ for it in v] for k, v in clusters_obj["clusters"].items()
        },
    }
    OUT_JSON.write_text(json.dumps(json_out, indent=2), encoding="utf-8")

    # Markdown
    md = []
    md.append("# CLI Conversion Clusters")
    md.append("")
    md.append(f"Source: `{INV_PATH}`")
    md.append("")
    md.append("## Summary")
    md.append("")
    s = clusters_obj["summary"]
    md.append(f"- Needs conversion: **{s['needs_conversion_total']}**")
    md.append(f"- Clusters: **{s['clusters_total']}**")
    md.append("")
    md.append("### Clusters by size (descending)")
    md.append("")
    md.append("| Cluster (legacy root) | Commands |")
    md.append("|---|---:|")
    for name, count in s["clusters_by_size_desc"]:
        md.append(f"| `{name}` | {count} |")

    md.append("")
    md.append("### Proposed target resources (from recommender)")
    md.append("")
    md.append("| Target resource | Commands |")
    md.append("|---|---:|")
    for trg, cnt in sorted(s["targets"].items(), key=lambda x: (-x[1], x[0])):
        md.append(f"| `{trg}` | {cnt} |")

    # Cluster sections
    md.append("")
    md.append("## Clusters")
    md.append("")
    for cluster_name, cluster_items in sorted(
        clusters_obj["clusters"].items(), key=lambda x: (-len(x[1]), x[0])
    ):
        md.append(f"### `{cluster_name}` ({len(cluster_items)} commands)")
        md.append("")
        md.append("| Command | Current module | Handler | Target resource | Action |")
        md.append("|---|---|---|---|---|")
        for it in sorted(cluster_items, key=lambda i: i.command):
            md.append(
                f"| `{it.command}` | `{it.module}` | `{it.handler}` | `{it.target_resource}` | `{it.action}` |"
            )
        md.append("")

    OUT_MD.write_text("\n".join(md), encoding="utf-8")


def main() -> None:
    inv = load_inventory()
    items, clusters_obj = build_clusters(inv)
    write_outputs(items, clusters_obj)
    print(f"Wrote: {OUT_MD}")
    print(f"Wrote: {OUT_JSON}")


if __name__ == "__main__":
    main()
