# src/cli/simple_health.py
# Standalone CORE health dashboard printer — run with: python -m src.cli.simple_health [--format rich|json|plain]

import argparse
import json
import sys
from datetime import datetime


try:
    from rich import box
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("rich not installed → install with: pip install rich", file=sys.stderr)


# ID: 8e043767-fef0-4d4d-92c5-f14b8cc38dd0
def get_sample_data():
    # This is placeholder data based on your earlier pasted output
    # Later replace this with real calls to your observers/blackboard/etc.
    return {
        "timestamp": datetime.now().isoformat(),
        "health": "MARGINAL",
        "workers": [
            {
                "name": "Proposal Consumer Worker",
                "class": "acting",
                "phase": "execution",
                "status": "active",
                "heartbeat": "11s ago",
            },
            {
                "name": "Violation Remediator",
                "class": "acting",
                "phase": "execution",
                "status": "active",
                "heartbeat": "3m ago",
            },
            {
                "name": "Audit Sensor — Purity",
                "class": "sensing",
                "phase": "audit",
                "status": "active",
                "heartbeat": "3m ago",
            },
            # ... add your full list here or load from real source
            {
                "name": "Audit Violation Sensor",
                "class": "sensing",
                "phase": "audit",
                "status": "stopped",
                "heartbeat": "4d ago",
            },
        ],
        "observer_snapshot": {
            "observed": "1d ago",
            "open_findings": 6133,
            "stale_entries": 5162,
            "silent_workers": 5,
            "orphaned_symbols": 1162,
        },
        "blackboard": {
            "resolved": 19253,
            "open": 6505,
            "abandoned": 310,
            "claimed": 39,
        },
        "blast_radius_top": [
            {
                "symbol": "src/shared/utils/header_tools.py::_HeaderTools.parse",
                "affected": 151,
                "callers": 41,
            },
            {
                "symbol": "src/shared/utils/header_tools.py::HeaderComponents",
                "affected": 147,
                "callers": 1,
            },
            # ... add more
        ],
    }


# ID: ae8a8989-fe9a-41a6-8ae4-5fa1c2abdb7e
def print_rich(data):
    if not RICH_AVAILABLE:
        print("rich library required for pretty output. Falling back to plain.")
        print_plain(data)
        return

    console = Console()
    console.clear()

    # Summary panel
    open_f = data["observer_snapshot"]["open_findings"]
    color = "green" if open_f < 1000 else "yellow" if open_f < 8000 else "red"
    summary = Text.assemble(
        ("CORE Health: ", "bold white"),
        (data["health"], f"bold {color}"),
        f"  — {data['timestamp']}\n",
        ("Open findings: ", "dim"),
        Text(f"{open_f}", style=f"bold {color}"),
    )
    console.print(
        Panel(summary, title="Overview", border_style="bright_blue", expand=False)
    )
    console.print("")

    # Workers table
    table = Table(
        title="Workers",
        box=box.ROUNDED,
        border_style="dim blue",
        header_style="bold magenta",
    )
    table.add_column("Name", style="cyan", max_width=32)
    table.add_column("Class", justify="center")
    table.add_column("Phase", justify="center")
    table.add_column("Status", justify="center")
    table.add_column("Heartbeat", justify="right")

    for w in sorted(data["workers"], key=lambda x: x["status"] != "active"):
        status_style = "bold green" if w["status"] == "active" else "bold red"
        hb_style = (
            "green"
            if "s ago" in w["heartbeat"]
            else "yellow"
            if "m ago" in w["heartbeat"]
            else "red"
        )
        table.add_row(
            w["name"],
            w["class"],
            w["phase"],
            Text(w["status"], style=status_style),
            Text(w["heartbeat"], style=hb_style),
        )
    console.print(table)
    console.print("")

    # Observer snapshot
    snap = data["observer_snapshot"]
    snap_text = f"Observed: {snap['observed']}\nOpen Findings: {snap['open_findings']}\nStale: {snap['stale_entries']}\nSilent: {snap['silent_workers']}\nOrphaned: {snap['orphaned_symbols']}"
    console.rule("Observer Snapshot", style="cyan")
    console.print(Panel(snap_text, border_style="dim"))
    console.print("")

    # Blackboard
    bb = data["blackboard"]
    bb_table = Table(title="Blackboard", box=box.SIMPLE)
    bb_table.add_column("Status", style="cyan")
    bb_table.add_column("Count", justify="right")
    bb_table.add_row("resolved", str(bb["resolved"]))
    bb_table.add_row("open", Text(str(bb["open"]), style="yellow"))
    bb_table.add_row("abandoned", str(bb["abandoned"]))
    bb_table.add_row("claimed", str(bb["claimed"]))
    console.print(bb_table)
    console.print("")

    # Blast Radius
    br_table = Table(
        title="Blast Radius — Top", box=box.ROUNDED, border_style="dim red"
    )
    br_table.add_column("Symbol", style="magenta", max_width=50)
    br_table.add_column("Affected", justify="right", style="bold")
    br_table.add_column("Callers", justify="right")
    for item in data["blast_radius_top"]:
        affected = item["affected"]
        aff_color = "red" if affected > 100 else "yellow" if affected > 50 else "white"
        br_table.add_row(
            item["symbol"],
            Text(str(affected), style=f"bold {aff_color}"),
            str(item["callers"]),
        )
    console.print(br_table)


# ID: 9c4b25ff-9ba1-49d7-9e20-eda87ab1d5d9
def print_plain(data):
    print("CORE Runtime Health")
    print("=" * 50)
    print(f"Time: {data['timestamp']}")
    print(f"Health: {data['health']}")
    print(f"Open findings: {data['observer_snapshot']['open_findings']}")
    print("\nWorkers:")
    for w in data["workers"]:
        print(f"  {w['name'][:30]:30} {w['status']:8} {w['heartbeat']}")
    print(
        "\nObserver: open findings={open_findings}, stale={stale_entries}".format(
            **data["observer_snapshot"]
        )
    )
    print("Blackboard open:", data["blackboard"]["open"])


# ID: 31666394-84dc-4d13-885b-da522244852b
def print_json(data):
    print(json.dumps(data, indent=2, default=str))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CORE Health Dashboard")
    parser.add_argument(
        "--format",
        choices=["rich", "plain", "json"],
        default="rich",
        help="Output format (rich requires 'pip install rich')",
    )
    args = parser.parse_args()

    data = get_sample_data()  # ← replace later with real data fetch

    if args.format == "json":
        print_json(data)
    elif args.format == "plain":
        print_plain(data)
    else:
        print_rich(data)
