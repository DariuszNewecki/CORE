#!/usr/bin/env python3
"""
Quick script to repair the broken test_logger.py file using our automatic repair tools.
"""

import sys
from pathlib import Path

# Add CORE to path
CORE_PATH = Path("/opt/dev/CORE")
sys.path.insert(0, str(CORE_PATH / "src"))

from features.self_healing.test_generation.automatic_repair import AutomaticRepairService

def main():
    test_file = CORE_PATH / "tests/shared/test_logger.py"
    
    print(f"Reading {test_file}...")
    broken_code = test_file.read_text()
    
    print("Running automatic repairs...")
    repair_service = AutomaticRepairService()
    fixed_code, repairs = repair_service.apply_all_repairs(broken_code)
    
    if repairs:
        print(f"\n✓ Applied repairs: {', '.join(repairs)}")
        
        # Write back the fixed code
        test_file.write_text(fixed_code)
        
        print(f"✓ File repaired successfully!")
        print(f"\nNow run: cd /opt/dev/CORE && poetry run pytest {test_file} -v")
    else:
        print("✗ No repairs applied - file may already be valid or has unfixable issues")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())