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


from shared.infrastructure.intent.target_intent_assembly import DisplacedFloorFile


# ID: db5fc969-b840-4480-abbb-735967131a59
def test_DisplacedFloorFile() -> None:
    displaced = DisplacedFloorFile(
        path="src/app/main.py",
        original_sha256="a" * 64,
        installed_floor_sha256="b" * 64,
    )

    assert displaced.path == "src/app/main.py"
    assert displaced.original_sha256 == "a" * 64
    assert displaced.installed_floor_sha256 == "b" * 64


from shared.infrastructure.intent.target_intent_assembly import SubjectCopyError


# ID: 8b9cd9f7-9539-4df9-9020-e3d8bf1310b3
def test_SubjectCopyError() -> None:
    error = SubjectCopyError("cannot copy subject faithfully")
    assert isinstance(error, SubjectCopyError)
    assert isinstance(error, Exception)
    assert "cannot copy subject faithfully" in str(error)


from unittest.mock import MagicMock, patch

from shared.infrastructure.intent.target_intent_assembly import assemble_target_intent


# ID: 13f8d4e4-d18f-4261-ae80-89c6d47d3e26
def test_assemble_target_intent(tmp_path: Path) -> None:
    intent_root = tmp_path / "intent"
    floor_root = tmp_path / "floor"
    floor_root.mkdir()
    (floor_root / "floor_file.txt").write_text("floor")

    overlay_dir = tmp_path / "overlay"
    overlay_dir.mkdir()
    (overlay_dir / "overlay_file.txt").write_text("overlay")

    mock_manifest = MagicMock(return_value={})
    mock_floor_hash = MagicMock(return_value="floorhash")
    mock_overlay_hash = MagicMock(return_value="overlayhash")

    with (
        patch(
            "shared.infrastructure.intent.target_intent_assembly.floor_manifest",
            mock_manifest,
        ),
        patch(
            "shared.infrastructure.intent.target_intent_assembly.floor_hash",
            mock_floor_hash,
        ),
        patch(
            "shared.infrastructure.intent.target_intent_assembly.overlay_hash",
            mock_overlay_hash,
        ),
        patch(
            "shared.infrastructure.intent.target_intent_assembly.importlib.resources.files",
            MagicMock(return_value=floor_root),
        ),
    ):
        result = assemble_target_intent(intent_root, overlay_dir)

    assert result.intent_root == intent_root
    assert result.floor_hash == "floorhash"
    assert result.overlay_hash == "overlayhash"
    assert "overlay_file.txt" in result.overlay_files
    assert (intent_root / "floor_file.txt").exists()
    assert (intent_root / "overlay_file.txt").exists()


from shared.infrastructure.intent.target_intent_assembly import overlay_hash


# ID: c2682600-cf17-4644-9f1b-bbc0e3130232
def test_overlay_hash(tmp_path):
    overlay = tmp_path / "overlay"
    overlay.mkdir()
    (overlay / "a.txt").write_text("hello", encoding="utf-8")
    (overlay / "b.txt").write_text("world", encoding="utf-8")

    result = overlay_hash(overlay)

    assert isinstance(result, str)
    assert len(result) == 64
    # Deterministic
    assert overlay_hash(overlay) == result
    # None hashes to the empty list digest
    import hashlib

    assert overlay_hash(None) == hashlib.sha256().hexdigest()



from shared.infrastructure.intent.target_intent_assembly import AssembledIntent


# ID: db22f221-e0cf-40e1-9502-28f977d2b9c1
def test_AssembledIntent() -> None:
    intent_root = Path("/tmp/intent")
    floor_hash = "abc123"
    overlay_hash = "def456"
    overlay_files = ("a.py", "b.py")

    assembled = AssembledIntent(
        intent_root=intent_root,
        floor_hash=floor_hash,
        overlay_hash=overlay_hash,
        overlay_files=overlay_files,
    )

    assert assembled.intent_root == intent_root
    assert assembled.floor_hash == floor_hash
    assert assembled.overlay_hash == overlay_hash
    assert assembled.overlay_files == overlay_files
