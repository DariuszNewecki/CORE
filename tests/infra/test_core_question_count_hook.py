"""The Stop hook that counts questions to the governor (#1307)."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
HOOK = REPO / "infra" / "claude-hooks" / "core-question-count.sh"


def _stop(tmp_path: Path, reply: str, *, active: bool = False) -> Path:
    transcript = tmp_path / "t.jsonl"
    lines = [
        {"type": "user", "message": {"content": "hi"}},
        {
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": reply}]},
        },
        {"type": "assistant", "message": {"content": [{"type": "tool_use"}]}},
    ]
    transcript.write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    event = {"transcript_path": str(transcript), "stop_hook_active": active}
    subprocess.run(
        ["sh", str(HOOK)],
        input=json.dumps(event),
        text=True,
        check=True,
        env={**os.environ, "HOME": str(tmp_path)},
    )
    return tmp_path / ".cache" / "governor-questions.log"


def test_a_reply_ending_with_a_question_adds_one_utc_line(tmp_path: Path) -> None:
    log = _stop(tmp_path, "Done.\nShall I move #1285 to 3.1?  \n")
    (line,) = log.read_text().splitlines()
    assert line.endswith("Z") and line[:4].isdigit() and "T" in line


def test_a_reply_without_a_question_adds_nothing(tmp_path: Path) -> None:
    assert not _stop(tmp_path, "Merged. Is it done? Yes, it is.").exists()


def test_a_forced_rewrite_is_not_counted_twice(tmp_path: Path) -> None:
    assert not _stop(tmp_path, "Approve it?", active=True).exists()


def test_the_hook_is_installed_as_a_stop_hook() -> None:
    settings = json.loads((REPO / "infra/claude-hooks/settings.json").read_text())
    commands = [h["command"] for s in settings["hooks"]["Stop"] for h in s["hooks"]]
    assert any("core-question-count.sh" in c for c in commands)
