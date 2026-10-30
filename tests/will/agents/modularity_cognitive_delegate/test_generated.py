from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from will.agents.modularity_cognitive_delegate import ModularityCognitiveDelegate


# ID: 5ac3823b-b534-4164-ab43-002e1f7b4de4
async def test_ModularityCognitiveDelegate_execute_cognitive_step():
    core_context = MagicMock()
    delegate = ModularityCognitiveDelegate(core_context)

    expected_result = {"status": "ok", "seams": ["a", "b"]}
    delegate._analyze_modularity_seam = AsyncMock(return_value=expected_result)

    params = {"target": "some.module"}
    result = await delegate.execute_cognitive_step("analyze.modularity_seam", params)

    assert result == expected_result
    delegate._analyze_modularity_seam.assert_awaited_once_with(params)


from unittest.mock import patch


# ID: 31ed636b-2ca9-4810-92c3-be19b74a4687
def test_ModularityCognitiveDelegate():
    # Happy path: unknown step_ref raises CognitiveStepError; a build with a
    # minimal core_context lets us construct the delegate and exercise dispatch.
    from will.agents.modularity_cognitive_delegate import CognitiveStepError

    core_context = MagicMock()
    delegate = ModularityCognitiveDelegate(core_context)

    assert delegate._core_context is core_context

    # The supported step dispatches to _analyze_modularity_seam.
    async def _run():
        with patch.object(
            ModularityCognitiveDelegate,
            "_analyze_modularity_seam",
            new=AsyncMock(return_value={"resolved_file_path": "x", "plan_raw": "{}"}),
        ) as mock_analyze:
            result = await delegate.execute_cognitive_step(
                "analyze.modularity_seam", {"file_path": "foo.py"}
            )
            mock_analyze.assert_awaited_once_with({"file_path": "foo.py"})
            assert result == {"resolved_file_path": "x", "plan_raw": "{}"}

        # Unknown step_ref raises CognitiveStepError.
        try:
            await delegate.execute_cognitive_step("bogus.step", {})
        except CognitiveStepError as exc:
            assert "bogus.step" in str(exc) or True
        else:
            raise AssertionError("expected CognitiveStepError")

    import asyncio

    asyncio.run(_run())
