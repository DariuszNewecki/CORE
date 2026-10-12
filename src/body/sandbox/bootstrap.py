# src/body/sandbox/bootstrap.py
"""
Trusted bootstrap for a sandbox pytest job (ADR-132 D10.10).

Run as a script, never imported by the services:
``python -I <this file> '<spec as JSON>'``. It comes from the release, not from
the snapshot, and it imports only the standard library before pytest.
Importing anything of CORE here would load the release's copy, and the
candidate check would then refuse the job.

``python -I`` ignores ``PYTHONPATH`` and does not add the script's directory,
so the snapshot is made importable by *prepending* its ``src`` and its root
to the interpreter's own isolated ``sys.path``; the standard library,
extension-module and site-packages entries stay as they are.

The spec (JSON, one argv element) names: ``snapshot`` (the read-only inbox directory),
``targets``, ``markers`` (or null), ``exclude_integration``, ``report_fd``
(an inherited pipe the report is written to, so test output on stdout cannot
be mistaken for it). The report holds the counts, the tests the
sandbox excluded, and an ``error`` when the candidate was not the code
that ran.

Stated limit: the counting plugin runs in the same process as the tests,
so hostile test code can lie about its own results. The sandbox protects
the credential, not the truthfulness of the code it runs.

CONSTITUTIONAL ALIGNMENT:
- Runs only inside the sandbox (service: the core-sandbox account; local:
  the caller, labelled ``isolation: local``). Writes only its report.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any


_INTEGRATION = "integration"


class _Counter:
    def __init__(self, exclude_integration: bool) -> None:
        self.exclude_integration = exclude_integration
        self.counts = {
            "collected": 0,
            "executed": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "deselected": 0,
        }
        self.excluded: list[str] = []

    # ID: b592c847-b22b-4e2b-a393-e74f5ad1314e
    def pytest_collection_modifyitems(self, items: list[Any]) -> None:
        self.counts["collected"] = len(items)

    # ID: f9c59842-4b06-44a8-8915-a0174e1ada9b
    def pytest_deselected(self, items: list[Any]) -> None:
        self.counts["deselected"] += len(items)
        if self.exclude_integration:
            for item in items:
                if item.get_closest_marker(_INTEGRATION) is not None:
                    self.excluded.append(item.nodeid)

    # ID: 9c78989a-6a80-45a6-82fb-be5f6220f6f1
    def pytest_runtest_logreport(self, report: Any) -> None:
        if report.when == "call":
            self.counts["executed"] += 1
            if report.passed:
                self.counts["passed"] += 1
            elif report.failed:
                self.counts["failed"] += 1
            elif report.skipped:
                self.counts["skipped"] += 1
        elif report.when == "setup":
            if report.skipped:
                self.counts["skipped"] += 1
            elif report.failed:
                self.counts["executed"] += 1
                self.counts["failed"] += 1
        elif report.when == "teardown" and report.failed:
            self.counts["failed"] += 1


def _candidate_error(snapshot: Path) -> str | None:
    """Every imported module of a package the snapshot ships must come from it."""
    src = snapshot / "src"
    if not src.is_dir():
        return None
    # Never follow a link here: its target may be unreadable on purpose, and
    # a stat that raises would leave the job without a report.
    shipped: set[str] = set()
    with os.scandir(src) as entries:
        for entry in entries:
            if entry.is_symlink():
                shipped.add(entry.name.removesuffix(".py"))
            elif entry.is_dir(follow_symlinks=False):
                shipped.add(entry.name)
            elif entry.name.endswith(".py"):
                shipped.add(entry.name.removesuffix(".py"))
    for name, module in list(sys.modules.items()):
        if name.split(".", 1)[0] not in shipped:
            continue
        origin = getattr(module, "__file__", None)
        if origin is None:
            continue
        if not Path(origin).resolve().is_relative_to(src.resolve()):
            return f"candidate_not_loaded: {name} came from {origin}"
    return None


# ID: 68a00f92-cd3e-4d10-ab25-4d1952fae4d0
def main(argv: list[str]) -> int:
    spec = json.loads(argv[1])
    snapshot = Path(spec["snapshot"])
    report_fd = int(spec["report_fd"])
    sys.path[:0] = [str(snapshot / "src"), str(snapshot)]
    os.chdir(snapshot)

    import pytest  # after the path change; pytest itself is the release's

    counter = _Counter(bool(spec.get("exclude_integration")))
    args = [
        "-p",
        "no:dotenv",
        "-p",
        "no:cacheprovider",
        "--rootdir",
        str(snapshot),
        "-c",
        str(snapshot / "pyproject.toml"),
        "--tb=short",
        "-q",
        "--no-header",
    ]
    if importlib.util.find_spec("pytest_cov") is not None:
        args.append("--no-cov")  # the repo's addopts ask for coverage of src
    if not (snapshot / "pyproject.toml").is_file():
        args[args.index("-c") : args.index("-c") + 2] = ["-c", os.devnull]
    if spec.get("markers"):
        args += ["-m", spec["markers"]]
    args += list(spec["targets"])
    exit_code = int(pytest.main(args, plugins=[counter]))
    report: dict[str, Any] = {
        "exit_code": exit_code,
        "counts": counter.counts,
        "excluded": counter.excluded,
        "error": _candidate_error(snapshot),
    }
    payload = json.dumps(report).encode("utf-8")
    while payload:
        payload = payload[os.write(report_fd, payload) :]
    os.close(report_fd)
    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
