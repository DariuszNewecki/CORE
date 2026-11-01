"""#1387: the prompt root comes from governance_paths.yaml, else var/prompts."""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.path_resolver import PathResolver


def _repo(tmp_path: Path, config: str | None) -> Path:
    cfg = tmp_path / ".intent" / "enforcement" / "config"
    cfg.mkdir(parents=True)
    if config is not None:
        (cfg / "governance_paths.yaml").write_text(config)
    return tmp_path


def _resolver(root: Path) -> PathResolver:
    return PathResolver.from_repo(root, intent_root=root / ".intent")


def test_declared_root_is_used(tmp_path: Path) -> None:
    root = _repo(tmp_path, 'prompts:\n  root: "src/shared/_prompts"\n')
    assert _resolver(root).prompts_dir == root / "src" / "shared" / "_prompts"


@pytest.mark.parametrize(
    "config",
    [
        None,
        "audit_findings:\n  raw_path: x\n",
        'prompts:\n  root: "/etc/prompts"\n',
        'prompts:\n  root: "../outside"\n',
        "prompts: [not, a, mapping]\n",
        ": not yaml : [",
    ],
)
def test_absent_or_unsafe_value_falls_back_to_var_prompts(
    tmp_path: Path, config: str | None
) -> None:
    root = _repo(tmp_path, config)
    assert _resolver(root).prompts_dir == root / "var" / "prompts"


def test_cores_own_law_points_at_the_packaged_corpus() -> None:
    repo = Path(__file__).resolve().parents[2]
    assert PathResolver(repo).prompts_dir == repo / "src" / "shared" / "_prompts"
