"""#909 -- bundled prompt resolver and the repository-first fallbacks.

Covers ``shared.infrastructure.bundled_prompts`` and the four read sites
that fall back to it: ``PathResolver.prompt``, both ``PromptModel.load``
implementations, and the external runner's prompt root. Precedence is
always repository first, bundle second; a genuinely missing artifact
raises the loader's existing clear error and never selects other content.
"""

from __future__ import annotations

from importlib.resources.abc import Traversable
from pathlib import Path
from unittest.mock import patch

import pytest

from shared.infrastructure.bundled_prompts import (
    bundled_prompt,
    bundled_prompts_as_path,
    bundled_prompts_root,
    is_package_marker,
)
from shared.path_resolver import PathResolver


ARTIFACT = "docstring_writer"  # a PromptModel artifact directory in the corpus
LOOSE = "capability_definer.prompt"  # a loose prompt file at the corpus root


# --- resolver ---------------------------------------------------------------


def test_root_is_a_traversable_directory() -> None:
    root = bundled_prompts_root()
    assert isinstance(root, Traversable)
    assert root.is_dir()
    assert root.joinpath("__init__.py").is_file()


def test_bundled_prompt_resolves_artifact_dir_and_loose_file() -> None:
    artifact = bundled_prompt(ARTIFACT)
    assert artifact is not None and artifact.is_dir()
    assert artifact.joinpath("model.yaml").is_file()
    loose = bundled_prompt(LOOSE)
    assert loose is not None and loose.is_file()
    assert loose.read_text(encoding="utf-8").strip()


@pytest.mark.parametrize(
    "name", ["", "__init__.py", "../x", "a/b", "a\\b", ".", "..", "no_such_prompt"]
)
def test_bundled_prompt_returns_none_for_markers_traversal_and_unknown(
    name: str,
) -> None:
    assert bundled_prompt(name) is None


def test_is_package_marker() -> None:
    assert is_package_marker("__init__.py")
    assert is_package_marker("sub/__init__.py")
    assert not is_package_marker("model.yaml")


def test_as_path_yields_a_real_directory_for_the_block() -> None:
    with bundled_prompts_as_path() as root:
        assert isinstance(root, Path)
        assert (root / ARTIFACT / "model.yaml").is_file()
        assert (root / LOOSE).is_file()


# --- PathResolver.prompt ----------------------------------------------------


def test_path_resolver_prompt_prefers_repository(tmp_path: Path) -> None:
    repo_artifact = PathResolver(tmp_path).prompts_dir / ARTIFACT
    repo_artifact.mkdir(parents=True)
    assert PathResolver(tmp_path).prompt(ARTIFACT) == repo_artifact


def test_path_resolver_prompt_falls_back_to_bundle(tmp_path: Path) -> None:
    resolved = PathResolver(tmp_path).prompt(ARTIFACT)
    assert isinstance(resolved, Path)
    assert (resolved / "model.yaml").is_file()
    assert tmp_path not in resolved.parents
    loose = PathResolver(tmp_path).prompt(LOOSE)
    assert loose.is_file()


def test_path_resolver_prompt_missing_raises_existing_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="not found at"):
        PathResolver(tmp_path).prompt("no_such_prompt")


def test_path_resolver_prompt_refuses_non_filesystem_bundle(tmp_path: Path) -> None:
    """A path API never hands out a Traversable that is not a Path."""

    class _NotAPath:
        def is_file(self) -> bool:
            return True

        def is_dir(self) -> bool:
            return False

    with patch(
        "shared.infrastructure.bundled_prompts.bundled_prompt", return_value=_NotAPath()
    ):
        with pytest.raises(FileNotFoundError, match="not filesystem-addressable"):
            PathResolver(tmp_path).prompt(ARTIFACT)


# --- shared.ai.PromptModel.load ---------------------------------------------


def _write_repo_artifact(prompts_root: Path, name: str, system_text: str) -> Path:
    """A repository copy of the bundled artifact *name* with its own system.txt."""
    bundled = bundled_prompt(name)
    assert bundled is not None
    d = prompts_root / name
    d.mkdir(parents=True)
    for part in ("model.yaml", "user.txt"):
        (d / part).write_text(
            bundled.joinpath(part).read_text(encoding="utf-8"), encoding="utf-8"
        )
    (d / "system.txt").write_text(system_text, encoding="utf-8")
    return d


