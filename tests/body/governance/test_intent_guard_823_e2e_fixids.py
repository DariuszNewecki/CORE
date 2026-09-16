# tests/body/governance/test_intent_guard_823_e2e_fixids.py
"""End-to-end reproduction of #823 through the real `fix.ids` write=True path.

Exercises the actual production call chain — `assign_missing_ids(context,
write=True)` -> `ActionExecutor.execute(action_id="file.tag_metadata", ...)`
-> `FileHandler.write_runtime_bytes` -> `IntentGuard.check_transaction` —
against disposable Postgres + Qdrant (the same `infra/demo/compose.yaml`
ADR-155 Phase 1 validated), never the shared LAN test database. Marked
`integration`; skipped entirely when `docker compose` (v2) isn't available.

Before the #823 fix this test fails: the real write is blocked by
`governance.commit_authorship_integrity` / `governance.proposal_finalization_integrity`
/ `governance.consequence_evidence_degraded` — all `authority: constitution`,
all `engine: passive_gate` declared directly (not via an alias) — because the
literal `passive_gate` engine name was absent from `_AUDIT_ENGINES`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import pytest


pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[3]
COMPOSE_FILE = REPO_ROOT / "infra" / "demo" / "compose.yaml"

# Deliberately avoids the literal substring "# ID:" anywhere in this content
# (including in prose) — the test asserts on that exact substring appearing
# in the *written-back* file, and a docstring merely describing the anchor
# would make that assertion pass whether or not the real write happened.
_PROBE_MODULE_CONTENT = (
    '"""Throwaway probe for issue 823 regression — not part of any real commit."""\n\n'
    "from __future__ import annotations\n\n\n"
    "def probe_fn_823_missing_id() -> str:\n"
    '    """Public function with no stable-identity anchor above it."""\n'
    '    return "probe"\n'
)

# linkage.no_orphan_ids companion probe: an anchor split from its def by a
# blank line (the 9e9067eb shape) shadowing one public symbol, plus an
# unrelated public symbol with no anchor. fix.ids write=True must leave the
# orphan's bytes exactly as written, must NOT hand the shadowed symbol a fresh
# anchor, and must still tag the unrelated one.
_ORPHAN_ANCHOR_LINE = "# ID: a1fb17c6-a4a7-4503-9103-491b28305c2d"
_ORPHAN_PROBE_CONTENT = (
    '"""Throwaway orphan-anchor probe -- not part of any real commit."""\n\n'
    "from __future__ import annotations\n\n\n"
    f"{_ORPHAN_ANCHOR_LINE}\n"
    "\n"
    "def probe_fn_orphan_shadowed() -> str:\n"
    '    return "shadowed"\n'
    "\n\n"
    "def probe_fn_orphan_unrelated() -> str:\n"
    '    return "unrelated"\n'
)

_CHILD_SCRIPT = '''\
import asyncio
import json
import sys

sys.path.insert(0, "src")


async def main() -> None:
    from body.infrastructure.bootstrap import create_core_context
    from body.services.service_registry import service_registry
    from body.self_healing.id_tagging_service import assign_missing_ids

    probe_path = "src/body/analyzers/_test_823_missing_id_probe.py"
    orphan_path = "src/body/analyzers/_test_orphan_anchor_probe.py"
    context = create_core_context(service_registry)

    report = await assign_missing_ids(context, write=True)
    content = (context.git_service.repo_path / probe_path).read_text()
    orphan_content = (context.git_service.repo_path / orphan_path).read_text()

    print(json.dumps({
        "total": report.ids_assigned,
        "content": content,
        "orphan_content": orphan_content,
        "orphans": [
            [o.file_path, o.line_number, o.symbol] for o in report.orphan_anchors
        ],
    }))


asyncio.run(main())
'''


def _run(args: list[str], cwd: Path | None = None, env: dict | None = None, check: bool = True):
    return subprocess.run(
        args, cwd=cwd, env=env, capture_output=True, text=True, check=check
    )


@pytest.fixture(scope="module")
def docker_compose_available() -> bool:
    """True only if `docker compose` v2 works here AND the compose file exists."""
    if not COMPOSE_FILE.exists():
        return False
    if not shutil.which("docker"):
        return False
    try:
        result = subprocess.run(
            ["docker", "compose", "version"], capture_output=True, timeout=10
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _docker_port(container: str, container_port: int) -> str:
    result = _run(["docker", "port", container, str(container_port)])
    # e.g. "127.0.0.1:32783"
    return result.stdout.strip().rsplit(":", 1)[-1]


@pytest.fixture
def disposable_infra(docker_compose_available: bool):
    if not docker_compose_available:
        pytest.skip("docker compose v2 unavailable or infra/demo/compose.yaml missing")

    project = f"core-823-test-{uuid.uuid4().hex[:10]}"
    env = {"RUN_ID": project}
    path = os.environ.get("PATH")
    if path:
        env["PATH"] = path

    _run(
        ["docker", "compose", "-p", project, "-f", str(COMPOSE_FILE), "up", "-d", "--wait"],
        env=env,
    )
    try:
        pg_port = _docker_port(f"{project}-postgres-1", 5432)
        qdrant_port = _docker_port(f"{project}-qdrant-1", 6333)
        yield {"pg_port": pg_port, "qdrant_port": qdrant_port}
    finally:
        _run(
            ["docker", "compose", "-p", project, "-f", str(COMPOSE_FILE), "down",
             "--volumes", "--remove-orphans"],
            env=env,
            check=False,
        )


def _prepare_clone(clone_dir: Path, disposable_infra: dict) -> Path:
    _run(["git", "clone", "--no-hardlinks", "--quiet", str(REPO_ROOT), str(clone_dir)])
    _run(["git", "remote", "remove", "origin"], cwd=clone_dir)

    probe_rel = "src/body/analyzers/_test_823_missing_id_probe.py"
    orphan_rel = "src/body/analyzers/_test_orphan_anchor_probe.py"
    (clone_dir / probe_rel).write_text(_PROBE_MODULE_CONTENT)
    (clone_dir / orphan_rel).write_text(_ORPHAN_PROBE_CONTENT)
    _run(["git", "add", probe_rel, orphan_rel], cwd=clone_dir)
    _run(
        [
            "git", "-c", "user.email=test-823@test.local", "-c", "user.name=Test 823",
            "-c", "commit.gpgsign=false", "commit", "-q", "-m", "probe: #823 regression",
        ],
        cwd=clone_dir,
    )

    (clone_dir / ".env").write_text(
        "CORE_ENV=development\n"
        "LLM_ENABLED=False\n"
        f"DATABASE_URL=postgresql+asyncpg://core_demo:core_demo@127.0.0.1:"
        f"{disposable_infra['pg_port']}/core_demo\n"
        f"QDRANT_URL=http://127.0.0.1:{disposable_infra['qdrant_port']}\n"
        "CORE_STRICT_MODE=False\n"
    )
    (clone_dir / "_run_fixids_probe.py").write_text(_CHILD_SCRIPT)
    return clone_dir


def test_fixids_write_succeeds_end_to_end(
    disposable_infra: dict, tmp_path: Path
) -> None:
    """The real fix.ids write path must succeed against disposable infra (#823)."""
    clone_dir = _prepare_clone(tmp_path / "clone", disposable_infra)

    result = _run(
        [sys.executable, "_run_fixids_probe.py"],
        cwd=clone_dir,
        env={"PATH": os.environ.get("PATH", "")},
        check=False,
    )

    assert result.returncode == 0, (
        f"probe script failed (exit {result.returncode}):\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    last_line = result.stdout.strip().splitlines()[-1]
    import json
    import re

    payload = json.loads(last_line)
    # `total` counts symbols *planned* for fixing during discovery — it is
    # nonzero whether or not the subsequent write actually applied, so it
    # cannot distinguish success from #823's silent block. The only proof
    # that matters is the anchor line genuinely present in the file the
    # real fix.ids write path wrote back to disk.
    # 1 for the #823 probe + 1 for the orphan probe's unrelated symbol. The
    # shadowed symbol must not be counted: it is skipped, not re-tagged.
    assert payload["total"] == 2, f"expected exactly 2 symbols discovered, got {payload}"
    anchor_pattern = re.compile(
        r"^# ID: [0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{12}\ndef probe_fn_823_missing_id",
        re.MULTILINE,
    )
    assert anchor_pattern.search(payload["content"]), (
        f"fix.ids did not write a genuine ID anchor immediately above the "
        f"function — write was blocked (#823 regressed): {payload['content']!r}"
    )

    # linkage.no_orphan_ids: the orphan's bytes survived the real write path
    # untouched (anchor, blank line, def -- exactly as committed), the symbol
    # it shadows was NOT given a fresh anchor, and the unrelated symbol was.
    orphan_written = payload["orphan_content"]
    assert (
        f"{_ORPHAN_ANCHOR_LINE}\n\ndef probe_fn_orphan_shadowed" in orphan_written
    ), f"fix.ids altered the orphan anchor bytes:\n{orphan_written}"
    assert orphan_written.count(_ORPHAN_ANCHOR_LINE) == 1
    assert not re.search(
        r"^# ID: [0-9a-fA-F-]{36}\ndef probe_fn_orphan_shadowed",
        orphan_written,
        re.MULTILINE,
    ), f"fix.ids regenerated an ID for the shadowed symbol:\n{orphan_written}"
    assert re.search(
        r"^# ID: [0-9a-fA-F-]{36}\ndef probe_fn_orphan_unrelated",
        orphan_written,
        re.MULTILINE,
    ), f"fix.ids did not tag the unrelated symbol:\n{orphan_written}"
    assert payload["orphans"] == [
        ["src/body/analyzers/_test_orphan_anchor_probe.py", 6, "probe_fn_orphan_shadowed"]
    ], payload["orphans"]


def test_unauthorized_intent_write_still_blocked(
    disposable_infra: dict, tmp_path: Path
) -> None:
    """The #823 fix must not weaken the real .intent/ hard invariant.

    Same clone/infra shape as the success case, but the probe script instead
    attempts to write into .intent/ via FileHandler — this must still be
    refused unconditionally, proving the passive_gate exemption is scoped to
    exactly the three named engines/rules and not a blanket write-time
    bypass.
    """
    clone_dir = tmp_path / "clone"
    _run(["git", "clone", "--no-hardlinks", "--quiet", str(REPO_ROOT), str(clone_dir)])
    _run(["git", "remote", "remove", "origin"], cwd=clone_dir)

    (clone_dir / ".env").write_text(
        "CORE_ENV=development\n"
        "LLM_ENABLED=False\n"
        f"DATABASE_URL=postgresql+asyncpg://core_demo:core_demo@127.0.0.1:"
        f"{disposable_infra['pg_port']}/core_demo\n"
        f"QDRANT_URL=http://127.0.0.1:{disposable_infra['qdrant_port']}\n"
        "CORE_STRICT_MODE=False\n"
    )
    script = (
        'import sys\n'
        'sys.path.insert(0, "src")\n'
        'from body.infrastructure.storage.file_handler import FileHandler\n'
        'from mind.governance.violation_report import ConstitutionalViolationError\n'
        'handler = FileHandler(".")\n'
        'try:\n'
        '    handler.write_runtime_text(".intent/should_not_write.json", "{}")\n'
        '    print("WROTE")\n'
        'except ConstitutionalViolationError:\n'
        '    print("BLOCKED")\n'
    )
    (clone_dir / "_run_intent_probe.py").write_text(script)

    result = _run(
        [sys.executable, "_run_intent_probe.py"],
        cwd=clone_dir,
        env={"PATH": os.environ.get("PATH", "")},
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "BLOCKED" in result.stdout, (
        f".intent/ write was not blocked — the #823 fix over-widened the "
        f"write-time skip. stdout: {result.stdout!r}"
    )
    assert not (clone_dir / ".intent" / "should_not_write.json").exists()
