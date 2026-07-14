# tests/shared/infrastructure/intent/test_pack_loader.py

"""Unit tests for PackLoader and LoadedPack."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from shared.infrastructure.intent.pack_loader import LoadedPack, PackLoader


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_pack(tmp_path: Path, filename: str, data: dict) -> Path:
    """Write a YAML pack file and return its path."""
    p = tmp_path / filename
    p.write_text(yaml.dump(data, default_flow_style=False), "utf-8")
    return p


def _minimal_pack(pack_id: str = "test/my-pack") -> dict:
    return {
        "kind": "governance_pack",
        "id": pack_id,
        "version": "1.0.0",
        "title": "Test Pack",
        "description": "A test pack.",
        "level": "starter",
        "rules": [
            {
                "id": "test.no_bare_except",
                "statement": "No bare excepts.",
                "enforcement": "blocking",
                "authority": "policy",
                "phase": "runtime",
            }
        ],
        "enforcement_mappings": {
            "test.no_bare_except": {
                "engine": "regex_gate",
                "params": {"forbidden_patterns": ["except:\\s*pass"]},
                "scope": {"applies_to": ["**/*.py"]},
            }
        },
    }


# ---------------------------------------------------------------------------
# LoadedPack
# ---------------------------------------------------------------------------


def test_loaded_pack_rule_ids():
    pack = LoadedPack(
        pack_id="core/starter-python",
        version="1.0.0",
        title="Starter",
        description="desc",
        level="starter",
        target_language="python",
        compatibility_floor="2.8.0",
        supersedes=None,
        rules=[
            {"id": "starter.no_bare_except"},
            {"id": "starter.no_print"},
        ],
        enforcement_mappings={},
    )
    assert pack.rule_ids == {"starter.no_bare_except", "starter.no_print"}


def test_loaded_pack_empty_rules():
    pack = LoadedPack(
        pack_id="core/empty",
        version="0.1.0",
        title="Empty",
        description="desc",
        level="starter",
        target_language=None,
        compatibility_floor=None,
        supersedes=None,
    )
    assert pack.rule_ids == set()


# ---------------------------------------------------------------------------
# PackLoader.list_pack_ids
# ---------------------------------------------------------------------------


def test_list_pack_ids_empty_dir(tmp_path: Path):
    assert PackLoader(tmp_path).list_pack_ids() == []


def test_list_pack_ids_missing_dir(tmp_path: Path):
    assert PackLoader(tmp_path / "nonexistent").list_pack_ids() == []


def test_list_pack_ids_finds_ids(tmp_path: Path):
    _write_pack(tmp_path, "pack_a.yaml", _minimal_pack("vendor/pack-a"))
    _write_pack(tmp_path, "pack_b.yaml", _minimal_pack("vendor/pack-b"))
    ids = PackLoader(tmp_path).list_pack_ids()
    assert set(ids) == {"vendor/pack-a", "vendor/pack-b"}


def test_list_pack_ids_skips_bad_files(tmp_path: Path):
    _write_pack(tmp_path, "good.yaml", _minimal_pack("test/good"))
    (tmp_path / "bad.yaml").write_text("{{not valid yaml{{", "utf-8")
    ids = PackLoader(tmp_path).list_pack_ids()
    assert ids == ["test/good"]


# ---------------------------------------------------------------------------
# PackLoader.load_pack
# ---------------------------------------------------------------------------


def test_load_pack_returns_none_when_not_found(tmp_path: Path):
    assert PackLoader(tmp_path).load_pack("core/missing") is None


def test_load_pack_returns_loaded_pack(tmp_path: Path):
    _write_pack(tmp_path, "starter.yaml", _minimal_pack("core/starter-python"))
    pack = PackLoader(tmp_path).load_pack("core/starter-python")
    assert pack is not None
    assert pack.pack_id == "core/starter-python"
    assert pack.version == "1.0.0"
    assert len(pack.rules) == 1
    assert pack.rules[0]["id"] == "test.no_bare_except"
    assert "test.no_bare_except" in pack.enforcement_mappings


def test_load_pack_wrong_kind_raises(tmp_path: Path):
    data = _minimal_pack("core/wrong-kind")
    data["kind"] = "rule_document"
    _write_pack(tmp_path, "wrong.yaml", data)
    with pytest.raises(ValueError, match="kind="):
        PackLoader(tmp_path).load_pack("core/wrong-kind")


def test_load_pack_missing_id_raises(tmp_path: Path):
    data = _minimal_pack("core/no-id")
    del data["id"]
    _write_pack(tmp_path, "no_id.yaml", data)
    # File has no 'id' so load_pack will never match it — returns None
    result = PackLoader(tmp_path).load_pack("core/no-id")
    assert result is None


# ---------------------------------------------------------------------------
# PackLoader.load_all
# ---------------------------------------------------------------------------


def test_load_all_empty(tmp_path: Path):
    assert PackLoader(tmp_path).load_all() == []


def test_load_all_returns_all_packs(tmp_path: Path):
    _write_pack(tmp_path, "a.yaml", _minimal_pack("test/a"))
    _write_pack(tmp_path, "b.yaml", _minimal_pack("test/b"))
    packs = PackLoader(tmp_path).load_all()
    assert len(packs) == 2
    assert {p.pack_id for p in packs} == {"test/a", "test/b"}


def test_load_all_skips_non_pack_kind(tmp_path: Path):
    data = _minimal_pack("test/a")
    data["kind"] = "something_else"
    _write_pack(tmp_path, "a.yaml", data)
    packs = PackLoader(tmp_path).load_all()
    assert packs == []


def test_load_all_optional_fields_default(tmp_path: Path):
    data = _minimal_pack("test/minimal")
    # Remove optional fields
    data.pop("level", None)
    data["level"] = "starter"
    _write_pack(tmp_path, "min.yaml", data)
    packs = PackLoader(tmp_path).load_all()
    assert len(packs) == 1
    assert packs[0].target_language is None
    assert packs[0].compatibility_floor is None
    assert packs[0].supersedes is None


# ---------------------------------------------------------------------------
# Integration: real CORE packs dir (smoke-loads without error)
# ---------------------------------------------------------------------------


def test_real_packs_dir_loads_without_error():
    """Smoke test: the three built-in packs load without error."""
    from shared.config import settings

    packs_dir = settings.MIND.parent / "packs"
    if not packs_dir.exists():
        pytest.skip("CORE packs/ registry not found in test environment")

    loader = PackLoader(packs_dir)
    packs = loader.load_all()
    assert len(packs) >= 3, f"Expected at least 3 packs, got {len(packs)}"

    ids = {p.pack_id for p in packs}
    assert "core/starter-python" in ids
    assert "core/python-hygiene" in ids
    assert "core/architectural-boundaries" in ids

    for pack in packs:
        assert pack.pack_id
        assert pack.rules, f"Pack {pack.pack_id!r} has no rules"
        assert pack.enforcement_mappings, f"Pack {pack.pack_id!r} has no mappings"
        for rule in pack.rules:
            assert rule.get("id") in pack.enforcement_mappings, (
                f"Pack {pack.pack_id!r}: rule {rule.get('id')!r} has no enforcement mapping"
            )
