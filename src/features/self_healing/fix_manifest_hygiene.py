# src/features/self_healing/fix_manifest_hygiene.py

"""
A self-healing tool that scans domain manifests for misplaced capability
declarations and moves them to the correct manifest file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer
import yaml
from shared.config import settings
from shared.logger import getLogger

logger = getLogger(__name__)
REPO_ROOT = settings.REPO_PATH
DOMAINS_DIR = REPO_ROOT / ".intent" / "mind" / "knowledge" / "domains"


# ID: edab7454-cab8-4e9a-bdaa-dc8b314f1fd8
def run_fix_manifest_hygiene(
    write: bool = typer.Option(
        False, "--write", help="Apply fixes to the manifest files."
    ),
):
    """
    Scans for and corrects misplaced capability declarations in domain manifests.
    """
    dry_run = not write
    logger.info("Starting manifest hygiene check for misplaced capabilities...")
    if not DOMAINS_DIR.is_dir():
        logger.error(f"Domains directory not found at: {DOMAINS_DIR}")
        raise typer.Exit(code=1)
    all_domain_files = {p.stem: p for p in DOMAINS_DIR.glob("*.yaml")}
    changes_to_make: dict[str, dict[str, Any]] = {}
    for domain_name, file_path in all_domain_files.items():
        try:
            content = yaml.safe_load(file_path.read_text("utf-8")) or {}
            capabilities = content.get("tags", [])
            misplaced_caps = [
                cap
                for cap in capabilities
                if isinstance(cap, dict)
                and "key" in cap
                and (not cap["key"].startswith(f"{domain_name}."))
            ]
            if misplaced_caps:
                content["tags"] = [
                    cap for cap in capabilities if cap not in misplaced_caps
                ]
                changes_to_make[str(file_path)] = {
                    "action": "update",
                    "content": content,
                }
                for cap in misplaced_caps:
                    correct_domain = cap["key"].split(".")[0]
                    correct_file_path = all_domain_files.get(correct_domain)
                    if correct_file_path:
                        correct_path_str = str(correct_file_path)
                        if correct_path_str not in changes_to_make:
                            changes_to_make[correct_path_str] = {
                                "action": "update",
                                "content": yaml.safe_load(
                                    correct_file_path.read_text("utf-8")
                                )
                                or {"tags": []},
                            }
                        changes_to_make[correct_path_str]["content"].setdefault(
                            "tags", []
                        ).append(cap)
                        logger.info(
                            f"   -> Planning to move '{cap['key']}' from '{file_path.name}' to '{correct_file_path.name}'"
                        )
                    else:
                        logger.warning(
                            f"   -> Could not find a manifest file for domain '{correct_domain}' to move '{cap['key']}'."
                        )
        except Exception as e:
            logger.error(f"Error processing {file_path.name}: {e}")
    if not changes_to_make:
        logger.info("Manifest hygiene is perfect. No misplaced capabilities found.")
        return
    if dry_run:
        logger.info("-- DRY RUN: The following manifest changes would be applied --")
        for path_str, change in changes_to_make.items():
            logger.info(
                f"  - File to {change['action']}: {Path(path_str).relative_to(REPO_ROOT)}"
            )
        return
    logger.info("Applying manifest hygiene fixes...")
    for path_str, change in changes_to_make.items():
        try:
            Path(path_str).write_text(
                yaml.dump(change["content"], indent=2, sort_keys=False), "utf-8"
            )
            logger.info(f"  - Updated {Path(path_str).name}")
        except Exception as e:
            logger.info(f"  - Failed to update {Path(path_str).name}: {e}")


if __name__ == "__main__":
    typer.run(run_fix_manifest_hygiene)
