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
