# tests/body/quality/test_coverage_candidate_selector.py
"""Tests for select_batch_candidates (#814 — extracted from BatchRemediationService)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from body.quality.coverage_candidate_selector import select_batch_candidates


def _mock_coverage(data: dict[str, float]):
    return patch(
        "body.quality.coverage_candidate_selector.CoverageAnalyzer.get_module_coverage",
        return_value=data,
    )


def _mock_threshold(pct: float):
    # CoverageConfig is a frozen dataclass — replace the module-level _CFG
    # reference wholesale rather than assigning to one of its fields.
    return patch(
        "body.quality.coverage_candidate_selector._CFG",
        MagicMock(batch_remediation_threshold_pct=pct),
    )


def test_empty_coverage_data_returns_no_candidates(tmp_path) -> None:
    with _mock_coverage({}):
        result = select_batch_candidates(tmp_path, count=5)
    assert result == []


def test_filters_to_src_files_below_threshold(tmp_path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "low.py").write_text("def f(): pass\n")
    (tmp_path / "src" / "high.py").write_text("def f(): pass\n")

    coverage = {
        "src/low.py": 10.0,
        "src/high.py": 95.0,
        "tests/not_src.py": 5.0,
    }
    with _mock_coverage(coverage), _mock_threshold(75.0):
        result = select_batch_candidates(tmp_path, count=5)

    result_paths = {str(p) for p, _ in result}
    assert str(tmp_path / "src" / "low.py") in result_paths
    assert str(tmp_path / "src" / "high.py") not in result_paths
    assert not any("not_src.py" in p for p in result_paths)


def test_sorted_by_lowest_coverage_first(tmp_path) -> None:
    (tmp_path / "src").mkdir()
    for name in ("a.py", "b.py", "c.py"):
        (tmp_path / "src" / name).write_text("def f(): pass\n")

    coverage = {"src/a.py": 40.0, "src/b.py": 10.0, "src/c.py": 60.0}
    with _mock_coverage(coverage), _mock_threshold(75.0):
        result = select_batch_candidates(tmp_path, count=5)

    assert [p.name for p, _ in result] == ["b.py", "a.py", "c.py"]


def test_count_truncates_after_complexity_filtering_not_before(tmp_path) -> None:
    """Complexity filtering must run on the full below-threshold set before
    truncation — otherwise a low-count caller could get fewer than `count`
    results even when enough simple candidates exist further down the list."""
    (tmp_path / "src").mkdir()
    # First-ranked file is too complex (many branches); second and third are simple.
    complex_body = "\n".join(f"    if x == {i}: return {i}" for i in range(60))
    (tmp_path / "src" / "complex.py").write_text(f"def f(x):\n{complex_body}\n")
    (tmp_path / "src" / "simple_one.py").write_text("def f(): pass\n")
    (tmp_path / "src" / "simple_two.py").write_text("def f(): pass\n")

    coverage = {
        "src/complex.py": 5.0,
        "src/simple_one.py": 10.0,
        "src/simple_two.py": 15.0,
    }
    with _mock_coverage(coverage), _mock_threshold(75.0):
        result = select_batch_candidates(tmp_path, count=2)

    result_names = {p.name for p, _ in result}
    assert result_names == {"simple_one.py", "simple_two.py"}


def test_nonexistent_file_skipped(tmp_path) -> None:
    coverage = {"src/gone.py": 10.0}
    with _mock_coverage(coverage), _mock_threshold(75.0):
        result = select_batch_candidates(tmp_path, count=5)
    assert result == []
