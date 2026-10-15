"""core-law's venv against the live release, by wheel hash (#1018)."""

from __future__ import annotations

import json
from pathlib import Path

from shared.infrastructure.law_venv import check_law_venv


LIVE = "a" * 40
WHEEL = "1" * 64


def _host(
    tmp: Path, venv_sha: str = LIVE, venv_wheel: str = WHEEL, pip_wheel: str = WHEEL
):
    status = tmp / "status.json"
    status.write_text(json.dumps({"live": LIVE}))
    rel = tmp / "releases" / LIVE / "venv"
    rel.mkdir(parents=True)
    (rel / "core-release.json").write_text(
        json.dumps({"sha": LIVE, "wheel_sha256": WHEEL})
    )
    venv = tmp / "law-venv"
    dist = (
        venv / "lib" / "python3.12" / "site-packages" / "core_runtime-2.14.5.dist-info"
    )
    dist.mkdir(parents=True)
    (venv / "core-release.json").write_text(
        json.dumps({"sha": venv_sha, "wheel_sha256": venv_wheel})
    )
    (dist / "direct_url.json").write_text(
        json.dumps({"archive_info": {"hashes": {"sha256": pip_wheel}}})
    )
    return status, tmp / "releases", venv


# ID: 8d1cc29d-1790-4e2c-942b-6db0c6e6c7bb
def test_matching_venv_has_no_problem(tmp_path: Path) -> None:
    state = check_law_venv(*_host(tmp_path))
    assert state.applies and state.problem is None


# ID: 7febe187-2df1-4f94-a18d-3aa0f698d9b7
def test_a_different_wheel_is_a_problem(tmp_path: Path) -> None:
    state = check_law_venv(
        *_host(tmp_path, venv_sha="b" * 40, venv_wheel="2" * 64, pip_wheel="2" * 64)
    )
    assert state.problem and "live release is aaaaaaaaaaaa" in state.problem


# ID: d477ea32-7bd9-45b2-bf1d-137c05f30e50
def test_a_record_that_disagrees_with_pip_is_a_problem(tmp_path: Path) -> None:
    state = check_law_venv(*_host(tmp_path, pip_wheel="3" * 64))
    assert state.problem


# ID: 719a1102-cbd2-4c96-bbc7-7ccadeeaac1f
def test_a_missing_or_unreadable_venv_is_a_problem(tmp_path: Path) -> None:
    status, releases, venv = _host(tmp_path)
    (venv / "core-release.json").unlink()
    assert "unreadable" in (check_law_venv(status, releases, venv).problem or "")


# ID: 8aaf5230-0cec-4774-b1de-8edf9e4d4e1a
def test_a_host_without_the_runtime_is_not_applicable(tmp_path: Path) -> None:
    state = check_law_venv(tmp_path / "absent.json", tmp_path, tmp_path)
    assert not state.applies and state.problem is None
