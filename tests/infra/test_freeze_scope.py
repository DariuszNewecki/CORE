"""freeze_scope.py: the freeze-scope PR check (governor 2026-10-23)."""

from __future__ import annotations

import datetime as dt
import importlib.util
from pathlib import Path

import yaml


_ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "freeze_scope", _ROOT / "infra/scripts/freeze_scope.py"
)
assert _SPEC and _SPEC.loader
fs = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(fs)

DURING = dt.datetime(2026, 10, 24, 12, 0, tzinfo=dt.UTC)
AFTER = dt.datetime(2026, 10, 30, 0, 0, tzinfo=dt.UTC)
NEXT = {1300, 1301}


def test_passes_with_an_exit_issue() -> None:
    ok, why = fs.verdict("Measure 5. Part of #1114.", "fix/x", DURING, NEXT)
    assert ok and "1114" in why
    assert fs.verdict("https://github.com/o/r/issues/1070", "fix/x", DURING, set())[0]


def test_passes_with_a_3_1_issue() -> None:
    ok, why = fs.verdict("Filed as #1301 for later.", "fix/x", DURING, NEXT)
    assert ok and "CORE 3.1" in why


def test_fails_with_neither() -> None:
    ok, why = fs.verdict("Fixes #1999; see PR #12.", "fix/x", DURING, NEXT)
    assert not ok and "Freeze until 2026-10-29" in why
    assert not fs.verdict("", "fix/x", DURING, NEXT)[0]
    assert not fs.verdict("#10550 only", "fix/x", DURING, NEXT)[0]
    assert not fs.verdict("x#1055y", "fix/x", DURING, NEXT)[0]  # not a reference


def test_a_3_1_list_that_cannot_be_read_fails_closed() -> None:
    ok, why = fs.verdict("Filed as #1301.", "fix/x", DURING, None)
    assert not ok and "not readable" in why
    assert fs.verdict("Part of #1055.", "fix/x", DURING, None)[0]


def test_promotions_and_core_test_gen_are_exempt() -> None:
    assert fs.verdict("", "promote/23d10ebe09ef", DURING, NEXT)[0]
    assert fs.verdict("", "core/test-gen", DURING, NEXT)[0]
    assert not fs.verdict("", "promotex", DURING, NEXT)[0]


def test_after_the_freeze_everything_passes() -> None:
    assert fs.verdict("", "fix/x", AFTER, NEXT) == (
        True,
        "the freeze ended at 2026-10-29 23:59Z",
    )
    edge = fs.FREEZE_END
    assert not fs.verdict("", "fix/x", edge, NEXT)[0]  # the last minute still binds


def test_the_check_is_named_freeze_scope_and_pull_request_only() -> None:
    workflow = yaml.safe_load(
        (_ROOT / ".github/workflows/freeze-scope.yml").read_text()
    )
    assert list(workflow["jobs"]) == ["freeze-scope"]
    for script in ("infra/core-pipeline", "infra/core-deploy"):
        text = (_ROOT / script).read_text()
        assert '"freeze-scope"' in text.split("PULL_REQUEST_ONLY = ")[1].split("\n")[0]


def test_1285_is_an_exit_issue() -> None:
    # Governor 2026-10-23: the #1070 drill's gap joins the exit list.
    assert 1285 in fs.EXIT_ISSUES
    assert fs.verdict("Part of #1285.", "fix/x", DURING, set())[0]
