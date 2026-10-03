"""resolve_catalog_root: repository corpus first, bundled public corpus second.

ADR-116 D6 (amended 2026-10-03): a ``pip install core-runtime`` user, whose
repository has no ``grc-catalogs/``, gets the public catalogs bundled in the
wheel; a repository that carries its own corpus keeps reading it.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from body.services.grc import catalog_resolver
from shared.infrastructure.bundled_grc_catalogs import bundled_grc_catalogs_dir


def _bound_to(repo: Path):
    intent = SimpleNamespace(root=repo / ".intent")
    return patch(
        "shared.infrastructure.intent.intent_repository.get_intent_repository",
        return_value=intent,
    )


def test_bundle_is_present_with_inventory_and_public_tier() -> None:
    bundle = bundled_grc_catalogs_dir()
    assert bundle is not None
    assert (bundle / "inventory.yaml").is_file()
    assert (bundle / "public" / "nist_800_171" / "catalog.yaml").is_file()


def test_repository_without_corpus_reads_the_bundle(tmp_path: Path) -> None:
    with _bound_to(tmp_path):
        root = catalog_resolver.resolve_catalog_root()
        published = catalog_resolver.discover_published_catalogs()
    assert root == bundled_grc_catalogs_dir()
    assert "nist_800_171" in published


def test_repository_corpus_wins_over_the_bundle(tmp_path: Path) -> None:
    (tmp_path / "grc-catalogs").mkdir()
    with _bound_to(tmp_path):
        assert catalog_resolver.resolve_catalog_root() == tmp_path / "grc-catalogs"


def test_explicit_root_overrides_both(tmp_path: Path) -> None:
    with _bound_to(tmp_path):
        assert catalog_resolver.resolve_catalog_root(tmp_path) == tmp_path.resolve()
