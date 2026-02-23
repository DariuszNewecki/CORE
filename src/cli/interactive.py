# src/body/cli/interactive.py
# ID: 66e15326-323e-4861-97e6-2d7ecddbbac9

from __future__ import annotations

import sys

from rich.console import Console
from rich.panel import Panel

from shared.utils.subprocess_utils import run_poetry_command


console = Console()


def _show_menu(title: str, options: dict[str, str], actions: dict):
    while True:
        console.clear()
        console.print(Panel(f"[bold cyan]{title}[/bold cyan]"))
        for key, text in options.items():
            console.print(f"  [{key}] {text}")
        console.print("\n  [b] Back | [q] Quit")
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
                console.print(f"[red]Error: {e}[/red]")
            console.input("\nPress Enter to return...")


# ID: 49910bc4-e193-4c26-bf7f-7f24b8356480
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


# ID: 431d5b2f-8186-4e61-af93-766a54e40e39
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


# ID: 38f63e99-7a3d-4734-9aaa-188e99e44846
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


# ID: b13f7aa2-3d3a-4442-af86-19bfb95ccfb9
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


# ID: 0493a7e1-3b54-478c-b22f-490a36be8b61
def launch_interactive_menu():
    """The main entry point for the interactive TUI menu."""
    while True:
        console.clear()
        console.print(
            Panel(
                "[bold green]🏛️ Welcome to the CORE Interactive Shell[/bold green]",
                subtitle="Select a command group",
            )
        )
        console.print("[bold cyan]1.[/bold cyan] AI Development & Self-Healing")
        console.print("[bold cyan]2.[/bold cyan] Constitutional Governance")
        console.print("[bold cyan]3.[/bold cyan] System Health & CI")
        console.print("[bold cyan]4.[/bold cyan] Project Lifecycle")
        console.print("\n[bold red]q.[/bold red] Quit")

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
