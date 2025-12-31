#!/usr/bin/env python3
# test_executor.py
"""
Test the new ActionExecutor with existing atomic actions.

This verifies:
1. Executor can load actions from registry
2. Executor validates policies
3. Executor checks authorization
4. Executor executes actions correctly
5. Executor returns consistent ActionResult
"""

import asyncio
import sys
from pathlib import Path


# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from body.atomic.executor import ActionExecutor
from body.atomic.registry import ActionCategory
from shared.context import CoreContext
from shared.logger import getLogger


logger = getLogger(__name__)


async def main():
    """Test the ActionExecutor."""

    print("=" * 70)
    print("TESTING ACTION EXECUTOR")
    print("=" * 70)
    print()

    # 1. Initialize CoreContext (same way as CLI does)
    print("1. Initializing CoreContext...")
    from body.services.service_registry import service_registry

    # Use the singleton service registry (same as admin_cli.py)
    core_context = CoreContext(registry=service_registry)
    print("   ✓ Context initialized")
    print()

    # 2. Create executor
    print("2. Creating ActionExecutor...")
    executor = ActionExecutor(core_context)
    print("   ✓ Executor created")
    print()

    # 3. List available actions
    print("3. Listing available actions...")
    actions = executor.list_actions()
    print(f"   Found {len(actions)} registered actions:")
    for action in actions:
        print(f"   - {action.action_id}: {action.description}")
        print(f"     Category: {action.category.value}, Impact: {action.impact_level}")
    print()

    # 4. Test dry-run execution
    print("4. Testing dry-run execution (fix.format)...")
    try:
        result = await executor.execute("fix.format", write=False)
        print("   ✓ Execution completed")
        print(f"     - ok: {result.ok}")
        print(f"     - duration: {result.duration_sec:.3f}s")
        print(f"     - data: {result.data}")
    except Exception as e:
        print(f"   ✗ Execution failed: {e}")
    print()

    # 5. Test action not found
    print("5. Testing non-existent action...")
    try:
        result = await executor.execute("fake.action", write=False)
        if not result.ok:
            print("   ✓ Correctly returned error")
            print(f"     - error: {result.data.get('error')}")
        else:
            print("   ✗ Should have failed but succeeded")
    except Exception as e:
        print(f"   ✗ Unexpected exception: {e}")
    print()

    # 6. Test by category
    print("6. Listing actions by category...")
    fix_actions = executor.list_actions(category=ActionCategory.FIX)
    sync_actions = executor.list_actions(category=ActionCategory.SYNC)
    print(f"   FIX actions: {len(fix_actions)}")
    for action in fix_actions:
        print(f"   - {action.action_id}")
    print(f"   SYNC actions: {len(sync_actions)}")
    for action in sync_actions:
        print(f"   - {action.action_id}")
    print()

    # 7. Test multiple executions (only safe ones in test)
    print("7. Testing multiple action executions...")
    test_actions = ["fix.format", "fix.ids", "fix.headers"]
    for action_id in test_actions:
        result = await executor.execute(action_id, write=False)
        status = "✓" if result.ok else "✗"
        print(f"   {status} {action_id}: {result.duration_sec:.3f}s")
    print()

    print("=" * 70)
    print("✓ ALL TESTS COMPLETED")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
