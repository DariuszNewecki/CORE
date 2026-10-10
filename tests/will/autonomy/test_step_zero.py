# tests/will/autonomy/test_step_zero.py
"""Step 0 report (ADR-168 Amendment 2026-10-10 R4; build plan U3).

Real git repository and real ADR files; only the embedding and vector search
are stand-ins (they need the model registry and Qdrant)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from will.autonomy.step_zero import build_step_zero_report


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _repo(root: Path) -> Path:
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t.invalid")
    _git(root, "config", "user.name", "t")
    _git(root, "config", "commit.gpgsign", "false")
    (root / "src" / "pkg").mkdir(parents=True)
    (root / "src" / "pkg" / "old.py").write_text("def gone():\n    return 1\n")
    decisions = root / ".specs" / "decisions"
    decisions.mkdir(parents=True)
    (decisions / "ADR-005-pkg.md").write_text(
        "---\nid: ADR-005\ntitle: Pkg\nstatus: accepted\n---\nGoverns pkg.old.\n"
    )
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "feat: pkg per ADR-005")
    return root


_PATCH = (
    "diff --git a/src/pkg/old.py b/src/pkg/old.py\n"
    "deleted file mode 100644\n"
    "--- a/src/pkg/old.py\n"
    "+++ /dev/null\n"
    "@@ -1,2 +0,0 @@\n"
    "-def gone():\n"
    "-    return 1\n"
    "diff --git a/src/pkg/new.py b/src/pkg/new.py\n"
    "new file mode 100644\n"
    "--- /dev/null\n"
    "+++ b/src/pkg/new.py\n"
    "@@ -0,0 +1,2 @@\n"
    "+def fresh():\n"
    "+    return 2\n"
)


def _cognitive(vector: list[float] | None, hits: list | Exception) -> MagicMock:
    qdrant = MagicMock()
    qdrant.collection_name = "core-code"
    qdrant.search = AsyncMock(
        side_effect=hits if isinstance(hits, Exception) else None,
        return_value=None if isinstance(hits, Exception) else hits,
    )
    service = MagicMock()
    service.qdrant_service = qdrant
    service.get_embedding_for_code = AsyncMock(return_value=vector)
    return service


# ID: 52a9b671-93e2-43b5-b73d-8783ae419e09
async def test_report_answers_retires_decisions_and_look_alikes(tmp_path: Path) -> None:
    hit = SimpleNamespace(
        score=0.91234, payload={"file_path": "src/pkg/old.py", "section": "gone"}
    )
    service = _cognitive([0.1, 0.2], [hit])

    report = await build_step_zero_report(
        patch=_PATCH,
        retires=["src/pkg/old.py", "src/pkg/new.py::fresh"],
        repo_root=_repo(tmp_path),
        cognitive_service=service,
    )

    assert [r["verified"] for r in report["retires"]] == [True, False]
    assert report["retires_all_verified"] is False
    assert report["decisions"]["mentions"]["src/pkg/old.py"][0]["id"] == "ADR-005"
    assert report["decisions"]["history"] == {"src/pkg/old.py": ["ADR-005"]}
    assert report["look_alikes"]["status"] == "ran"
    assert report["look_alikes"]["symbols"] == [
        {
            "file": "src/pkg/new.py",
            "symbol": "fresh",
            "matches": [{"file": "src/pkg/old.py", "symbol": "gone", "score": 0.912}],
        }
    ]
    embedded = service.get_embedding_for_code.await_args.args[0]
    assert embedded == "def fresh():\n    return 2"


# ID: c8a81121-85d3-4b06-aaf6-db40f54c3a9d
async def test_failed_search_is_unavailable_not_nothing_found(tmp_path: Path) -> None:
    report = await build_step_zero_report(
        patch=_PATCH,
        retires=[],
        repo_root=_repo(tmp_path),
        cognitive_service=_cognitive([0.1], RuntimeError("qdrant down")),
    )
    assert report["look_alikes"] == {
        "status": "unavailable",
        "reason": "qdrant down",
        "symbols": [],
    }


# ID: aa6423a9-11bd-4824-aab6-d1b52f12ecdd
async def test_missing_embedding_is_unavailable(tmp_path: Path) -> None:
    report = await build_step_zero_report(
        patch=_PATCH,
        retires=[],
        repo_root=_repo(tmp_path),
        cognitive_service=_cognitive(None, []),
    )
    assert report["look_alikes"]["status"] == "unavailable"


# ID: 269469ba-9aa5-4ea4-99aa-99c3cc7e1581
async def test_a_patch_with_no_new_symbol_searches_nothing(tmp_path: Path) -> None:
    service = _cognitive([0.1], [])
    only_delete = _PATCH.split("diff --git a/src/pkg/new.py")[0]

    report = await build_step_zero_report(
        patch=only_delete,
        retires=["src/pkg/old.py"],
        repo_root=_repo(tmp_path),
        cognitive_service=service,
    )

    assert report["look_alikes"]["status"] == "nothing_new"
    assert report["retires_all_verified"] is True
    service.get_embedding_for_code.assert_not_awaited()
