from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from mind.governance.audit_context import AuditorContext


# ID: 933f8efd-cbd8-46ce-b05e-64ab4c9d1326
async def test_AuditorContext_load_knowledge_graph():
    repo_path = Path("/tmp/repo_ktest").resolve()

    mock_intent_repo = MagicMock()
    mock_intent_repo.root = Path("/tmp/law_ktest")

    with (
        patch("mind.logic.engines.registry.EngineRegistry") as mock_engine_registry,
        patch.object(AuditorContext, "_load_governance_resources", return_value={}),
        patch("mind.governance.audit_context.EnforcementMappingLoader"),
        patch(
            "mind.governance.audit_context.KnowledgeService"
        ) as mock_knowledge_service_cls,
    ):
        mock_engine_registry.initialize = MagicMock()

        graph = {"symbols": {"a": {"name": "a"}, "b": {"name": "b"}}}
        mock_service = MagicMock()
        mock_service.get_graph = AsyncMock(return_value=graph)
        mock_knowledge_service_cls.return_value = mock_service

        ctx = AuditorContext(
            repo_path=repo_path,
            intent_repository=mock_intent_repo,
            stateless=False,
        )
        ctx.stateless = False

        await ctx.load_knowledge_graph(force=True)

        mock_service.get_graph.assert_awaited_once()
        assert ctx.knowledge_graph == graph
        assert ctx.symbols_map == {"a": {"name": "a"}, "b": {"name": "b"}}
        assert len(ctx.symbols_list) == 2


# ID: ae627b81-1e5b-49d1-bef6-08c82ab06186
def test_AuditorContext_get_tree(tmp_path: Path):
    source_file = tmp_path / "example.py"
    source_file.write_text("x = 1\n", encoding="utf-8")

    mock_executor = MagicMock()

    with patch("mind.governance.audit_context._AST_CACHE", {}):
        with (
            patch.object(AuditorContext, "_load_governance_resources", return_value={}),
            patch(
                "mind.governance.audit_context.get_intent_repository"
            ) as mock_get_intent_repo,
            patch("mind.logic.engines.registry.EngineRegistry") as mock_registry,
            patch("mind.governance.audit_context.EnforcementMappingLoader"),
            patch("mind.logic.engines.registry.EngineRegistry.initialize"),
        ):
            mock_repo = MagicMock()
            mock_repo.root = tmp_path / "intent"
            mock_repo.root.mkdir(parents=True, exist_ok=True)
            mock_get_intent_repo.return_value = mock_repo

            ctx = AuditorContext(repo_path=tmp_path, intent_repository=mock_repo)

            tree = ctx.get_tree(source_file)

    assert tree is not None
    import ast

    assert isinstance(tree, ast.Module)
    assert len(tree.body) == 1


# ID: 2708c753-dd76-4279-8c61-1a3e5ab3b1b7
def test_auditor_context_rel_path(tmp_path):
    from mind.governance.audit_context import AuditorContext

    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    intent_root = tmp_path / "law"
    intent_root.mkdir()

    target_file = repo_path / "src" / "module.py"
    target_file.parent.mkdir(parents=True)
    target_file.write_text("x = 1\n")

    intent_repo = MagicMock()
    intent_repo.root = intent_root

    with (
        patch(
            "mind.governance.audit_context.get_intent_repository",
            return_value=intent_repo,
        ),
        patch("mind.governance.audit_context.PathResolver") as mock_paths_cls,
        patch("mind.logic.engines.registry.EngineRegistry") as mock_registry,
        patch.object(
            AuditorContext,
            "_load_governance_resources",
            return_value={},
        ),
    ):
        mock_paths = MagicMock()
        mock_paths.repo_root = repo_path
        mock_paths.intent_root = intent_root
        mock_paths_cls.return_value = mock_paths
        mock_registry.initialize = MagicMock()

        ctx = AuditorContext(
            repo_path=repo_path,
            intent_repository=intent_repo,
            stateless=True,
        )

        # Happy path: cache miss, file is under repo root -> law_relpath result
        with patch(
            "shared.infrastructure.intent.law_roots.law_relpath",
            return_value="src/module.py",
        ) as mock_law_relpath:
            result = ctx.rel_path(target_file)

        mock_law_relpath.assert_called_once()
        assert result == "src/module.py"
        assert isinstance(result, str)

        # Cached path returns same value without consulting law_relpath again
        with patch(
            "shared.infrastructure.intent.law_roots.law_relpath",
            return_value="should-not-be-used",
        ) as mock_law_relpath2:
            ctx._rel_path_map[target_file] = "src/module.py"
            cached = ctx.rel_path(target_file)

        mock_law_relpath2.assert_not_called()
        assert cached == "src/module.py"


