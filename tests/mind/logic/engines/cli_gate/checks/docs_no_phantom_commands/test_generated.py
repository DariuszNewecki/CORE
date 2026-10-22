from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from mind.logic.engines.cli_gate.checks.docs_no_phantom_commands import (
    CORE_CLI_PAGE,
    DocsNoPhantomCommandsCheck,
)


# ID: c6797709-13de-4f5f-b215-920c7a0e728a
def test_DocsNoPhantomCommandsCheck_verify(tmp_path: Path) -> None:
    reference = tmp_path / CORE_CLI_PAGE
    reference.parent.mkdir(parents=True, exist_ok=True)
    reference.write_text("core foo\n", encoding="utf-8")

    path_resolver = MagicMock()
    path_resolver.repo_root = tmp_path

    core_admin_tree = MagicMock()

    check = DocsNoPhantomCommandsCheck(
        path_resolver=path_resolver,
        core_admin_tree=core_admin_tree,
    )

    check._docs = MagicMock(return_value=[])

    with (
        patch(
            "mind.logic.engines.cli_gate.checks.docs_no_phantom_commands.inventory_from_tree",
            return_value=MagicMock(),
        ) as mock_inv_tree,
        patch(
            "mind.logic.engines.cli_gate.checks.docs_no_phantom_commands.inventory_from_reference",
            return_value=MagicMock(),
        ) as mock_inv_ref,
        patch(
            "mind.logic.engines.cli_gate.checks.docs_no_phantom_commands.find_phantom_mentions",
            return_value=[],
        ) as mock_find,
    ):
        result = check.verify(commands=[], params={})

    assert result == []
    check._docs.assert_called_once_with({})
    mock_inv_tree.assert_called_once()
    mock_inv_ref.assert_called_once()
    mock_find.assert_called_once()


# ID: 859f0b9e-14b7-4903-83e9-2a5e8857efbd
def test_DocsNoPhantomCommandsCheck(tmp_path: Path) -> None:
    repo_root = tmp_path
    reference = repo_root / "docs" / "reference" / "core.md"
    reference.parent.mkdir(parents=True, exist_ok=True)
    reference.write_text("core reference text", encoding="utf-8")

    path_resolver = MagicMock()
    path_resolver.repo_root = repo_root

    core_admin_tree = MagicMock()
    core_admin_tree.return_value = MagicMock()

    check = DocsNoPhantomCommandsCheck(
        path_resolver=path_resolver,
        core_admin_tree=core_admin_tree,
    )

    params = {"include": [], "exclude": [], "extra_paths": [], "allow_mentions": []}

    with (
        patch(
            "mind.logic.engines.cli_gate.checks.docs_no_phantom_commands.inventory_from_tree",
            return_value=MagicMock(),
        ),
        patch(
            "mind.logic.engines.cli_gate.checks.docs_no_phantom_commands.inventory_from_reference",
            return_value=MagicMock(),
        ),
        patch(
            "mind.logic.engines.cli_gate.checks.docs_no_phantom_commands.find_phantom_mentions",
            return_value=[],
        ) as mock_find,
    ):
        findings = check.verify([], params)

    assert findings == []
    core_admin_tree.assert_called_once()
    mock_find.assert_called_once()


from mind.logic.engines.cli_gate.checks.docs_no_phantom_commands import (
    find_phantom_mentions,
)


# ID: fe8212ce-1762-4596-81e7-556157582734
def test_find_phantom_mentions():
    inventory = MagicMock()

    docs = {"README.md": "run will foo bar\n"}
    inventories = {"will": inventory}

    with (
        patch(
            "mind.logic.engines.cli_gate.checks.docs_no_phantom_commands.iter_code_mentions",
            return_value=[(1, "will", ("foo", "bar"))],
        ),
        patch(
            "mind.logic.engines.cli_gate.checks.docs_no_phantom_commands.resolve_mention",
            return_value=("phantom", ("foo", "bar")),
        ) as mock_resolve,
    ):
        problems = find_phantom_mentions(docs, inventories)

    mock_resolve.assert_called_once_with(("foo", "bar"), inventory)
    assert len(problems) == 1
    problem = problems[0]
    assert problem.file_path == "README.md"
    assert problem.line == 1
    assert problem.kind == "phantom"
    assert problem.mention == "will foo bar"


