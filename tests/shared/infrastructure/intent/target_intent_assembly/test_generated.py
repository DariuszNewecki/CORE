from __future__ import annotations

from shared.infrastructure.intent.target_intent_assembly import InstalledPrompt


# ID: b0007de6-ca37-4755-bcf1-45a113d80647
def test_InstalledPrompt() -> None:
    # Happy path: construct the dataclass and verify fields round-trip.
    files = {"planner_prompt.md": "abc123"}
    displaced = {"planner_prompt.md": "def456"}

    prompt = InstalledPrompt(
        prompt_id="prompt-001",
        files=files,
        displaced_original_sha256=displaced,
    )

    assert prompt.prompt_id == "prompt-001"
    assert prompt.files == {"planner_prompt.md": "abc123"}
    assert prompt.displaced_original_sha256 == {"planner_prompt.md": "def456"}
    assert prompt.files["planner_prompt.md"] == "abc123"
    assert prompt.displaced_original_sha256["planner_prompt.md"] == "def456"


import json
from pathlib import Path

from shared.infrastructure.intent.target_intent_assembly import write_evidence_json


# ID: 6118dce3-2ff6-41da-802a-2614a71de51d
def test_write_evidence_json(tmp_path: Path) -> None:
    evidence_root = tmp_path / "evidence"
    evidence_root.mkdir()

    payload = {"b": 2, "a": 1, "nested": {"z": "last", "y": Path("/tmp/x")}}

    result = write_evidence_json(evidence_root, "report.json", payload)

    assert result == evidence_root / "report.json"
    assert result.exists()
    content = result.read_text(encoding="utf-8")
    assert content.endswith("\n")
    written = json.loads(content)
    assert written == {"a": 1, "b": 2, "nested": {"y": "/tmp/x", "z": "last"}}
    # deterministic sorted-key encoding
    assert content.startswith(
        json.dumps(payload, indent=2, sort_keys=True, default=str)
    )
