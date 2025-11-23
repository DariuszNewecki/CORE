# src/body/cli/interactive.py
"""
Implements the interactive, menu-driven TUI for the CORE Admin CLI.
This provides a user-friendly way to discover and run commands.
"""

from __future__ import annotations

import sys
from collections.abc import Callable

from rich.console import Console
from rich.panel import Panel

from shared.utils.subprocess_utils import run_poetry_command

console = Console()


def _show_menu(title: str, options: dict[str, str], actions: dict[str, Callable]):
    """Generic helper to display a menu, get input, and execute an action."""
    while True:
        console.clear()
        console.print(Panel(f"[bold cyan]{title}[/bold cyan]"))
        for key, text in options.items():
            console.print(f"  [{key}] {text}")

        console.print("\n  [b] Back to main menu")
        console.print("  [q] Quit")
        choice = console.input("\nEnter your choice: ").lower()

        if choice == "b":
            return
        if choice == "q":
            sys.exit(0)

        action = actions.get(choice)
        if action:
            try:
                action()
            except Exception as e:
                console.print(f"[bold red]Command failed: {e}[/bold red]")
            console.print(
                "\n[bold green]Press Enter to return to the menu...[/bold green]"
            )
            input()
        else:
            console.print(
                f"[bold red]Invalid choice '{choice}'. Please try again.[/bold red]"
            )
            input("Press Enter to continue...")


# ID: e4f81e87-71c1-41c1-bfed-fdba926db71f
def show_development_menu():
    """Displays the AI Development & Self-Healing submenu."""
    _show_menu(
        title="AI Development & Self-Healing",
        options={
            "1": "Chat with CORE (Translate idea to command)",
            "2": "Develop (Execute a high-level goal)",
            "3": "Fix Headers (Run AI-powered style fixer)",
        },
        actions={
            "1": lambda: run_poetry_command(
                "Translating goal...",
                ["core-admin", "chat", console.input("Enter your goal: ")],
            ),
            "2": lambda: run_poetry_command(
                "Executing goal...",
                [
                    "core-admin",
                    "run",
                    "develop",
                    console.input("Enter the full development goal: "),
                ],
            ),
            "3": lambda: run_poetry_command(
                "Fixing headers...", ["core-admin", "fix", "headers", "--write"]
            ),
        },
    )


# ID: 91af5862-021e-4c3b-ba18-51deb032382c
def show_governance_menu():
    """Displays the Constitutional Governance submenu."""
    _show_menu(
        title="Constitutional Governance",
        options={
            "1": "List Proposals",
            "2": "Sign a Proposal",
            "3": "Approve a Proposal",
            "4": "Generate a new Operator Key",
            "5": "Review Constitution (AI Peer Review)",
        },
        actions={
            "1": lambda: run_poetry_command(
                "Listing proposals...", ["core-admin", "manage", "proposals", "list"]
            ),
            "2": lambda: run_poetry_command(
                "Signing proposal...",
                [
                    "core-admin",
                    "manage",
                    "proposals",
                    "sign",
                    console.input("Enter proposal filename to sign: "),
                ],
            ),
            "3": lambda: run_poetry_command(
                "Approving proposal...",
                [
                    "core-admin",
                    "manage",
                    "proposals",
                    "approve",
                    console.input("Enter proposal filename to approve: "),
                ],
            ),
            "4": lambda: run_poetry_command(
                "Generating key...",
                [
                    "core-admin",
                    "manage",
                    "keys",
                    "generate",
                    console.input("Enter identity for key (e.g., email): "),
                ],
            ),
            "5": lambda: run_poetry_command(
                "Reviewing constitution...", ["core-admin", "review", "constitution"]
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
