"""Review finding F1 (2026-10-23): a hand-started CI run cannot fake green.

A workflow_dispatch run posts its check results on the head of the ref it
was started on. When it tested another commit (the old ``sha`` input), or
skipped a required job, it could replace a red result on that head. Every
job must test the run's own commit and run on every event.
"""

from __future__ import annotations

from pathlib import Path

import yaml


WORKFLOW = Path(__file__).resolve().parents[2] / ".github/workflows/core-ci.yml"


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text())


def test_dispatch_takes_no_commit_input() -> None:
    triggers = _workflow()[True]  # YAML 1.1 reads the key `on` as True
    assert not (triggers["workflow_dispatch"] or {}).get("inputs")
    assert "inputs." not in WORKFLOW.read_text()


def test_every_checkout_tests_the_runs_own_commit() -> None:
    for name, job in _workflow()["jobs"].items():
        for step in job.get("steps", []):
            if str(step.get("uses", "")).startswith("actions/checkout"):
                assert "ref" not in (step.get("with") or {}), name


def test_no_job_skips_a_hand_started_run() -> None:
    for name, job in _workflow()["jobs"].items():
        assert "workflow_dispatch" not in str(job.get("if", "")), name
