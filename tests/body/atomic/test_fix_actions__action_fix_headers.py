"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/body/atomic/fix_actions.py
- Symbol: action_fix_headers
- Status: 1 tests passed, some failed
- Passing tests: test_action_fix_headers_context_usage
- Generated: 2026-01-11 02:53:43
"""

import pytest
from body.atomic.fix_actions import action_fix_headers

@pytest.mark.asyncio
async def test_action_fix_headers_context_usage():
    """Test that context is passed through correctly."""

    class MockCoreContext:

        def __init__(self, workspace_path):
            self.config = {'header_template': 'Test Header'}
            self.workspace = workspace_path
            self.passed_to_internal = False

        async def process(self):
            self.passed_to_internal = True
            return type('ActionResult', (), {'success': True, 'message': 'Processed', 'data': {'files': 1}})()
    import body.atomic.fix_actions as module
    original_internal = module.fix_headers_internal
    captured_context = None
    captured_write = None

    async def mock_fix_headers_internal(context, write=False):
        nonlocal captured_context, captured_write
        captured_context = context
        captured_write = write
        return type('ActionResult', (), {'success': True, 'message': 'Mocked', 'data': {}})()
    module.fix_headers_internal = mock_fix_headers_internal
    try:
        context = MockCoreContext('/test/workspace')
        result = await action_fix_headers(context, write=True)
        assert captured_context == context
        assert captured_write == True
        assert result.success == True
    finally:
        module.fix_headers_internal = original_internal
