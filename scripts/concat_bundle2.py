#!/usr/bin/env python3
"""
concat_bundle.py

A constitutionally-aware script to bundle all relevant .intent2/ files
into a single text file for external AI review and analysis.

Features:
- Auto-detects project root by finding '.intent2' directory
- Runs from /opt/dev/CORE/scripts/ with NO arguments
- Outputs to /opt/dev/CORE/intent.txt by default
- Respects Charter/Mind separation
- Excludes sensitive/generated files
- Includes timestamp, Git version, and final summary
- NOW RECURSIVE: Includes all sub-files for comprehensive insight
"""

import argparse
import datetime
import subprocess
from pathlib import Path

# --- Configuration ---
DEFAULT_OUTPUT_NAME = "intent.txt"  # Output in project root
ENCODING = "utf-8"
EXCLUDE_DIRS = ["keys", "mind/prompts", "mind_export", "proposals"]
INCLUDE_EXTS = {".yaml", ".yml", ".md", ".json"}
# --- End Configuration ---


def get_git_version() -> str:
    """Get short Git commit hash if available."""
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"], cwd=Path(__file__).parent
            )
            .decode("utf-8")
            .strip()
        )
    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
        subprocess.SubprocessError,
    ):
        return "no-git"


def find_project_root(start_path: Path) -> Path:
    """Find the nearest directory containing '.intent2' by walking up."""
    current = start_path.resolve()
    while current != current.parent:  # Stop at filesystem root
        if (current / ".intent2").is_dir():
            return current
        current = current.parent
    raise FileNotFoundError("Could not find project root containing '.intent2'")


def read_file_safely(p: Path) -> str:
    """Return file contents as string; fallback to hex preview if not UTF-8."""
    try:
        return p.read_text(encoding=ENCODING, errors="strict")
    except UnicodeDecodeError:
        preview = p.read_bytes()[:256].hex()
        return (
            f"\n!!! BINARY OR NON-{ENCODING} FILE – first 256 bytes (hex):\n{preview}\n"
        )


