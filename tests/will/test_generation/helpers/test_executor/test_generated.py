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




# ID: 769772c8-d6ab-43f6-af5c-b9cd0505997f
def test_TestExecutor():
    import asyncio

    from will.test_generation.helpers.test_executor import TestExecutor

    context = MagicMock()
    artifacts = MagicMock()
    normalizer = MagicMock()
    validator = MagicMock()
    sandbox = MagicMock()
    persistence = MagicMock()
    prompt_engine = MagicMock()

    normalizer.normalize.return_value = MagicMock(
        code="def test_x():\n    assert True\n", method="strip"
    )
    validator.validate.return_value = MagicMock(ok=True, error="")
    sandbox.run = AsyncMock(
        return_value=MagicMock(passed=True, error="", passed_tests=["test_x"])
    )
    persistence.persist_quarantined.return_value = MagicMock(
        ok=True, path="/quarantine/test_x.py", error=""
    )
    prompt_engine.build.return_value = "PROMPT"

    executor = TestExecutor(
        context=context,
        artifacts=artifacts,
        session_dir="/tmp/session",
        normalizer=normalizer,
        validator=validator,
        sandbox=sandbox,
        persistence=persistence,
        prompt_engine=prompt_engine,
    )

    # Replace extractor/model to avoid real I/O.
    executor.extractor = MagicMock()
    executor.extractor.extract_target_code.return_value = "def x():\n    return 1\n"
    executor.extractor.extract_dependencies.return_value = []
    executor.extractor.extract_similar_symbols.return_value = []

    exec_model = MagicMock()
    exec_model.manifest = MagicMock(role="coder")
    exec_model.invoke = AsyncMock(return_value="raw response")
    executor.model = exec_model

    context_service = MagicMock()
    context_service.build_for_task = AsyncMock(return_value=MagicMock())

    cognitive_svc = MagicMock()
    cognitive_svc.aget_client_for_role = AsyncMock(return_value=MagicMock())
    context.registry.get_cognitive_service = AsyncMock(return_value=cognitive_svc)

    file_path = "/repo/src/module.py"
    symbol = {"name": "x"}
    strategy = MagicMock()
    file_type = "python"
    complexity = "low"

    fake_facts = {"introspection_error": None}
    with patch(
        "will.test_generation.helpers.test_executor.build_introspection_facts",
        return_value=fake_facts,
    ):
        result = asyncio.run(
            executor.execute(
                file_path=file_path,
                symbol=symbol,
                strategy=strategy,
                context_service=context_service,
                write=True,
                file_type=file_type,
                complexity=complexity,
                has_db_harness=False,
            )
        )

    assert result["symbol"] == "x"
    assert result["skipped"] is False
    assert result["validation_failure"] is False
    assert result["validated"] is True
    assert result["sandbox_ran"] is True
    assert result["sandbox_passed"] is True
    assert result["persisted"] is True
    assert result["error"] == ""
    artifacts.write_prompt.assert_called_once()
    normalizer.normalize.assert_called_once_with("raw response")
    validator.validate.assert_called_once()
    sandbox.run.assert_awaited_once()
    persistence.persist_quarantined.assert_called_once()
