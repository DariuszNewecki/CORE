# tests/cli/test_admin_cli__help_for_adopters.py
"""#1158 (proof run 3): after `pip install core-runtime`, `core-admin --help`
listed 29 groups, two with internal tracker refs ("#821 Unit 2"), several
citing CORE's own ADRs, and nothing told the offline-capable groups from the
ones that need PostgreSQL, Qdrant or the API."""

from __future__ import annotations

import re

import typer

from cli import admin_cli


_INTERNAL_REF = re.compile(r"#\d+|\bADR-\d+")
OFFLINE_GROUPS = {"project", "code", "law", "decisions", "mcp"}


def _groups() -> dict[str, typer.models.TyperInfo]:
    return {g.name: g for g in admin_cli.app.registered_groups}


# ID: 72550481-8ef2-4301-bc2e-f6a95e55b3c9
def test_top_level_group_help_cites_no_internal_refs() -> None:
    found = {
        name: g.typer_instance.info.help
        for name, g in _groups().items()
        if _INTERNAL_REF.search(str(g.typer_instance.info.help or ""))
    }
    assert found == {}


# ID: b8b6d7a8-1a07-44eb-b301-3c50365377da
def test_offline_groups_have_their_own_help_panel() -> None:
    panels = {name: g.rich_help_panel for name, g in _groups().items()}
    offline = {
        name for name, panel in panels.items() if panel == admin_cli.OFFLINE_PANEL
    }
    assert offline == OFFLINE_GROUPS
    assert all(panels[name] for name in panels), "every group is in a panel"
