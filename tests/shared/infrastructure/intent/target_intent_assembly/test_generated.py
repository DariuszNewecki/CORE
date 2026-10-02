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


from shared.infrastructure.intent.target_intent_assembly import (
    materialize_execution_copy,
)


# ID: d787f8a0-3fcb-4a94-a6b6-b2869bf14410
def test_materialize_execution_copy(tmp_path: Path) -> None:
    subject_root = tmp_path / "subject"
    subject_root.mkdir()
    (subject_root / "hello.txt").write_text("hi", encoding="utf-8")

    run_root = tmp_path / "run"

    result = materialize_execution_copy(subject_root, run_root)

    assert result.target_root == run_root / "target"
    assert result.intent_root == run_root / "target" / ".intent"
    assert result.evidence_root == run_root / "evidence"
    assert (run_root / "target" / "hello.txt").read_text(encoding="utf-8") == "hi"

    manifest_path = run_root / "evidence" / "collision_manifest.json"
    assert manifest_path.is_file()
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["subject_root"]
    assert "displaced" in data


from shared.infrastructure.intent.target_intent_assembly import subject_fingerprint


# ID: 756a3b19-fab2-429c-bc28-d9525176a4ca
def test_subject_fingerprint(tmp_path: Path) -> None:
    subject_root = tmp_path / "subject"
    subject_root.mkdir()

    (subject_root / "a.txt").write_bytes(b"hello")
    (subject_root / "b.txt").write_bytes(b"world")

    sub = subject_root / "nested"
    sub.mkdir()
    (sub / "c.txt").write_bytes(b"deep")

    # .git dir itself must be skipped at the root.
    git_dir = subject_root / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_bytes(b"should-be-ignored")

    result = subject_fingerprint(subject_root)

    # Deterministic: same tree yields same digest.
    assert result == subject_fingerprint(subject_root)

    # A 64-char lowercase hex sha256 digest.
    assert isinstance(result, str)
    assert len(result) == 64
    int(result, 16)

    # The root .git contents must NOT influence the fingerprint: adding a new
    # file inside .git leaves the digest unchanged.
    (git_dir / "HEAD").write_bytes(b"ref: refs/heads/main")
    assert subject_fingerprint(subject_root) == result

    # A chmod (mode change) must change the fingerprint.
    (subject_root / "a.txt").chmod(0o755)
    assert subject_fingerprint(subject_root) != result




# ID: 727992d8-f41d-4ca2-bb5c-ed0e6da8940a
def test_ExecutionCopy():
    from shared.infrastructure.intent.target_intent_assembly import ExecutionCopy

    copy = ExecutionCopy(
        target_root=Path("/target"),
        intent_root=Path("/intent"),
        evidence_root=Path("/evidence"),
        floor_hash="floorhash",
        overlay_hash="overlayhash",
        overlay_files=("a.txt", "b.txt"),
        displaced=(),
        collision_manifest_path=Path("/manifest.json"),
    )

    assert copy.target_root == Path("/target")
    assert copy.intent_root == Path("/intent")
    assert copy.evidence_root == Path("/evidence")
    assert copy.floor_hash == "floorhash"
    assert copy.overlay_hash == "overlayhash"
    assert copy.overlay_files == ("a.txt", "b.txt")
    assert copy.displaced == ()
    assert copy.collision_manifest_path == Path("/manifest.json")
    assert copy.prompts == ()
    assert copy.prompt_collision_manifest_path is None
