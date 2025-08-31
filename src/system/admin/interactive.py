# src/system/admin/interactive.py
"""
Implements the interactive, menu-driven TUI for the CORE Admin CLI.
This provides a user-friendly way to discover and run commands.
"""

from __future__ import annotations

import subprocess
import sys

from rich.console import Console
from rich.panel import Panel

console = Console()


def run_command(command: list[str]):
    """Executes a core-admin command as a subprocess."""
    try:
        # We use sys.executable to ensure we're using the python from the correct venv
        subprocess.run([sys.executable, "-m", "poetry", "run", *command], check=True)
    except subprocess.CalledProcessError:
        console.print("[bold red]Command failed. See error output above.[/bold red]")
    except FileNotFoundError:
        console.print("[bold red]Error: 'poetry' command not found.[/bold red]")

    console.print("\n[bold green]Press Enter to return to the menu...[/bold green]")
    input()


def show_development_menu():
    """Displays the AI Development & Self-Healing submenu."""
    while True:
        console.clear()
        console.print(Panel("[bold cyan]AI Development & Self-Healing[/bold cyan]"))
        console.print("  [1] Chat with CORE (Translate idea to command)")
        console.print("  [2] Develop (Execute a high-level goal)")
        console.print("  [3] Fix Headers (Run AI-powered style fixer)")
        console.print("\n  [b] Back to main menu")
        console.print("  [q] Quit")
        choice = console.input("\nEnter your choice: ")

        if choice == "1":
            goal = console.input("Enter your goal in natural language: ")
            if goal:
                run_command(["core-admin", "chat", goal])
        elif choice == "2":
            goal = console.input("Enter the full development goal: ")
            if goal:
                run_command(["core-admin", "develop", goal])
        elif choice == "3":
            run_command(["core-admin", "fix", "headers", "--write"])
        elif choice.lower() == "b":
            return
        elif choice.lower() == "q":
            sys.exit(0)


def show_governance_menu():
    """Displays the Constitutional Governance submenu."""
    while True:
        console.clear()
        console.print(Panel("[bold cyan]Constitutional Governance[/bold cyan]"))
        console.print("  [1] List Proposals")
        console.print("  [2] Sign a Proposal")
        console.print("  [3] Approve a Proposal")
        console.print("  [4] Review Constitution (AI Peer Review)")
        console.print("\n  [b] Back to main menu")
        console.print("  [q] Quit")
        choice = console.input("\nEnter your choice: ")

        if choice == "1":
            run_command(["core-admin", "proposals", "list"])
        elif choice == "2":
            name = console.input("Enter the proposal filename to sign: ")
            if name:
                run_command(["core-admin", "proposals", "sign", name])
        elif choice == "3":
            name = console.input("Enter the proposal filename to approve: ")
            if name:
                run_command(["core-admin", "proposals", "approve", name])
        elif choice == "4":
            run_command(["core-admin", "review", "constitution"])
        elif choice.lower() == "b":
            return
        elif choice.lower() == "q":
            sys.exit(0)


def show_system_menu():
    """Displays the System Health & CI submenu."""
    while True:
        console.clear()
        console.print(Panel("[bold cyan]System Health & CI[/bold cyan]"))
        console.print("  [1] Run Full Check (lint, test, audit)")
        console.print("  [2] Run Only Tests")
        console.print("  [3] Format All Code")
        console.print("\n  [b] Back to main menu")
        console.print("  [q] Quit")
        choice = console.input("\nEnter your choice: ")

        if choice == "1":
            run_command(["core-admin", "system", "check"])
        elif choice == "2":
            run_command(["core-admin", "system", "test"])
        elif choice == "3":
            run_command(["core-admin", "system", "format"])
        elif choice.lower() == "b":
            return
        elif choice.lower() == "q":
            sys.exit(0)


def show_project_lifecycle_menu():
    """Displays the Project Lifecycle submenu."""
    while True:
        console.clear()
        console.print(Panel("[bold cyan]Project Lifecycle[/bold cyan]"))
        console.print("  [1] Create New Governed Application")
        console.print("  [2] Onboard Existing Repository (BYOR)")
        console.print("\n  [b] Back to main menu")
        console.print("  [q] Quit")
        choice = console.input("\nEnter your choice: ")

        if choice == "1":
            name = console.input("Enter the name for the new application: ")
            if name:
                run_command(["core-admin", "new", name, "--write"])
        elif choice == "2":
            path = console.input("Enter the path to the existing repository: ")
            if path:
                run_command(["core-admin", "byor-init", path, "--write"])
        elif choice.lower() == "b":
            return
        elif choice.lower() == "q":
            sys.exit(0)


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