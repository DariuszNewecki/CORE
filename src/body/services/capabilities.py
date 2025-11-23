# src/body/services/capabilities.py

"""
Orchestrates the system's self-analysis cycle by executing introspection tools as governed subprocesses.
"""

from __future__ import annotations

import sys

from dotenv import load_dotenv

from shared.logger import getLogger
from shared.utils.subprocess_utils import run_poetry_command

logger = getLogger(__name__)


# ID: 49402dba-c978-4325-a509-c3a20c1a1957
def introspection():
    """
    Runs a full self-analysis cycle to inspect system structure and health.
    This orchestrates the execution of the system's own introspection tools
    as separate, governed processes.
    """
    logger.info("🔍 Starting introspection cycle...")
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
            run_poetry_command(f"Running {name}...", command)
            logger.info(f"✅ {name} completed successfully.")
        except Exception:
            logger.error(f"❌ {name} failed.")
            all_passed = False
    logger.info("🧠 Introspection cycle completed.")
    return all_passed


if __name__ == "__main__":
    load_dotenv()
    if not introspection():
        sys.exit(1)
    sys.exit(0)
