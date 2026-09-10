"""Unit E child process: the real governed fix.format mutation attempt,
run against a target that already carries staged (uncommitted) operator
work outside the Proposal's scope.

Invoked as ``python unit_e_child.py <target_path> <result_path>`` with
``REPO_PATH``, ``MIND``, and ``DATABASE_URL`` already bound in the
environment by the parent orchestrator (``unit_e_orchestrator.py``) --
identical invocation contract to Unit D's child.

Reuses ``unit_d_child.py``'s ``_run()`` unmodified except for the
Proposal's ``goal`` string (see that module's docstring for the added
parameter). Unit E's premise is precisely that this exact real
construction/approval/worker-invocation sequence -- unchanged -- refuses
the autonomous commit when ``scripts/outside.py`` is staged outside the
``package/example.py`` production set before this process starts
(ADR-129 D1's ``commit_paths()`` Layer-1 check), and rolls the production
set back via ``rollback_proposal`` (ADR-101 D3) rather than completing.
Nothing in this module performs that staging, and nothing here mocks,
monkeypatches, or bypasses the executor -- see ``unit_e_orchestrator.py``
for the pre-run setup and post-run evidence verification.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))

from unit_d_child import _fail, _run


_GOAL = (
    "Unit E: live post-propagation rollback qualification -- staged "
    "scripts/outside.py contamination must refuse the autonomous commit "
    "of package/example.py (ADR-129 D1) and roll back cleanly (ADR-101 D3)"
)


def main() -> int:
    target = Path(sys.argv[1])
    result_path = Path(sys.argv[2])

    try:
        result = asyncio.run(_run(target, goal=_GOAL))
    except Exception as exc:  # captured, never a bare crash with no evidence
        result = _fail("unhandled_exception", f"{type(exc).__name__}: {exc}")

    result_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
