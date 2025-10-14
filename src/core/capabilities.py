# src/core/capabilities.py
"""
Orchestrates the system's self-analysis cycle by executing introspection tools as governed subprocesses.
"""

from __future__ import annotations

import sys

from dotenv import load_dotenv

from shared.logger import getLogger
from shared.utils.subprocess_utils import run_poetry_command

log = getLogger(__name__)


# ID: b36292a6-98b1-44fb-b76a-a2faad96564b
def introspection():
    """
    Runs a full self-analysis cycle to inspect system structure and health.
    This orchestrates the execution of the system's own introspection tools
    as separate, governed processes.
    """
    log.info("🔍 Starting introspection cycle...")

    tools_to_run = [
        ("Knowledge Graph Builder", ["python", "-m", "system.tools.codegraph_builder"]),
        (
            "Constitutional Auditor",
            ["python", "-m", "system.governance.constitutional_auditor"],
        ),
    ]

    all_passed = True
    for name, command in tools_to_run:
        try:
            # Use the sanctioned wrapper instead of direct subprocess call
            run_poetry_command(f"Running {name}...", command)
            log.info(f"✅ {name} completed successfully.")
        except Exception:
            log.error(f"❌ {name} failed.")
            all_passed = False

    log.info("🧠 Introspection cycle completed.")
    return all_passed


if __name__ == "__main__":
    load_dotenv()
    if not introspection():
        sys.exit(1)
    sys.exit(0)
