#!/usr/bin/env python3
"""
validate_flow_placement.py

Validates that all Flow layer files are correctly placed in a CORE
repository. Run from the repository root on lira:

    python validate_flow_placement.py
    python validate_flow_placement.py --root /opt/dev/CORE
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# ANSI colours
# ---------------------------------------------------------------------------
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


def ok(msg: str) -> None:
    print(f"  {GREEN}✓{RESET}  {msg}")


def fail(msg: str) -> None:
    print(f"  {RED}✗{RESET}  {msg}")


def warn(msg: str) -> None:
    print(f"  {YELLOW}⚠{RESET}  {msg}")


def section(title: str) -> None:
    print(f"\n{BOLD}{CYAN}── {title}{RESET}")


# ---------------------------------------------------------------------------
# Expected files
# ---------------------------------------------------------------------------

SRC_FILES = [
    "src/body/flows/__init__.py",
    "src/body/flows/registry.py",
    "src/body/flows/executor.py",
    "src/body/flows/result.py",
]

INTENT_FLOWS = [
    ".intent/flows/flow.fix_code.yaml",
    ".intent/flows/flow.sync_state.yaml",
    ".intent/flows/flow.build_tests.yaml",
    ".intent/flows/flow.dev_sync.yaml",
]

META_FILES = [
    ".intent/META/flow.schema.json",
]

SPECS_FILES = [
    ".specs/papers/CORE-Flow.md",
]

REQUIRED_FLOW_IDS = {
    "flow.fix_code",
    "flow.sync_state",
    "flow.build_tests",
    "flow.dev_sync",
}

REQUIRED_SRC_SYMBOLS = {
    "src/body/flows/registry.py": [
        "FlowRegistry",
        "FlowDefinition",
        "FlowStep",
        "StepKind",
        "flow_registry",
    ],
    "src/body/flows/executor.py": ["FlowExecutor"],
    "src/body/flows/result.py": ["FlowResult", "StepResult"],
    "src/body/flows/__init__.py": ["FlowExecutor", "FlowResult", "flow_registry"],
}

REQUIRED_INTENT_TREE_ENTRY = "flows"


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def check_file_exists(root: Path, rel: str) -> bool:
    p = root / rel
    if p.exists():
        ok(rel)
        return True
    else:
        fail(f"{rel}  ← NOT FOUND")
        return False


def check_src_files(root: Path) -> int:
    section("src/body/flows/ — Python source files")
    failures = 0
    for rel in SRC_FILES:
        if not check_file_exists(root, rel):
            failures += 1
    return failures


def check_intent_flows(root: Path) -> int:
    section(".intent/flows/ — Flow declarations (YAML)")
    failures = 0
    for rel in INTENT_FLOWS:
        if not check_file_exists(root, rel):
            failures += 1
    return failures


def check_meta_files(root: Path) -> int:
    section(".intent/META/ — Flow schema")
    failures = 0
    for rel in META_FILES:
        if not check_file_exists(root, rel):
            failures += 1
    return failures


def check_specs_files(root: Path) -> int:
    section(".specs/papers/ — Constitutional paper")
    failures = 0
    for rel in SPECS_FILES:
        if not check_file_exists(root, rel):
            failures += 1
    return failures


def check_yaml_content(root: Path) -> int:
    section("YAML content — flow_id, kind, steps")
    failures = 0
    found_ids: set[str] = set()

    flows_dir = root / ".intent" / "flows"
    if not flows_dir.exists():
        fail(".intent/flows/ directory missing — skipping YAML content checks")
        return 1

    for yaml_path in sorted(flows_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        except Exception as exc:
            fail(f"{yaml_path.name}: parse error — {exc}")
            failures += 1
            continue

        # kind must be 'flow'
        kind = data.get("kind")
        if kind != "flow":
            fail(f"{yaml_path.name}: kind='{kind}' — expected 'flow'")
            failures += 1

        # $schema must reference flow.schema.json
        schema_ref = data.get("$schema", "")
        if "flow.schema.json" not in schema_ref:
            warn(
                f"{yaml_path.name}: $schema='{schema_ref}' — expected 'META/flow.schema.json'"
            )

        flow_block = data.get("flow", {})
        flow_id = flow_block.get("flow_id", "")
        steps = flow_block.get("steps", [])

        if not flow_id:
            fail(f"{yaml_path.name}: missing flow.flow_id")
            failures += 1
        elif not flow_id.startswith("flow."):
            fail(f"{yaml_path.name}: flow_id='{flow_id}' must start with 'flow.'")
            failures += 1
        else:
            found_ids.add(flow_id)
            ok(f"{yaml_path.name}: flow_id='{flow_id}', {len(steps)} step(s)")

        if not steps:
            fail(f"{yaml_path.name}: no steps declared")
            failures += 1
        else:
            for i, step in enumerate(steps):
                ref_id = step.get("ref_id", "")
                kind_s = step.get("kind", "")
                if not ref_id:
                    fail(f"{yaml_path.name}: step[{i}] missing ref_id")
                    failures += 1
                if kind_s not in ("action", "flow"):
                    fail(
                        f"{yaml_path.name}: step[{i}] kind='{kind_s}' — must be 'action' or 'flow'"
                    )
                    failures += 1

    # Check all required flow IDs are present
    missing_ids = REQUIRED_FLOW_IDS - found_ids
    for fid in sorted(missing_ids):
        fail(f"Required flow_id '{fid}' not found in any .intent/flows/*.yaml")
        failures += 1

    return failures


def check_schema_json(root: Path) -> int:
    section(".intent/META/flow.schema.json — JSON schema validity")
    schema_path = root / ".intent" / "META" / "flow.schema.json"
    if not schema_path.exists():
        fail("flow.schema.json not found — skipping schema checks")
        return 1

    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"flow.schema.json: JSON parse error — {exc}")
        return 1

    failures = 0
    required_keys = ["$schema", "$id", "title", "properties", "required"]
    for key in required_keys:
        if key not in schema:
            fail(f"flow.schema.json: missing top-level key '{key}'")
            failures += 1
        else:
            ok(f"flow.schema.json: has '{key}'")

    return failures


def check_src_symbols(root: Path) -> int:
    section("src/body/flows/ — key symbols present in source")
    failures = 0

    for rel, symbols in REQUIRED_SRC_SYMBOLS.items():
        path = root / rel
        if not path.exists():
            fail(f"{rel}: file missing — skipping symbol check")
            failures += 1
            continue
        content = path.read_text(encoding="utf-8")
        for sym in symbols:
            if sym in content:
                ok(f"{rel}: found '{sym}'")
            else:
                fail(f"{rel}: '{sym}' NOT found")
                failures += 1

    return failures


def check_registry_loads_from_intent(root: Path) -> int:
    section("registry.py — loads from .intent/flows/ not hardcoded")
    failures = 0
    path = root / "src" / "body" / "flows" / "registry.py"
    if not path.exists():
        fail("registry.py not found — skipping")
        return 1

    content = path.read_text(encoding="utf-8")

    # Must load from .intent
    if ".intent" in content and "flows_dir" in content:
        ok("registry.py: references .intent/flows/ directory")
    else:
        fail("registry.py: does not appear to load from .intent/flows/")
        failures += 1

    # Must NOT have hardcoded register_flow calls
    if "register_flow(" in content:
        fail(
            "registry.py: contains hardcoded register_flow() calls — declarations must live in .intent/flows/"
        )
        failures += 1
    else:
        ok("registry.py: no hardcoded register_flow() calls")

    # __init__.py must not have register_flow calls either
    init_path = root / "src" / "body" / "flows" / "__init__.py"
    if init_path.exists():
        init_content = init_path.read_text(encoding="utf-8")
        if "register_flow(" in init_content:
            fail("__init__.py: contains hardcoded register_flow() calls")
            failures += 1
        else:
            ok("__init__.py: no hardcoded register_flow() calls")

    return failures


def check_intent_tree(root: Path) -> int:
    section(".intent/META/intent_tree.yaml — 'flows' directory declared")
    tree_path = root / ".intent" / "META" / "intent_tree.yaml"
    if not tree_path.exists():
        warn("intent_tree.yaml not found — skipping (add 'flows' manually)")
        return 0

    try:
        data = yaml.safe_load(tree_path.read_text(encoding="utf-8"))
    except Exception as exc:
        warn(f"intent_tree.yaml: parse error — {exc}")
        return 0

    all_dirs = (
        data.get("required_directories", [])
        + data.get("optional_directories", [])
        + data.get("validated_directories", [])
    )
    if REQUIRED_INTENT_TREE_ENTRY in all_dirs:
        ok("intent_tree.yaml: 'flows' is declared")
    else:
        warn(
            "intent_tree.yaml: 'flows' not yet declared — "
            "add it to optional_directories or validated_directories"
        )

    return 0  # warning only, not a hard failure


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate CORE Flow layer placement")
    parser.add_argument(
        "--root",
        default=".",
        help="Repository root (default: current directory)",
    )
    args = parser.parse_args()
    root = Path(args.root).resolve()

    print(f"\n{BOLD}CORE Flow Layer — Placement Validation{RESET}")
    print(f"Repository root: {root}\n")

    total_failures = 0
    total_failures += check_src_files(root)
    total_failures += check_intent_flows(root)
    total_failures += check_meta_files(root)
    total_failures += check_specs_files(root)
    total_failures += check_yaml_content(root)
    total_failures += check_schema_json(root)
    total_failures += check_src_symbols(root)
    total_failures += check_registry_loads_from_intent(root)
    check_intent_tree(root)  # warnings only

    print()
    if total_failures == 0:
        print(
            f"{BOLD}{GREEN}✓ All checks passed. Flow layer is correctly placed.{RESET}\n"
        )
        sys.exit(0)
    else:
        print(
            f"{BOLD}{RED}✗ {total_failures} check(s) failed. "
            f"Fix the issues above before proceeding.{RESET}\n"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
