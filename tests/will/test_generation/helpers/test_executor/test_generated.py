from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from will.test_generation.helpers.test_executor import TestExecutor


# ID: 98871d31-354a-4ac3-8a6d-afa7081f3217
def test_TestExecutor_execute():
    import asyncio

    executor = MagicMock(spec=TestExecutor)
    executor.session_dir = "/tmp/session"
    executor.extractor = MagicMock()
    executor.extractor.extract_target_code.return_value = "def foo():\n    return 1\n"
    executor.extractor.extract_dependencies.return_value = []
    executor.extractor.extract_similar_symbols.return_value = []
    executor.prompt_engine = MagicMock()
    executor.prompt_engine.build.return_value = "prompt text"
    executor.artifacts = MagicMock()
    executor.normalizer = MagicMock()
    normalized = MagicMock()
    normalized.code = "def test_foo():\n    assert True\n"
    normalized.method = "direct"
    executor.normalizer.normalize.return_value = normalized
    executor.validator = MagicMock()
    vres = MagicMock()
    vres.ok = True
    vres.error = ""
    executor.validator.validate.return_value = vres
    executor.sandbox = MagicMock()
    sres = MagicMock()
    sres.passed = True
    sres.error = ""
    sres.passed_tests = ["test_foo"]
    executor.sandbox.run = AsyncMock(return_value=sres)
    executor.persistence = MagicMock()
    pres = MagicMock()
    pres.ok = True
    pres.path = "/tmp/session/quarantine/test_foo.py"
    pres.error = ""
    executor.persistence.persist_quarantined.return_value = pres

    model = MagicMock()
    model.manifest = MagicMock()
    model.manifest.role = "coder"
    model.invoke = AsyncMock(return_value="raw-llm-output")
    executor.model = model

    cognitive_svc = MagicMock()
    cognitive_svc.aget_client_for_role = AsyncMock(return_value=MagicMock())
    executor.context = MagicMock()
    executor.context.registry = MagicMock()
    executor.context.registry.get_cognitive_service = AsyncMock(
        return_value=cognitive_svc
    )

    context_service = MagicMock()
    context_service.build_for_task = AsyncMock(return_value=MagicMock())

    introspection_facts = {"ok": True}

    with patch(
        "will.test_generation.helpers.test_executor.build_introspection_facts",
        return_value=introspection_facts,
    ):
        result = asyncio.run(
            TestExecutor.execute(
                executor,
                file_path="src/will/foo.py",
                symbol={"name": "foo"},
                strategy=MagicMock(),
                context_service=context_service,
                write=True,
                file_type="python",
                complexity="low",
                has_db_harness=False,
            )
        )

    assert result["symbol"] == "foo"
    assert result["skipped"] is False
    assert result["validation_failure"] is False
    assert result["validated"] is True
    assert result["sandbox_ran"] is True
    assert result["sandbox_passed"] is True
    assert result["persisted"] is True
    assert result["persist_path"] == "/tmp/session/quarantine/test_foo.py"
    assert result["test_code"] == normalized.code
    context_service.build_for_task.assert_awaited_once()
    executor.model.invoke.assert_awaited_once()
    executor.sandbox.run.assert_awaited_once()
    executor.persistence.persist_quarantined.assert_called_once()
