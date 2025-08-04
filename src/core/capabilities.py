# src/core/capabilities.py
"""
CORE Capability Registry
This file is the high-level entry point for the system's self-awareness loop.
It defines the `introspection` capability, which orchestrates the system's tools
to perform a full self-analysis.
"""
import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# CAPABILITY: introspection
def introspection():
    """
    Runs a full self-analysis cycle to inspect system structure and health.
    This orchestrates the execution of the system's own introspection tools
    as separate, governed processes.
    """
    logger.info("🔍 Starting introspection cycle...")
    
    project_root = Path(__file__).resolve().parents[2]
    python_executable = sys.executable

    tools_to_run = [
        ("Knowledge Graph Builder", "src.system.tools.codegraph_builder"),
        ("Constitutional Auditor", "src.system.governance.constitutional_auditor"),
    ]

    all_passed = True
    for name, module in tools_to_run:
        print(f"\n--- Running {name} ---")
        try:
            result = subprocess.run(
                [python_executable, "-m", module],
                cwd=project_root,
                capture_output=True,
                text=True,
                check=True 
            )
            print(result.stdout)
            if result.stderr:
                print("--- Stderr ---")
                print(result.stderr)
            logger.info(f"✅ {name} completed successfully.")
        except subprocess.CalledProcessError as e:
            print(e.stdout)
            print("--- Stderr ---")
            print(e.stderr)
            logger.error(f"❌ {name} failed with exit code {e.returncode}.")
            all_passed = False
        except Exception as e:
            logger.error(f"❌ An unexpected error occurred while running {name}: {e}")
            all_passed = False
            
    logger.info("🧠 Introspection cycle completed.")
    return all_passed