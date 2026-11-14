"""ADR-177 D3, D5 (#1339 PR I): plug-in governance packs."""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.infrastructure.intent.pack_loader import (
    PackIdCollisionError,
    list_pack_ids_from_sources,
    load_pack_from_sources,
)
from tests.helpers.fake_plugin import install_fake_plugin


_PACK = """\
kind: governance_pack
id: "{pack_id}"
version: "1.0.0"
title: "Plug-in pack"
description: "A pack from a plug-in."
target_language: "python"
level: "starter"
compatibility_floor: "3.0.0"
rules: []
enforcement_mappings: {{}}
"""


def _plugin_with_pack(
    monkeypatch: pytest.MonkeyPatch, site: Path, dist: str, pack_id: str
) -> None:
    install_fake_plugin(
        monkeypatch,
        site,
        dist_name=dist,
        package=dist.replace("-", "_"),
        manifest='{"format_version": 1, "core_engine_api": "1", "packs": "packs"}',
        files={"packs/pack.yaml": _PACK.format(pack_id=pack_id)},
    )


def _repo(tmp_path: Path, *pack_ids: str) -> Path:
    """A repository with its own packs/ registry (ADR-149: repository first)."""
    repo = tmp_path / "repo"
    (repo / "packs").mkdir(parents=True)
    for i, pack_id in enumerate(pack_ids):
        (repo / "packs" / f"p{i}.yaml").write_text(_PACK.format(pack_id=pack_id))
    return repo


def test_a_plugin_pack_is_found_beside_cores(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repo = _repo(tmp_path, "core/own")
    _plugin_with_pack(monkeypatch, tmp_path / "site", "ip-one", "acme/plugin-pack")
    assert {"core/own", "acme/plugin-pack"} <= set(list_pack_ids_from_sources(repo))
    pack = load_pack_from_sources("acme/plugin-pack", repo)
    assert pack is not None
    assert pack.pack_id == "acme/plugin-pack"
    assert load_pack_from_sources("core/own", repo) is not None
    assert load_pack_from_sources("nobody/none", repo) is None


def test_a_plugin_pack_with_a_core_id_refuses(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repo = _repo(tmp_path, "core/shared")
    _plugin_with_pack(monkeypatch, tmp_path / "site", "ip-clash", "core/shared")
    with pytest.raises(PackIdCollisionError) as exc:
        load_pack_from_sources("core/shared", repo)
    message = str(exc.value)
    assert "pack registry" in message
    assert "plug-in ip-clash 0.1.0" in message
    assert "ADR-177 D5" in message
    with pytest.raises(PackIdCollisionError):
        list_pack_ids_from_sources(repo)
