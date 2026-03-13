# src/cli/interactive.py
from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)
import sys

from rich.console import Console
from rich.panel import Panel

from shared.utils.subprocess_utils import run_poetry_command


console = Console()


def _show_menu(title: str, options: dict[str, str], actions: dict):
    while True:
        console.clear()
        logger.info(Panel(f"[bold cyan]{title}[/bold cyan]"))
        for key, text in options.items():
            logger.info("  [%s] %s", key, text)
        logger.info("\n  [b] Back | [q] Quit")
        choice = console.input("\nEnter choice: ").lower()
        if choice == "b":
            return
        if choice == "q":
            sys.exit(0)
        action = actions.get(choice)
        if action:
            try:
                action()
            except Exception as e:
                logger.info("[red]Error: %s[/red]", e)
            console.input("\nPress Enter to return...")


# ID: 827a231b-79dd-42ba-8ae4-2e3857a2f4b2
def show_development_menu():
    _show_menu(
        title="AI Development & Quality",
        options={
            "1": "Dev Sync (Fix & Sync Everything)",
            "2": "Chat with CORE (Intent Translation)",
            "3": "Run Project Tests",
            "4": "Interactive Test Generation",
        },
        actions={
            "1": lambda: run_poetry_command(
                "Syncing...", ["core-admin", "dev", "sync", "--write"]
            ),
            "2": lambda: run_poetry_command(
                "Thinking...", ["core-admin", "dev", "chat", console.input("Goal: ")]
            ),
            "3": lambda: run_poetry_command(
                "Testing...", ["core-admin", "code", "test"]
            ),
            "4": lambda: run_poetry_command(
                "Starting...", ["core-admin", "dev", "test", console.input("File: ")]
            ),
        },
    )


# ID: c36a1e25-f2e0-4bf6-b860-1ecdfc6089eb
def show_governance_menu():
    _show_menu(
        title="Constitutional Governance",
        options={
            "1": "Validate Constitution (.intent)",
            "2": "Check Rule Coverage",
            "3": "List A3 Proposals",
            "4": "Query the Mind (Semantic Search)",
        },
        actions={
            "1": lambda: run_poetry_command(
                "Validating...", ["core-admin", "constitution", "validate"]
            ),
            "2": lambda: run_poetry_command(
                "Checking...", ["core-admin", "constitution", "status"]
            ),
            "3": lambda: run_poetry_command(
                "Listing...", ["core-admin", "proposals", "list"]
            ),
            "4": lambda: run_poetry_command(
                "Searching...",
                ["core-admin", "constitution", "query", console.input("Question: ")],
            ),
        },
    )


# ID: 6b97f86f-c37f-4df8-a754-4c1e84c4b575
def show_system_menu():
    """Displays the System Health & CI submenu."""
    _show_menu(
        title="System Health & CI",
        options={
            "1": "Run Full Check (lint, test, audit)",
            "2": "Run Only Tests",
            "3": "Format All Code",
        },
        actions={
            "1": lambda: run_poetry_command(
                "Running system check...", ["core-admin", "check", "system"]
            ),
            "2": lambda: run_poetry_command(
                "Running tests...", ["core-admin", "check", "tests"]
            ),
            "3": lambda: run_poetry_command(
                "Formatting code...", ["core-admin", "fix", "code-style"]
            ),
        },
    )


# ID: 74f08345-03bd-4112-a13f-1353113e2c44
def show_project_lifecycle_menu():
    """Displays the Project Lifecycle submenu."""
    _show_menu(
        title="Project Lifecycle",
        options={
            "1": "Create New Governed Application",
            "2": "Onboard Existing Repository (BYOR)",
        },
        actions={
            "1": lambda: run_poetry_command(
                "Creating new application...",
                [
                    "core-admin",
                    "manage",
                    "project",
                    "new",
                    console.input("Enter the name for the new application: "),
                    "--write",
                ],
            ),
            "2": lambda: run_poetry_command(
                "Onboarding repository...",
                [
                    "core-admin",
                    "manage",
                    "project",
                    "onboard",
                    console.input("Enter the path to the existing repository: "),
                    "--write",
                ],
            ),
        },
    )


# ID: 30f97ec8-8803-4ef3-91cf-4fb31943e28c
def launch_interactive_menu():
    """The main entry point for the interactive TUI menu."""
    while True:
        console.clear()
        logger.info(
            Panel(
                "[bold green]🏛️ Welcome to the CORE Interactive Shell[/bold green]",
                subtitle="Select a command group",
            )
        )
        logger.info("[bold cyan]1.[/bold cyan] AI Development & Self-Healing")
        logger.info("[bold cyan]2.[/bold cyan] Constitutional Governance")
        logger.info("[bold cyan]3.[/bold cyan] System Health & CI")
        logger.info("[bold cyan]4.[/bold cyan] Project Lifecycle")
        logger.info("\n[bold red]q.[/bold red] Quit")
        choice = console.input("\nEnter your choice: ")
        if choice == "1":
            show_development_menu()
        elif choice == "2":
            show_governance_menu()
        elif choice == "3":
            show_system_menu()
        elif choice == "4":
            show_project_lifecycle_menu()
        elif choice.lower() == "q":
            break
