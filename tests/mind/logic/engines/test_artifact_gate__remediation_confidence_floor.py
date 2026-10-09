"""#964: autonomy.remediation.min_confidence_floor is checked where the
decision is written -- auto_remediation.yaml -- by artifact_gate's
remediation_confidence_floor check. Fixture pair for the G2 registry."""

from __future__ import annotations

from pathlib import Path

from mind.logic.engines.artifact_gate import _check_remediation_confidence_floor


_REPO_ROOT = Path(__file__).resolve().parents[4]
_CHECK = "remediation_confidence_floor"


def _repo(tmp_path: Path, mappings: str, floor: str = "0.80") -> Path:
    remediation = tmp_path / ".intent" / "enforcement" / "remediation"
    config = tmp_path / ".intent" / "enforcement" / "config"
    remediation.mkdir(parents=True)
    config.mkdir(parents=True)
    (remediation / "auto_remediation.yaml").write_text("mappings:\n" + mappings)
    (config / "governance_paths.yaml").write_text(
        f"remediation:\n  min_confidence: {floor}\n"
    )
    return tmp_path


# ID: 5d8812cf-4b22-42ae-8f65-0b37cc19069c
def test_active_entry_below_floor_is_a_violation(tmp_path: Path) -> None:
    repo = _repo(
        tmp_path,
        "  some.rule:\n    action: fix.x\n    confidence: 0.79\n    status: ACTIVE\n",
    )
    result = _check_remediation_confidence_floor(repo, _CHECK)
    assert not result.ok
    assert any("'some.rule'" in v and "0.79" in v for v in result.violations)


# ID: 725eaa93-4865-4153-b6ea-7f04ab139cb9
def test_entries_at_or_above_floor_pass(tmp_path: Path) -> None:
    """ACTIVE at the floor passes; DELEGATE / PENDING may sit below it, since
    they never produce proposals."""
    repo = _repo(
        tmp_path,
        "  a.rule:\n    action: fix.a\n    confidence: 0.80\n    status: ACTIVE\n"
        "  b.rule:\n    confidence: 0.40\n    status: DELEGATE\n"
        "  c.rule:\n    action: fix.c\n    confidence: 0.40\n    status: PENDING\n",
    )
    result = _check_remediation_confidence_floor(repo, _CHECK)
    assert result.ok, result.violations


# ID: 7db91e13-5ada-4a5a-bc8d-92cc81ed4a83
def test_missing_or_unknown_status_is_a_violation(tmp_path: Path) -> None:
    """The loader used to default a missing status to ACTIVE."""
    repo = _repo(
        tmp_path,
        "  no.status:\n    action: fix.x\n    confidence: 0.95\n"
        "  typo.status:\n    action: fix.y\n    confidence: 0.95\n    status: DELEGATED\n",
    )
    result = _check_remediation_confidence_floor(repo, _CHECK)
    assert not result.ok
    assert any("'no.status'" in v for v in result.violations)
    assert any("'typo.status'" in v for v in result.violations)


# ID: da4e233d-a890-401c-800f-1a09f1dac3fe
def test_active_entry_without_confidence_is_a_violation(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "  some.rule:\n    action: fix.x\n    status: ACTIVE\n")
    result = _check_remediation_confidence_floor(repo, _CHECK)
    assert not result.ok


# ID: 4d0a5a06-aa28-40d3-a571-03758b411b67
def test_missing_floor_fails_closed(tmp_path: Path) -> None:
    repo = _repo(
        tmp_path,
        "  some.rule:\n    action: fix.x\n    confidence: 0.95\n    status: ACTIVE\n",
        floor="null",
    )
    result = _check_remediation_confidence_floor(repo, _CHECK)
    assert not result.ok
    assert "min_confidence" in result.violations[0]


# ID: 7393145a-39c8-4007-9fdc-33b1d51d21f4
def test_this_repository_satisfies_the_floor() -> None:
    result = _check_remediation_confidence_floor(_REPO_ROOT, _CHECK)
    assert result.ok, result.violations