def test_ai_prompt_model_loads_from_bundle_when_repo_lacks_artifact(
    tmp_path: Path,
) -> None:
    from shared.ai.prompt_model import PromptModel

    model = PromptModel.load(ARTIFACT, prompts_root=tmp_path)
    assert model.manifest.id
    assert tmp_path not in Path(str(model._artifact._artifact_path)).parents


def test_ai_prompt_model_prefers_repo_artifact(tmp_path: Path) -> None:
    from shared.ai.prompt_model import PromptModel

    _write_repo_artifact(tmp_path, ARTIFACT, "REPO COPY WINS")
    model = PromptModel.load(ARTIFACT, prompts_root=tmp_path)
    assert model._artifact.system_text == "REPO COPY WINS"


def test_ai_prompt_model_missing_artifact_raises_clearly(tmp_path: Path) -> None:
    from shared.ai.prompt_model import PromptModel

    with pytest.raises(FileNotFoundError, match=r"missing model\.yaml at"):
        PromptModel.load("no_such_prompt", prompts_root=tmp_path)


def test_ai_prompt_model_partial_repo_artifact_is_not_patched_from_bundle(
    tmp_path: Path,
) -> None:
    """A repo artifact that has model.yaml but lacks system.txt is the
    repository's artifact -- it fails on its own terms, not silently
    completed from the bundle."""
    from shared.ai.prompt_model import PromptModel

    bundled = bundled_prompt(ARTIFACT)
    assert bundled is not None
    d = tmp_path / ARTIFACT
    d.mkdir()
    (d / "model.yaml").write_text(
        bundled.joinpath("model.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    with pytest.raises(FileNotFoundError, match=r"missing system\.txt"):
        PromptModel.load(ARTIFACT, prompts_root=tmp_path)


# --- shared.models.PromptModel.load -----------------------------------------


def test_models_prompt_model_loads_from_bundle_when_repo_lacks_artifact(
    tmp_path: Path,
) -> None:
    from shared.models.prompt_model import PromptModel

    with patch("shared.models.prompt_model.settings") as settings:
        settings.paths.prompts_dir = tmp_path
        model = PromptModel.load(ARTIFACT)
    assert model.manifest.id


def test_models_prompt_model_prefers_repo_artifact(tmp_path: Path) -> None:
    from shared.models.prompt_model import PromptModel

    _write_repo_artifact(tmp_path, ARTIFACT, "REPO COPY WINS")
    with patch("shared.models.prompt_model.settings") as settings:
        settings.paths.prompts_dir = tmp_path
        model = PromptModel.load(ARTIFACT)
    assert model._system_prompt == "REPO COPY WINS"


def test_models_prompt_model_missing_artifact_raises_clearly(tmp_path: Path) -> None:
    from shared.models.prompt_model import PromptModel

    with patch("shared.models.prompt_model.settings") as settings:
        settings.paths.prompts_dir = tmp_path
        with pytest.raises(FileNotFoundError, match="missing required file"):
            PromptModel.load("no_such_prompt")


# --- external runner --------------------------------------------------------


def test_runner_prompt_root_prefers_repository_even_if_incomplete(
    tmp_path: Path,
) -> None:
    from cli.runtime_external_run import runner_prompt_root, runner_prompt_sources

    repo_prompts = PathResolver(tmp_path).prompts_dir
    (repo_prompts / "something_else").mkdir(parents=True)
    (repo_prompts / "something_else" / "model.yaml").write_text(
        "id: x\n", encoding="utf-8"
    )
    with runner_prompt_root(tmp_path) as root:
        assert root == repo_prompts
        with pytest.raises(Exception, match="lacks the planner artifacts"):
            runner_prompt_sources(tmp_path, prompts_root=root)


def test_runner_prompt_root_falls_back_to_bundle_when_repo_has_no_root(
    tmp_path: Path,
) -> None:
    from cli.runtime_external_run import (
        PLANNER_PROMPT_IDS,
        runner_prompt_root,
        runner_prompt_sources,
    )

    with runner_prompt_root(tmp_path) as root:
        assert isinstance(root, Path) and root.is_dir()
        assert tmp_path not in root.parents
        sources = runner_prompt_sources(tmp_path, prompts_root=root)
        assert set(PLANNER_PROMPT_IDS) <= set(sources)
        assert LOOSE in sources
        assert "__init__.py" not in sources
        assert all(p.exists() for p in sources.values())


def test_runner_prompt_sources_without_root_refuses_when_repo_has_none(
    tmp_path: Path,
) -> None:
    from cli.runtime_external_run import runner_prompt_sources

    with pytest.raises(Exception, match="does not exist"):
        runner_prompt_sources(tmp_path)
