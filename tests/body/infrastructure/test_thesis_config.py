"""The thesis sensor reads the governor's GitHub login where the runner does."""

from __future__ import annotations

from pathlib import Path

from body.infrastructure.thesis_config import pipeline_governor


def test_pipeline_governor_reads_the_runners_conf(tmp_path: Path) -> None:
    conf = tmp_path / "pipeline.conf"
    conf.write_text('# x\nGITHUB_REPO=o/n\nGOVERNOR_GITHUB="someone"\nBRANCH=main\n')
    assert pipeline_governor(conf) == "someone"
    conf.write_text("GITHUB_REPO=o/n\n")
    assert pipeline_governor(conf) is None
    assert pipeline_governor(tmp_path / "missing") is None
