# src/core/capabilities.py
"""
CORE Capability Registry
This file is the high-level entry point for the system's self-awareness loop.
It defines the `introspection` capability, which orchestrates the system's tools
to perform a full self-analysis.
"""
import subprocess
import sys
from pathlib import Path
from dotenv import load_dotenv

from shared.logger import getLogger

log = getLogger(__name__)

# CAPABILITY: introspection
def introspection():
    """
    Runs a full self-analysis cycle to inspect system structure and health.
    This orchestrates the execution of the system's own introspection tools
    as separate, governed processes.
    """
    log.info("🔍 Starting introspection cycle...")
    
    project_root = Path(__file__).resolve().parents[2]
    python_executable = sys.executable

    tools_to_run = [
        ("Knowledge Graph Builder", "src.system.tools.codegraph_builder"),
        ("Constitutional Auditor", "src.system.governance.constitutional_auditor"),
    ]

    all_passed = True
    for name, module in tools_to_run:
        log.info(f"Running {name}...")
        try:
            result = subprocess.run(
                [python_executable, "-m", module],
                cwd=project_root,
                capture_output=True,
                text=True,
                check=True 
            )
            # Log stdout and stderr at a lower level to keep the main log clean
            if result.stdout:
                log.debug(f"{name} stdout:\n{result.stdout}")
            if result.stderr:
                log.warning(f"{name} stderr:\n{result.stderr}")
            log.info(f"✅ {name} completed successfully.")
        except subprocess.CalledProcessError as e:
            # Log the captured output for better error diagnosis
            log.error(f"❌ {name} failed with exit code {e.returncode}.")
            if e.stdout:
                log.error(f"{name} stdout:\n{e.stdout}")
            if e.stderr:
                log.error(f"{name} stderr:\n{e.stderr}")
            all_passed = False
        except Exception as e:
            log.error(f"💥 An unexpected error occurred while running {name}: {e}", exc_info=True)
            all_passed = False
            
    log.info("🧠 Introspection cycle completed.")
    return all_passed

if __name__ == "__main__":
    load_dotenv()
    # Allows running the full introspection cycle directly from the CLI.
    if not introspection():
        sys.exit(1)
    sys.exit(0)