"""architecture.intent.references_resolve — every covered .intent/ field
fires on a dangling reference and stays quiet when the target exists."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from mind.logic.engines.reference_gate import (
    ReferenceGateEngine,
    find_dangling_references,
)


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A minimal repository in which every covered reference resolves."""
    _write(
        tmp_path,
        "src/body/actions.py",
        "@atomic_action(action_id='sync.real')\nasync def a(**kwargs): ...\n",
    )
    _write(tmp_path, "src/will/workers/solo.py", "class SoloWorker: ...\n")
    _write(
        tmp_path,
        "src/will/workers/pkg/__init__.py",
        "from .impl import PkgWorker\n",
    )
    _write(tmp_path, "src/will/workers/pkg/impl.py", "class PkgWorker: ...\n")
    _write(
        tmp_path,
        ".intent/flows/flow.x.yaml",
        "kind: flow\nflow:\n  steps:\n"
        "    - {ref_id: sync.real, kind: action}\n"
        "    - {ref_id: some.cognitive.role, kind: cognitive}\n",
    )
    _write(
        tmp_path,
        ".intent/enforcement/config/test_coverage.yaml",
        "include_files:\n  - src/will/workers/solo.py\n",
    )
    _write(
        tmp_path,
        ".intent/enforcement/mappings/code/purity.yaml",
        "mappings:\n  purity.no_orphan_files:\n    params:\n"
        "      entry_points: ['src/will/workers/', 'src/body/actions.py']\n",
    )
    _write(
        tmp_path,
        ".intent/workers/solo.yaml",
        "implementation:\n  module: will.workers.solo\n  class: SoloWorker\n",
    )
    _write(
        tmp_path,
        ".intent/workers/pkg.yaml",
        "implementation:\n  module: will.workers.pkg\n  class: PkgWorker\n",
    )
    _write(
        tmp_path,
        ".intent/governance/namespace_manifest.yaml",
        "classifications:\n"
        "  - {path: .intent/workers/solo.yaml}\n"
        "  - {path: .specs/local-only/gitignored.md}\n",
    )
    return tmp_path


def _refs(root: Path) -> set[tuple[str, str]]:
    return {
        (f.context["field"], f.context["reference"])
        for f in find_dangling_references(root)
    }


def test_clean_repository_has_no_findings(repo: Path) -> None:
    assert _refs(repo) == set()


def test_renamed_flow_action_fires(repo: Path) -> None:
    _write(
        repo,
        ".intent/flows/flow.y.yaml",
        "kind: flow\nflow:\n  steps:\n    - {ref_id: sync.renamed, kind: action}\n",
    )
    findings = find_dangling_references(repo)
    assert {(f.context["field"], f.context["reference"]) for f in findings} == {
        ("flow.steps[].ref_id", "sync.renamed")
    }
    assert findings[0].file_path == ".intent/flows/flow.y.yaml"


def test_deleted_include_file_fires(repo: Path) -> None:
    (repo / "src/will/workers/solo.py").unlink()
    refs = _refs(repo)
    assert ("include_files", "src/will/workers/solo.py") in refs
    # The worker declaration pointing at the same module fires too.
    assert ("implementation.module", "will.workers.solo") in refs


def test_missing_entry_point_fires(repo: Path) -> None:
    _write(
        repo,
        ".intent/enforcement/mappings/code/other.yaml",
        "mappings:\n  some.rule:\n    params:\n      entry_points: ['src/gone/']\n",
    )
    assert _refs(repo) == {("some.rule.params.entry_points", "src/gone/")}


def test_worker_class_missing_fires_but_reexport_resolves(repo: Path) -> None:
    _write(
        repo,
        ".intent/workers/pkg.yaml",
        "implementation:\n  module: will.workers.pkg\n  class: RenamedWorker\n",
    )
    assert _refs(repo) == {("implementation.class", "RenamedWorker")}


def test_manifest_checks_intent_paths_only(repo: Path) -> None:
    _write(
        repo,
        ".intent/governance/namespace_manifest.yaml",
        "classifications:\n  - {path: .intent/packs/gone.yaml}\n"
        "  - {path: .specs/local-only/gitignored.md}\n",
    )
    assert _refs(repo) == {("classifications[].path", ".intent/packs/gone.yaml")}


async def test_engine_dispatches_context_level(repo: Path) -> None:
    engine = ReferenceGateEngine(path_resolver=None)  # type: ignore[arg-type]
    assert ReferenceGateEngine.is_context_level_for("intent_references_resolve")
    (repo / "src/will/workers/solo.py").unlink()
    findings = await engine.verify_context(
        SimpleNamespace(repo_path=repo),  # type: ignore[arg-type]
        {"check_type": "intent_references_resolve"},
    )
    assert findings and all(
        f.check_id == "architecture.intent.references_resolve" for f in findings
    )
    unknown = await engine.verify_context(
        SimpleNamespace(repo_path=repo),  # type: ignore[arg-type]
        {"check_type": "nope"},
    )
    assert unknown[0].check_id == "reference_gate.unknown_check_type"