# ID: 82e9944b-daaf-451f-af6d-bcf889368108
def test_AuditorContext_get_files(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("x")
    sub = repo / "pkg"
    sub.mkdir()
    (sub / "b.py").write_text("y")
    (sub / "c.txt").write_text("z")

    intent_repo = MagicMock()
    intent_repo.root = str(repo / ".intent")

    with (
        patch(
            "mind.governance.audit_context.get_intent_repository",
            return_value=intent_repo,
        ),
        patch(
            "mind.logic.engines.registry.EngineRegistry.initialize",
        ),
        patch(
            "mind.governance.audit_context.EnforcementMappingLoader",
        ) as mock_loader,
        patch.object(
            AuditorContext,
            "_load_governance_resources",
            return_value={},
        ),
    ):
        mock_loader.return_value = MagicMock()
        ctx = AuditorContext(repo_path=repo, intent_repository=intent_repo)

        ctx._active_per_file_rule_scopes = MagicMock(return_value=[])
        # Seed the derived file cache directly so get_files serves them from
        # _file_list_cache without relying on internal walk behaviour.
        ctx._file_list_cache = [repo / "a.py", sub / "b.py"]
        ctx._rel_path_map = {
            repo / "a.py": "a.py",
            sub / "b.py": "pkg/b.py",
        }

        files = ctx.get_files(include=["**/*.py"])

        names = sorted(p.name for p in files)
        assert names == ["a.py", "b.py"]
        assert all(isinstance(p, Path) for p in files)

        cached = ctx.get_files(include=["**/*.py"])
        assert sorted(p.name for p in cached) == names


import asyncio


# ID: 57758456-6e5c-45b3-ae97-2261b0240d38
def test_AuditorContext_sweep_llm_gate_cache():
    ctx = AuditorContext.__new__(AuditorContext)
    ctx.stateless = False
    ctx._llm_gate_cache_swept = False

    cfg = MagicMock()
    cfg.audit.llm_gate_verdict_cache_ttl_days = 7

    execute_result = MagicMock()
    execute_result.rowcount = 3
    session = MagicMock()
    session.execute = AsyncMock(return_value=execute_result)
    session.commit = AsyncMock()
    ctx.db_session = session

    with patch(
        "shared.infrastructure.intent.operational_config.load_operational_config",
        return_value=cfg,
    ):
        purged = asyncio.run(AuditorContext.sweep_llm_gate_cache(ctx))

    assert purged == 3
    session.execute.assert_awaited_once()
    session.commit.assert_awaited_once()
    assert ctx._llm_gate_cache_swept is True


# ID: 37b294e9-2047-4347-92b1-ff5ed70d2cd3
def test_AuditorContext_reload_governance(tmp_path: Path) -> None:
    intent_repo = MagicMock()
    intent_repo.root = tmp_path / ".intent"

    with (
        patch("mind.governance.audit_context.EnforcementMappingLoader") as mock_loader,
        patch("mind.logic.engines.registry.EngineRegistry") as mock_registry,
    ):
        mock_registry.initialize = MagicMock()
        mock_loader_instance = MagicMock()
        mock_loader.return_value = mock_loader_instance

        context = AuditorContext(
            repo_path=tmp_path,
            intent_repository=intent_repo,
            session_provider=None,
            llm_client=None,
        )

        new_policies = {"rule_a": object()}
        with (
            patch.object(
                AuditorContext, "_load_governance_resources", return_value=new_policies
            ) as mock_load,
            patch(
                "mind.governance.audit_context.EnforcementMappingLoader"
            ) as mock_loader2,
        ):
            new_loader_instance = MagicMock()
            mock_loader2.return_value = new_loader_instance

            context.reload_governance()

            intent_repo.reload.assert_called_once_with()
            mock_load.assert_called_once_with()
            assert context.policies == new_policies
            mock_loader2.assert_called_once_with(intent_repo.root)
            assert context.enforcement_loader is new_loader_instance


# ID: 103efbd5-90ca-4a2d-a334-701b40f60849
def test_AuditorContext_invalidate_file_cache(tmp_path):
    with (
        patch(
            "mind.governance.audit_context.get_intent_repository"
        ) as mock_get_intent_repo,
        patch("mind.logic.engines.registry.EngineRegistry.initialize"),
        patch("mind.governance.audit_context.EnforcementMappingLoader"),
        patch.object(
            __import__(
                "mind.governance.audit_context", fromlist=["AuditorContext"]
            ).AuditorContext,
            "_load_governance_resources",
            return_value={},
        ),
    ):
        mock_intent_repo = MagicMock()
        mock_intent_repo.root = tmp_path
        mock_get_intent_repo.return_value = mock_intent_repo

        ctx = __import__(
            "mind.governance.audit_context", fromlist=["AuditorContext"]
        ).AuditorContext(
            repo_path=tmp_path,
            intent_repository=mock_intent_repo,
            stateless=True,
        )

        # Populate caches to exercise the clear paths.
        ctx._file_list_cache = [tmp_path / "a.py", tmp_path / "b.py"]
        ctx._rel_path_map = {tmp_path / "a.py": "a.py"}
        ctx._pattern_cache = {"*.py": [tmp_path / "a.py"]}
        ctx._per_file_scopes_cache = ["scope1", "scope2"]

        ctx.invalidate_file_cache()

        assert ctx._file_list_cache is None
        assert ctx._rel_path_map == {}
        assert ctx._pattern_cache == {}
        assert ctx._per_file_scopes_cache is None


# ID: 0fb7bf15-23e1-42f1-b1a1-8d8fdc2717d5
def test_AuditorContext_mind_path():
    from mind.governance.audit_context import AuditorContext

    fake_mind_dir = Path("/fake/repo/.mind")
    mock_paths = MagicMock()
    mock_paths.mind_dir = fake_mind_dir
    mock_paths.repo_root = Path("/fake/repo")
    mock_paths.intent_root = Path("/fake/repo/intent")

    mock_intent_repo = MagicMock()
    mock_intent_repo.root = Path("/fake/repo/intent")

    with (
        patch("mind.governance.audit_context.PathResolver", return_value=mock_paths),
        patch(
            "mind.governance.audit_context.get_intent_repository",
            return_value=mock_intent_repo,
        ),
        patch("mind.logic.engines.registry.EngineRegistry"),
        patch.object(AuditorContext, "_load_governance_resources", return_value={}),
        patch("mind.governance.audit_context.EnforcementMappingLoader"),
    ):
        ctx = AuditorContext(
            repo_path=Path("/fake/repo"),
            intent_repository=mock_intent_repo,
            session_provider=None,
            llm_client=None,
            stateless=False,
        )

        # mind_path is exposed as a property-like attribute via PathResolver;
        # access the underlying path value rather than calling it.
        result = getattr(ctx, "mind_path")
        if callable(result):
            result = result()

    assert result == fake_mind_dir
    assert result is fake_mind_dir





# ID: 76adb032-55f4-475b-8d97-d700e5ebdc2f
def test_AuditorContext_intent_root():
    repo_path = Path("/tmp/repo")
    intent_root = Path("/tmp/intent")

    mock_intent_repo = MagicMock()
    mock_intent_repo.root = intent_root

    mock_paths = MagicMock()
    mock_paths.repo_root = repo_path
    mock_paths.intent_root = intent_root

    with (
        patch(
            "mind.governance.audit_context.get_intent_repository",
            return_value=mock_intent_repo,
        ),
        patch(
            "mind.governance.audit_context.PathResolver",
            return_value=mock_paths,
        ),
        patch(
            "mind.logic.engines.registry.EngineRegistry.initialize",
        ),
        patch.object(
            AuditorContext,
            "_load_governance_resources",
            return_value={},
        ),
        patch(
            "mind.governance.audit_context.EnforcementMappingLoader",
        ),
    ):
        context = AuditorContext(
            repo_path=repo_path,
            intent_repository=mock_intent_repo,
            stateless=True,
        )

        result = context.intent_root

    assert result == intent_root
    assert result == context.intent_path