def append_directory(
    output_path: Path,
    title: str,
    dir_path: Path,
    exclude_dirs: list[str],
    include_exts: set,
) -> int:
    """Append matching files from dir_path (recursive) to output. Returns file count."""
    file_count = 0
    if not dir_path.is_dir():
        return file_count

    # Get all files recursively, matching extensions, not in excluded paths
    files = [
        f
        for f in dir_path.rglob("*")
        if f.is_file()
        and f.suffix in include_exts
        and not any(ex in f.parts for ex in exclude_dirs)
    ]
    files.sort(key=lambda x: x.as_posix())

    if not files:
        return file_count

    with output_path.open("a", encoding=ENCODING) as out:
        out.write("\n")
        out.write(f"--- START OF SECTION: {title} ---\n")
        out.write("\n")

        for file in files:
            rel_file = file.relative_to(output_path.parent)
            out.write(f"--- START OF FILE {rel_file} ---\n")
            out.write(read_file_safely(file).rstrip() + "\n")
            out.write(f"--- END OF FILE {rel_file} ---\n\n")
            file_count += 1

        out.write(f"--- END OF SECTION: {title} ({file_count} files) ---\n")

    return file_count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate constitutional bundle for AI review."
    )
    parser.add_argument(
        "--output", help="Output file path (default: <root>/intent.txt)"
    )
    parser.add_argument(
        "--root", help="Project root directory (auto-detected if omitted)"
    )
    args = parser.parse_args()

    # --- Auto-detect project root ---
    script_dir = Path(__file__).parent.resolve()
    try:
        project_root = (
            Path(args.root).resolve() if args.root else find_project_root(script_dir)
        )
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print(
            "   Make sure '.intent2' directory exists in or above this script's location."
        )
        exit(1)

    intent_dir = project_root / ".intent2"
    if not intent_dir.is_dir():
        print(f"Error: Expected '.intent2' directory not found: {intent_dir}")
        exit(1)

    # --- Output file ---
    output_file = (
        Path(args.output).resolve()
        if args.output
        else (project_root / DEFAULT_OUTPUT_NAME)
    )

    print("Generating constitutional bundle for AI review...")
    print(f"   Project root: {project_root}")
    print(f"   Intent dir  : {intent_dir}")
    print(f"   Output file : {output_file}")

    # Start fresh
    output_file.unlink(missing_ok=True)

    total_files = 0

    # --- Header ---
    with output_file.open("a", encoding=ENCODING) as out:
        out.write(
            f"# Constitutional Bundle Generated: {datetime.datetime.now().isoformat()}\n"
        )
        out.write(f"# Source Commit: {get_git_version()}\n")
        out.write(f"# Project Root: {project_root}\n")
        out.write("\n")

    # --- 1. Master Index: meta.yaml ---
    meta_file = intent_dir / "meta.yaml"
    if meta_file.is_file():
        with output_file.open("a", encoding=ENCODING) as out:
            rel_meta = meta_file.relative_to(output_file.parent)
            out.write(f"--- START OF FILE {rel_meta} ---\n")
            out.write(read_file_safely(meta_file).rstrip() + "\n")
            out.write(f"--- END OF FILE {rel_meta} ---\n\n")
        total_files += 1

    # --- 2. PART 1: THE CHARTER ---
    with output_file.open("a", encoding=ENCODING) as out:
        out.write(
            "==============================================================================\n"
        )
        out.write("                            PART 1: THE CHARTER\n")
        out.write(
            " (The Immutable Laws, Mission, and Foundational Principles of the System)\n"
        )
        out.write(
            "==============================================================================\n"
        )

    charter_dirs = [
        ("Constitution", intent_dir / "charter" / "constitution"),
        ("Mission", intent_dir / "charter" / "mission"),
        ("Policies", intent_dir / "charter" / "policies"),
        ("Schemas", intent_dir / "charter" / "schemas"),
    ]

    for title, path in charter_dirs:
        total_files += append_directory(
            output_file, title, path, EXCLUDE_DIRS, INCLUDE_EXTS
        )

    # --- 3. PART 2: THE WORKING MIND ---
    with output_file.open("a", encoding=ENCODING) as out:
        out.write("\n")
        out.write(
            "==============================================================================\n"
        )
        out.write("                            PART 2: THE WORKING MIND\n")
        out.write(
            " (The Dynamic Knowledge, Configuration, and Evaluation Logic of the System)\n"
        )
        out.write(
            "==============================================================================\n"
        )

    mind_dirs = [
        ("Configuration", intent_dir / "mind" / "config"),
        ("Evaluation", intent_dir / "mind" / "evaluation"),
        ("Knowledge", intent_dir / "mind" / "knowledge"),
    ]

    for title, path in mind_dirs:
        total_files += append_directory(
            output_file, title, path, EXCLUDE_DIRS, INCLUDE_EXTS
        )

    # --- 4. Final Summary ---
    total_size = output_file.stat().st_size
    with output_file.open("a", encoding=ENCODING) as out:
        out.write("\n")
        out.write(
            "==============================================================================\n"
        )
        out.write("SUMMARY\n")
        out.write(
            "==============================================================================\n"
        )
        out.write(f"Generated: {datetime.datetime.now().isoformat()}\n")
        out.write(f"Files included: {total_files}\n")
        out.write(f"Total size: {total_size} bytes ({total_size / 1024:.2f} KB)\n")
        out.write(f"Output file: {output_file}\n")

    print("")
    print("Constitutional bundle successfully generated!")
    print(f"   Files: {total_files}")
    print(f"   Size : {total_size / 1024:.2f} KB")
    print(f"   Saved: {output_file}")
    print("   You can now provide this file to an external AI for review.")


if __name__ == "__main__":
    main()
