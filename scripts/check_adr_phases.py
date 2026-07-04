#!/usr/bin/env python3
"""scripts/check_adr_phases.py — #726

Scan .specs/decisions/*.phases.yaml sidecars and report every open phase
that has no linked issue.  An open phase without an issue means the work is
untracked — no backlog item, no visibility, no closure path.

Exit codes:
  0  — no untracked open phases (or no sidecars exist yet)
  1  — at least one open phase has no linked issue

The CI job that calls this script uses continue-on-error: true so the result
is advisory — visible in the workflow run but not a hard CI gate.

Sidecar format (.specs/decisions/ADR-NNN.phases.yaml):

  adr: ADR-NNN
  phases:
    D1:
      status: shipped
      commit: abc1234
      summary: "What D1 delivered"
    D2:
      status: open
      issue: 674
      summary: "What D2 needs to do"
    D3:
      status: open
      summary: "D3 work not yet tracked in any issue"   # ← this triggers exit 1

Run locally: python scripts/check_adr_phases.py [--specs-dir .specs/decisions]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed — run: pip install pyyaml", file=sys.stderr)
    sys.exit(2)


def _load_sidecars(specs_dir: Path) -> list[tuple[Path, dict]]:
    sidecars = []
    for p in sorted(specs_dir.glob("*.phases.yaml")):
        try:
            data = yaml.safe_load(p.read_text()) or {}
        except Exception as exc:
            print(f"WARN  {p.name}: could not parse — {exc}", file=sys.stderr)
            continue
        sidecars.append((p, data))
    return sidecars


def _check(sidecars: list[tuple[Path, dict]]) -> int:
    """Return 0 if clean, 1 if any open phase has no issue."""
    untracked: list[tuple[str, str]] = []
    tracked_open: list[tuple[str, str, int]] = []
    shipped: list[tuple[str, str]] = []

    for path, data in sidecars:
        adr_id = data.get("adr", path.stem.replace(".phases", ""))
        phases = data.get("phases") or {}
        for phase_id, info in phases.items():
            if not isinstance(info, dict):
                continue
            status = str(info.get("status", "unknown")).lower()
            if status == "shipped":
                shipped.append((adr_id, phase_id))
            elif status == "open":
                issue = info.get("issue")
                if issue:
                    tracked_open.append((adr_id, phase_id, int(issue)))
                else:
                    untracked.append((adr_id, phase_id))

    # Print summary
    total = len(shipped) + len(tracked_open) + len(untracked)
    print(f"\nADR phase scan: {total} phase(s) across {len(sidecars)} sidecar(s)\n")

    if shipped:
        print(f"  ✓ Shipped ({len(shipped)}):")
        for adr, phase in shipped:
            print(f"      {adr} {phase}")

    if tracked_open:
        print(f"\n  ⟳ Open + tracked ({len(tracked_open)}):")
        for adr, phase, issue in tracked_open:
            print(f"      {adr} {phase}  → #{issue}")

    if untracked:
        print(f"\n  ✗ Open + UNTRACKED ({len(untracked)}) — create an issue or mark shipped:")
        for adr, phase in untracked:
            print(f"      {adr} {phase}")

    print()

    if untracked:
        print(
            f"FAIL: {len(untracked)} open phase(s) have no linked issue.\n"
            "      Link an issue (add 'issue: NNN') or mark 'status: shipped'."
        )
        return 1

    print("OK: all open phases are tracked.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--specs-dir",
        default=".specs/decisions",
        help="Directory containing *.phases.yaml sidecars (default: .specs/decisions)",
    )
    args = parser.parse_args()

    specs_dir = Path(args.specs_dir)
    if not specs_dir.is_dir():
        print(f"ERROR: specs-dir not found: {specs_dir}", file=sys.stderr)
        sys.exit(2)

    sidecars = _load_sidecars(specs_dir)
    if not sidecars:
        print(f"No *.phases.yaml sidecars found in {specs_dir} — nothing to check.")
        sys.exit(0)

    sys.exit(_check(sidecars))


if __name__ == "__main__":
    main()