from mind.logic.engines.cli_gate.checks.docs_no_phantom_commands import resolve_mention


# ID: b82cbbfc-7599-4c5e-b36e-c69f406fd05e
def test_resolve_mention():
    inventory = MagicMock()
    inventory.commands = {("build",), ("deploy",)}
    inventory.groups = {("build",), ("deploy",)}
    inventory.hidden = {("secret",)}

    assert resolve_mention(("build",), inventory) is None
    assert resolve_mention(("deploy", "--flag"), inventory) is None
    assert resolve_mention(("secret",), inventory) == ("hidden", ("secret",))
    assert resolve_mention(("nope", "--x"), inventory) == ("phantom", ("nope",))


from mind.logic.engines.cli_gate.checks.docs_no_phantom_commands import (
    inventory_from_reference,
)


# ID: 67bd6628-a508-48cb-a91d-9bec462be8aa
def test_inventory_from_reference():
    text = (
        "# Core Reference\n"
        "Some intro text.\n"
        "### `core mind run`\n"
        "Description of run.\n"
        "### `core mind build --all`\n"
        "### not a command heading\n"
        "#### `core ignored`\n"
    )

    inventory = inventory_from_reference(text)

    assert inventory.commands == frozenset(
        {
            ("mind", "run"),
            ("mind", "build", "--all"),
        }
    )


from mind.logic.engines.cli_gate.checks.docs_no_phantom_commands import (
    inventory_from_tree,
)


# ID: 146aa84f-ed51-45d1-aee3-6af77453e8a4
def test_inventory_from_tree():
    # Root command with a group of subcommands, one hidden subgroup
    root = MagicMock()
    root.hidden = False

    visible_leaf = MagicMock()
    visible_leaf.hidden = False
    visible_leaf.commands = None

    hidden_leaf = MagicMock()
    hidden_leaf.hidden = True
    hidden_leaf.commands = None

    nested_leaf = MagicMock()
    nested_leaf.hidden = False
    nested_leaf.commands = None

    subgroup = MagicMock()
    subgroup.hidden = False
    subgroup.commands = {"nested": nested_leaf}

    root.commands = {
        "visible": visible_leaf,
        "secret": hidden_leaf,
        "group": subgroup,
    }

    inventory = inventory_from_tree(root)

    # Inspect the returned inventory through its dataclass fields, discovering them dynamically
    from dataclasses import fields

    field_map = {f.name: getattr(inventory, f.name) for f in fields(inventory)}
    set_values = [v for v in field_map.values() if isinstance(v, frozenset)]

    expected_visible = frozenset({("visible",), ("group", "nested")})
    expected_hidden = frozenset({("secret",)})

    assert expected_visible in set_values
    assert expected_hidden in set_values


from mind.logic.engines.cli_gate.checks.docs_no_phantom_commands import CommandInventory


# ID: 7d11be00-9405-4c73-972d-30bb0c9b2b7f
def test_CommandInventory_groups():
    inventory = CommandInventory(
        commands=frozenset({("a", "b", "c")}),
        hidden=frozenset({("x", "y")}),
    )

    result = inventory.groups

    assert result == frozenset(
        {
            ("a",),
            ("a", "b"),
            ("x",),
        }
    )
    assert isinstance(result, frozenset)




# ID: 5bd1a1cc-d934-406b-a7e4-118d8be9b1d3
def test_CommandInventory():
    inventory = CommandInventory(
        commands=frozenset({("project", "new"), ("project", "delete")}),
        hidden=frozenset({("config", "set", "value")}),
    )

    assert inventory.commands == frozenset({("project", "new"), ("project", "delete")})
    assert inventory.hidden == frozenset({("config", "set", "value")})

    assert inventory.groups == frozenset(
        {
            ("project",),
            ("config",),
            ("config", "set"),
        }
    )
