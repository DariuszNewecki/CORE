# scripts/test_di_check_import.py
"""
A temporary diagnostic script to force-load the DependencyInjectionCheck
and reveal any underlying ImportErrors.
"""
import sys
from pathlib import Path

print("--- Diagnostic Import Test ---")

# Add the 'src' directory to the Python path, just like the real app does
project_root = Path(__file__).resolve().parents[1]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

print(f"Attempting to import DependencyInjectionCheck from:")
print("src.mind.governance.checks.dependency_injection_check")

try:
    from mind.governance.checks.dependency_injection_check import DependencyInjectionCheck
    print("\n✅ SUCCESS: The DependencyInjectionCheck module was imported without errors.")
    print("This is unexpected. The problem may lie in the auditor's discovery mechanism.")

except ImportError as e:
    print(f"\n❌ FAILURE: An ImportError occurred during import.")
    print(f"   Error: {e}")
    print("\n   This is the root cause. The check cannot be loaded by the auditor.")
    print("   Look for circular dependencies or missing modules related to this error.")

except Exception as e:
    print(f"\n❌ FAILURE: An unexpected error occurred: {type(e).__name__}")
    print(f"   Error: {e}")