# src/features/self_healing/fix_manifest_hygiene.py
# ID: 186b49f2-f06a-49b6-95f7-0e7fd097c94e

"""
Self-healing tool that scans domain manifests for misplaced capability
declarations and moves them to the correct manifest file.

Refactored to use the canonical ActionExecutor Gateway for all mutations.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from body.atomic.executor import ActionExecutor
from shared.config import settings
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)
REPO_ROOT = settings.REPO_PATH
# Use PathResolver (SSOT) to find the domains directory
DOMAINS_DIR = settings.paths.intent_root / "knowledge" / "domains"


# ID: c10bfc33-9e21-44be-9216-5ed72eaafa05
async def run_fix_manifest_hygiene(context: CoreContext, write: bool = False):
    """
    Scans for and corrects misplaced capability declarations in domain manifests.
    Mutations are routed through the governed ActionExecutor.
    """
    logger.info("🔍 Starting Governed Manifest Hygiene Check...")

    executor = ActionExecutor(context)

    if not DOMAINS_DIR.is_dir():
        logger.error("Domains directory not found at: %s", DOMAINS_DIR)
        return

    all_domain_files = {p.stem: p for p in DOMAINS_DIR.glob("*.yaml")}
    changes_to_make: dict[str, dict[str, Any]] = {}

    # 1. ANALYSIS PHASE (Read-Only)
    for domain_name, file_path in all_domain_files.items():
        try:
            content = yaml.safe_load(file_path.read_text("utf-8")) or {}
            capabilities = content.get("tags", [])

            # Find tags that belong to a different domain
            misplaced_caps = [
                cap
                for cap in capabilities
                if isinstance(cap, dict)
                and "key" in cap
                and (not cap["key"].startswith(f"{domain_name}."))
            ]

            if misplaced_caps:
                logger.warning(
                    "🚨 Found %d misplaced capabilities in %s",
                    len(misplaced_caps),
                    file_path.name,
                )

                # Prepare cleaned version of original file
                content["tags"] = [
                    cap for cap in capabilities if cap not in misplaced_caps
                ]
                changes_to_make[str(file_path)] = content

                # Move them to the correct target files
                for cap in misplaced_caps:
                    correct_domain = cap["key"].split(".")[0]
                    correct_file_path = all_domain_files.get(correct_domain)

                    if correct_file_path:
                        correct_path_str = str(correct_file_path)
                        if correct_path_str not in changes_to_make:
                            changes_to_make[correct_path_str] = yaml.safe_load(
                                correct_file_path.read_text("utf-8")
                            ) or {"tags": []}

                        changes_to_make[correct_path_str].setdefault("tags", []).append(
                            cap
                        )
                        logger.debug(
                            "   -> Moving '%s' to '%s'",
                            cap["key"],
                            correct_file_path.name,
                        )
        except Exception as e:
            logger.error("Error analyzing %s: %s", file_path.name, e)

    if not changes_to_make:
        logger.info("✅ Manifest hygiene is perfect. No misplaced capabilities found.")
        return

    # 2. EXECUTION PHASE (Gateway Dispatch)
    # We apply changes via the ActionExecutor to ensure IntentGuard compliance.
    for path_str, updated_content in changes_to_make.items():
        try:
            # Convert to repo-relative path for the Gateway
            rel_path = str(Path(path_str).relative_to(REPO_ROOT))
            yaml_str = yaml.dump(updated_content, indent=2, sort_keys=False)

            # CONSTITUTIONAL GATEWAY: Instead of raw write_text, use the executor.
            result = await executor.execute(
                action_id="file.edit", write=write, file_path=rel_path, code=yaml_str
            )

            if result.ok:
                mode_label = "Fixed" if write else "Proposed (Dry Run)"
                logger.info("   -> [%s] %s", mode_label, rel_path)
            else:
                logger.error(
                    "   -> [BLOCKED] %s: %s", rel_path, result.data.get("error")
                )

        except Exception as e:
            logger.error("❌ Failed to process fix for %s: %s", path_str, e)
