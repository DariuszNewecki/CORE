#!/usr/bin/env python3
"""scripts/verify_test_partition.py — ADR-157 D3.4

Verify that the `unit`/`integration` pytest marker split used by
core-ci.yml's `hermetic` and `integration` jobs is an exhaustive,
non-overlapping partition of the full test suite.

`-m "not integration"` and `-m "integration"` are complementary by
construction over a fixed collection, so this check exists to catch
*drift*, not to prove math that already holds: a file silently failing to
collect in one job's environment (import error, missing fixture
dependency), a typo'd marker name slipping past `--strict-markers` in some
future refactor, or a `-k` filter accidentally layered on top of `-m`
later. Any of those would desynchronize the two job selectors from the
full collection without necessarily failing loudly on their own.

Exit codes:
  0 — the two selectors are disjoint and their union equals the full
      collection.
  1 — collection failed for one of the three invocations, or the two
      selectors overlap, or their union misses some test the full
      collection finds.
"""

from __future__ import annotations

import re
import subprocess
import sys


# The part after `::` must allow whitespace, not just \S+ -- a parametrized
# test ID can contain spaces (e.g. `test_foo[a b]`), and a strict \S+ here
# silently drops those from every set, which happens to cancel out in the
# disjoint/union check and would hide real gaps. Only the file-path prefix
# before `::` is space-free.
_NODE_ID_RE = re.compile(r"^(tests/\S+::.+)$")


def _collect(marker_expr: str | None) -> set[str] | None:
    """Run `pytest --collect-only -q --no-cov` and return the set of
    collected node IDs, or None if collection itself failed.

    --no-cov is required: pyproject.toml's global addopts include
    --cov=src, which a bare --collect-only invocation would otherwise
    inherit and use to create/overwrite coverage data as a side effect
    (ADR-157 D3's implementation checklist). -qq (not -q): addopts also
    carries -v, and pytest's verbosity flags are additive counters, not a
    single override -- one -q nets to the same verbosity as addopts' -v
    and prints pytest 9's tree-style collection view instead of flat
    `path::test` node IDs; two -q's are needed to net negative and get
    the flat, greppable format this script depends on.
    """
    cmd = ["poetry", "run", "pytest", "--collect-only", "-qq", "--no-cov"]
    if marker_expr is not None:
        cmd += ["-m", marker_expr]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode not in (0, 1):
        # pytest returns 1 for "tests failed" too, but --collect-only never
        # executes a test body, so 1 here means a collection *error*
        # (import failure, etc.) -- treat as a hard failure, not a normal
        # "some markers excluded everything" case (which is returncode 5,
        # unlikely here but not itself an error).
        print(f"collection failed for {cmd!r} (exit {result.returncode}):")
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        return None
    node_ids = {
        m.group(1)
        for raw_line in result.stdout.splitlines()
        if (m := _NODE_ID_RE.match(raw_line.rstrip()))
    }
    return node_ids


def main() -> int:
    full = _collect(None)
    unit = _collect("not integration")
    integration = _collect("integration")

    if full is None or unit is None or integration is None:
        print(
            "verify_test_partition: collection error, see above — not a partition defect."
        )
        return 1

    overlap = unit & integration
    union = unit | integration
    missing_from_union = full - union
    extra_in_union = union - full

    ok = True
    if overlap:
        ok = False
        print(f"NOT DISJOINT: {len(overlap)} test(s) collected by both selectors:")
        for node_id in sorted(overlap)[:20]:
            print(f"  {node_id}")
    if missing_from_union:
        ok = False
        print(
            f"NOT EXHAUSTIVE: {len(missing_from_union)} test(s) in the full collection "
            "but neither selector:"
        )
        for node_id in sorted(missing_from_union)[:20]:
            print(f"  {node_id}")
    if extra_in_union:
        ok = False
        print(
            f"PHANTOM: {len(extra_in_union)} test(s) collected by a selector but not "
            "the full collection (should be impossible):"
        )
        for node_id in sorted(extra_in_union)[:20]:
            print(f"  {node_id}")

    if not ok:
        return 1

    print(
        f"verify_test_partition: OK — {len(full)} total, "
        f"{len(unit)} unit / {len(integration)} integration, disjoint and exhaustive."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
