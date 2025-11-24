#!/usr/bin/env python3
"""
Fix the duplicate TestModuleInitialization class in test_logger.py
"""
from pathlib import Path

test_file = Path("/opt/dev/CORE/tests/shared/test_logger.py")

print(f"Reading {test_file}...")
content = test_file.read_text()

# The problem: There are TWO "class TestModuleInitialization:" definitions
# One at line 171 and another nested inside it at line 172

# Fix: Remove the duplicate nested class definition
# Look for the pattern of duplicate class
lines = content.split('\n')
fixed_lines = []
skip_next_class = False
inside_duplicate = False

for i, line in enumerate(lines):
    # Look for the first TestModuleInitialization
    if 'class TestModuleInitialization:' in line and not inside_duplicate:
        fixed_lines.append(line)
        inside_duplicate = True
        skip_next_class = True
        continue
    
    # Skip the nested duplicate class and its immediate content
    if skip_next_class and 'class TestModuleInitialization:' in line:
        print(f"Removing duplicate class at line {i+1}")
        # Skip this line and the next few (docstring and pass)
        continue
    
    if skip_next_class and line.strip() in ['"""Test module initialization behavior."""', 'pass']:
        print(f"Removing duplicate content at line {i+1}: {line.strip()[:50]}")
        skip_next_class = False
        continue
    
    fixed_lines.append(line)

fixed_content = '\n'.join(fixed_lines)

print(f"\nWriting fixed content...")
test_file.write_text(fixed_content)

print("✓ File fixed!")
print("\nNow run: cd /opt/dev/CORE && poetry run pytest tests/shared/test_logger.py -v")