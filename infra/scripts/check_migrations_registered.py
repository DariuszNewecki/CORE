#!/usr/bin/env python3
# infra/scripts/check_migrations_registered.py
"""Pre-commit guard: SQL migrations under infra/scripts/migrations/ must be
registered in `migrations.order` within the database-migration policy.

#438: forward-looking enforcement against workflow-drift where SQL files
land outside the core-admin migrate framework. Runs against staged files
only — existing unregistered files are grandfathered until the governor
authorizes a bootstrap (see issue #438 'Out of scope').
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


POLICY_PATH = Path(".intent/rules/data/governance.json")
MIGRATIONS_PREFIX = "infra/scripts/migrations/"


def _registered_migrations(policy_path: Path) -> tuple[set[str], str | None]:
    """Return (registered_set, error_message). error_message is non-None
    when the policy cannot be read or has no `migrations:` block, in
    which case the caller should fail loudly so the gap is visible."""
    if not policy_path.exists():
        return set(), f"policy file missing: {policy_path}"
    try:
        policy = json.loads(policy_path.read_text())
    except json.JSONDecodeError as exc:
        return set(), f"policy file is invalid JSON ({policy_path}): {exc}"
    migrations = policy.get("migrations")
    if not isinstance(migrations, dict):
        return set(), (
            f"policy file has no `migrations:` block ({policy_path}); "
            "the migration framework is currently orphaned. Until the "
            "governor authorizes a bootstrap, the hook can only refuse "
            "new SQL files."
        )
    order = migrations.get("order", [])
    if not isinstance(order, list):
        return set(), f"`migrations.order` is not a list ({policy_path})"
    return set(order), None


def main(argv: list[str]) -> int:
    staged_sql = sorted(
        Path(p).name
        for p in argv
        if p.startswith(MIGRATIONS_PREFIX) and p.endswith(".sql")
    )
    if not staged_sql:
        return 0

    registered, policy_error = _registered_migrations(POLICY_PATH)
    unregistered = [f for f in staged_sql if f not in registered]
    if not unregistered:
        return 0

    print(
        "ERROR: SQL migration file(s) not registered in `migrations.order`:",
        file=sys.stderr,
    )
    for f in unregistered:
        print(f"  - {f}", file=sys.stderr)
    if policy_error:
        print(f"\nPolicy state: {policy_error}", file=sys.stderr)
    print(
        f"\nAdd each file to `migrations.order` in {POLICY_PATH} before committing.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
