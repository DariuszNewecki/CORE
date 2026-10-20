# src/cli/logic/test_symbol_ledger.py

"""
One row per public symbol in test-coverage scope: does it have a test, is
that test failing, and how many generation attempts has it taken.

The pieces already existed in three places nobody joined (2026-10-20): the
gap check (shared.utils.public_symbols, the same matching TestGapEvaluator
uses), the runner sensor's open ``python::test.runner.failure`` findings,
and the flow.build_test_for_symbol proposal history. `tests symbols` reads
the last two from the database and joins them here. No Rich, no I/O beyond
reading source and test files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from shared.infrastructure.intent.test_coverage_paths import source_to_test_path
from shared.utils.public_symbols import (
    extract_public_symbols,
    leaf_name_counts,
    name_key,
    symbol_is_tested,
    tested_symbol_names,
)


__all__ = [
    "STATUSES",
    "AttemptStats",
    "SymbolRow",
    "build_symbol_ledger",
    "failing_test_names",
]

# Display order. Every row has exactly one status.
STATUSES = ("passing", "failing", "untested", "capped", "unreadable")


@dataclass
# ID: b62e83f5-2a52-4d6e-a718-d6b0666e33d6
class AttemptStats:
    """flow.build_test_for_symbol history for one (source_file, symbol)."""

    completed: int = 0
    failed: int = 0
    last_failure: str | None = None


@dataclass
# ID: a653aa9c-7184-45b2-a4c9-d873f273194d
class SymbolRow:
    """One public symbol and where it stands."""

    source_file: str
    symbol: str
    kind: str
    status: str
    attempts: AttemptStats = field(default_factory=AttemptStats)


# ID: f2dbb314-3c87-4b51-bb63-951aef405a38
def failing_test_names(subjects: list[str]) -> dict[str, set[str]]:
    """Map test_file -> tested names, from open test.runner.failure subjects.

    Subject (ADR-091 D2): ``python::test.runner.failure::<test_file>::<node>``
    where node is pytest's id, e.g. ``tests/x/test_generated.py::test_run`` or
    ``...::TestSvc::test_go[param]``. Names follow tested_symbol_names:
    ``run`` and ``Svc.go``.
    """
    failing: dict[str, set[str]] = {}
    for subject in subjects:
        parts = subject.split("::")
        if len(parts) < 4:
            continue
        test_file = parts[2]
        node = [p.split("[", 1)[0] for p in parts[3:] if p != test_file]
        func = node[-1] if node else ""
        if not func.startswith("test_"):
            continue
        name = func[5:]
        if len(node) >= 2 and node[-2].startswith("Test"):
            name = f"{node[-2][4:]}.{name}"
        failing.setdefault(test_file, set()).add(name)
    return failing


# ID: 8d1906c2-a080-47ba-bdae-df84b15e69fe
def build_symbol_ledger(
    repo_root: Path,
    source_files: list[str],
    config: dict[str, Any],
    attempts: dict[tuple[str, str], AttemptStats],
    failing: dict[str, set[str]],
    cap_n: int,
) -> list[SymbolRow]:
    """Join the gap check, failing tests and attempt history per symbol.

    passing:    a test is credited to it and no open failure names it
    failing:    a credited test has an open test.runner.failure finding
    untested:   no credited test; under the attempt cap
    capped:     no credited test; attempts (completed + failed) reached
                cap_n, so the remediator no longer tries it (ADR-133 D4)
    unreadable: the source file cannot be parsed (one row, symbol "*")
    """
    rows: list[SymbolRow] = []
    for source_file in sorted(source_files):
        try:
            symbols = extract_public_symbols(repo_root / source_file)
        except (SyntaxError, UnicodeDecodeError, OSError):
            rows.append(SymbolRow(source_file, "*", "module", "unreadable"))
            continue
        test_file = source_to_test_path(source_file, config)
        try:
            tested = tested_symbol_names(repo_root / test_file)
        except (SyntaxError, UnicodeDecodeError, OSError):
            tested = set()
        tested_keys = {name_key(n) for n in tested}
        failing_keys = {name_key(n) for n in failing.get(test_file, set())}
        leaf_counts = leaf_name_counts([s.name for s in symbols])
        for sym in symbols:
            stats = attempts.get((source_file, sym.name), AttemptStats())
            if symbol_is_tested(sym.name, tested_keys, leaf_counts):
                status = (
                    "failing"
                    if symbol_is_tested(sym.name, failing_keys, leaf_counts)
                    else "passing"
                )
            elif stats.completed + stats.failed >= cap_n:
                status = "capped"
            else:
                status = "untested"
            rows.append(SymbolRow(source_file, sym.name, sym.kind, status, stats))
    return rows
