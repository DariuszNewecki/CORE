"""#909 -- installed-wheel proof: the prompt corpus works from a clean install.

Archive inspection (tests/infra/test_prompts_ship_in_wheel.py) proves the
wheel *carries* the corpus. This proves the installed package *uses* it:
the wheel is installed into a fresh venv, and a probe runs from a directory
that is not a CORE checkout and has no ``var/prompts/`` at all. It asserts:

- both ``PromptModel`` implementations load representative artifacts;
- a loose specialist ``.prompt`` file resolves through ``PathResolver.prompt``;
- ``runtime_external_run`` obtains its required prompt sources (planner ids
  present, package marker absent) from the bundled root;
- a repository prompt still wins when one is explicitly available;
- a missing prompt raises the existing clear ``FileNotFoundError`` rather
  than silently selecting unrelated content.

Same shape as tests/cli/test_offline_audit_regression_544.py: skipped when
no wheel is in ``dist/``; CI's hermetic job builds one before running.
"""

from __future__ import annotations

import json
import subprocess
import venv
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
DIST_DIR = REPO_ROOT / "dist"

PROBE = r"""
import json, sys
from pathlib import Path

out = {}
cwd = Path.cwd()
assert not (cwd / "var" / "prompts").exists(), "probe cwd must have no var/prompts"
assert not (cwd / ".git").exists(), "probe cwd must not be a checkout"

from shared.ai.prompt_model import PromptModel as AiPromptModel
from shared.models.prompt_model import PromptModel as ModelsPromptModel
from shared.path_resolver import PathResolver
from cli.runtime_external_run import (
    PLANNER_PROMPT_IDS, runner_prompt_root, runner_prompt_sources,
)

# 1. both implementations, default root (settings -> cwd/var/prompts, absent)
ai_default = AiPromptModel.load("docstring_writer")
out["ai_default"] = ai_default.manifest.id
out["ai_default_path"] = str(ai_default._artifact._artifact_path)
out["ai_explicit_empty_root"] = AiPromptModel.load(
    "planner_agent", prompts_root=cwd / "empty"
).manifest.id
out["models_default"] = ModelsPromptModel.load("docstring_writer").manifest.id

# 2. loose specialist .prompt file via the path API
loose = PathResolver(cwd).prompt("capability_definer.prompt")
out["loose_is_file"] = loose.is_file()
out["loose_in_site_packages"] = "site-packages" in str(loose)

# 3. external runner corpus from the bundled root, lifetime-bounded
with runner_prompt_root(cwd) as root:
    sources = runner_prompt_sources(cwd, prompts_root=root)
    out["runner_planner_ids_present"] = all(p in sources for p in PLANNER_PROMPT_IDS)
    out["runner_count"] = len(sources)
    out["runner_has_marker"] = "__init__.py" in sources
    out["runner_root_in_site_packages"] = "site-packages" in str(root)

# 4. repository wins when explicitly available
repo_prompts = cwd / "repo" / "var" / "prompts"
d = repo_prompts / "docstring_writer"
d.mkdir(parents=True)
bundled = PathResolver(cwd).prompt("docstring_writer")
for part in ("model.yaml", "user.txt"):
    (d / part).write_text((bundled / part).read_text(encoding="utf-8"), encoding="utf-8")
(d / "system.txt").write_text("REPO COPY WINS", encoding="utf-8")
out["repo_wins"] = AiPromptModel.load(
    "docstring_writer", prompts_root=repo_prompts
)._artifact.system_text
out["repo_wins_path_api"] = PathResolver(cwd / "repo").prompt("docstring_writer") == d

# 5. missing prompt -> existing clear failure, never unrelated content
try:
    AiPromptModel.load("no_such_prompt_xyz")
    out["missing"] = "NO ERROR"
except FileNotFoundError as exc:
    out["missing"] = str(exc)
try:
    PathResolver(cwd).prompt("no_such_prompt_xyz")
    out["missing_path_api"] = "NO ERROR"
except FileNotFoundError as exc:
    out["missing_path_api"] = str(exc)

print("PROBE_JSON=" + json.dumps(out))
"""


def _find_latest_wheel() -> Path | None:
    if not DIST_DIR.exists():
        return None
    wheels = sorted(DIST_DIR.glob("core_runtime-*.whl"))
    return wheels[-1] if wheels else None


@pytest.mark.e2e
@pytest.mark.slow
# ID: 807fb37e-8210-4ce9-aaac-2c186f4a85f3
def test_installed_wheel_serves_bundled_prompts_without_a_checkout(
    tmp_path: Path,
) -> None:
    wheel = _find_latest_wheel()
    if wheel is None:
        pytest.skip("No core_runtime-*.whl in dist/. Run `poetry build` first.")

    venv_dir = tmp_path / "venv"
    venv.create(venv_dir, with_pip=True)
    bin_dir = venv_dir / "bin"
    install = subprocess.run(
        [str(bin_dir / "pip"), "install", "--quiet", str(wheel)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert install.returncode == 0, f"pip install failed: {install.stderr[-1500:]}"

    workspace = tmp_path / "not-a-checkout"
    workspace.mkdir()
    (workspace / "probe.py").write_text(PROBE, encoding="utf-8")
    result = subprocess.run(
        [str(bin_dir / "python"), "probe.py"],
        cwd=str(workspace),
        env={"PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert result.returncode == 0, (
        f"probe failed (exit {result.returncode})\n"
        f"stdout:\n{result.stdout[-3000:]}\n\nstderr:\n{result.stderr[-3000:]}"
    )
    line = next(ln for ln in result.stdout.splitlines() if ln.startswith("PROBE_JSON="))
    out = json.loads(line[len("PROBE_JSON=") :])
    print(line)  # evidence in the -s / failure output

    assert out["ai_default"] == "prompt.docstring_writer"
    assert "site-packages" in out["ai_default_path"], out["ai_default_path"]
    assert out["ai_explicit_empty_root"]
    assert out["models_default"] == "prompt.docstring_writer"
    assert out["loose_is_file"] and out["loose_in_site_packages"]
    assert out["runner_planner_ids_present"]
    assert out["runner_count"] >= 40
    assert out["runner_has_marker"] is False
    assert out["runner_root_in_site_packages"]
    assert out["repo_wins"] == "REPO COPY WINS"
    assert out["repo_wins_path_api"] is True
    assert "missing model.yaml at" in out["missing"]
    assert "not found at" in out["missing_path_api"]
