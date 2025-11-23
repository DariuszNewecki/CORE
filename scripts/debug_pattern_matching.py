#!/usr/bin/env python3
"""
Diagnostic script to understand why entry point pattern isn't matching.
Run this from your CORE repository root:
  poetry run python scripts/debug_pattern_matching.py
"""

import asyncio
from pathlib import Path

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.orphaned_logic import OrphanedLogicCheck
from shared.config import settings


async def main():
    print("🔍 Diagnostic: Entry Point Pattern Matching\n")
    
    # Initialize audit context the correct way
    context = AuditorContext(settings.REPO_PATH)
    await context.load_knowledge_graph()  # This populates symbols_list
    
    # Create the check
    check = OrphanedLogicCheck(context)
    
    print(f"Total symbols loaded: {len(check.all_symbols)}")
    print(f"Entry point patterns loaded: {len(check.entry_point_patterns)}\n")
    
    # Show the patterns
    print("=" * 80)
    print("LOADED PATTERNS:")
    print("=" * 80)
    for i, pattern in enumerate(check.entry_point_patterns, 1):
        print(f"\n{i}. {pattern.get('name', 'UNNAMED')}")
        print(f"   Type: {pattern.get('entry_point_type')}")
        print(f"   Match rules: {pattern.get('match', {})}")
    
    # Find the action_handler pattern
    action_handler_pattern = None
    for p in check.entry_point_patterns:
        if p.get('name') == 'action_handler_execute':
            action_handler_pattern = p
            break
    
    if not action_handler_pattern:
        print("\n❌ action_handler_execute pattern NOT FOUND in loaded patterns!")
        print("\n📋 Available pattern names:")
        for p in check.entry_point_patterns:
            print(f"  - {p.get('name')}")
        return
    
    print("\n✅ action_handler_execute pattern FOUND!")
    print(f"   Match rules: {action_handler_pattern.get('match', {})}")
    
    # Find ActionHandler execute methods
    execute_methods = [
        s for s in check.all_symbols 
        if 'execute' in s.get('name', '').lower() and 'Handler' in s.get('name', '')
    ]
    
    print(f"\n" + "=" * 80)
    print(f"FOUND {len(execute_methods)} Handler execute methods")
    print("=" * 80)
    
    # Test first 3
    for symbol in execute_methods[:3]:
        name = symbol.get('name', 'unknown')
        file_path = symbol.get('file_path', 'unknown')
        symbol_type = symbol.get('type', 'unknown')
        
        print(f"\n📍 Symbol: {name}")
        print(f"   file_path: {file_path}")
        print(f"   type: {symbol_type}")
        
        # Derive module_path the same way the check does
        module_path = (
            file_path.replace("src/", "").replace(".py", "").replace("/", ".")
        )
        print(f"   derived module_path: {module_path}")
        
        # Check if it matches
        matches = check._is_entry_point(symbol)
        print(f"   {'✅ MATCHES' if matches else '❌ NO MATCH'}")
        
        # Test each rule individually
        match_rules = action_handler_pattern.get('match', {})
        print(f"   Testing individual rules:")
        for rule_key, rule_value in match_rules.items():
            result = check._evaluate_match_rule(rule_key, rule_value, symbol)
            status = "✅" if result else "❌"
            print(f"      {status} {rule_key} = {rule_value}")
            
            # Show why it failed
            if not result and rule_key == "module_path_contains":
                print(f"         Looking for '{rule_value}' in '{module_path}'")
                print(f"         Contains check: {rule_value in module_path}")


if __name__ == "__main__":
    asyncio.run(main())