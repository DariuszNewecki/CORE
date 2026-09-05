# src/cli/runtime_external_verify.py

"""
Pre-bootstrap dispatch and implementation for
``core-admin runtime external-verify --target <path>`` (Unit B, EC-1A
safety package; Governor ruling 2026-09-05).

Import-order problem this module solves: ``cli.admin_cli`` imports
``body.infrastructure.bootstrap`` at module load, which transitively
imports ``GitService``, which loads ``shared.infrastructure.intent.
operational_config`` at *its* import time, which calls
``get_intent_repository()`` as a module-level side effect. By the time
Typer would dispatch to an ordinary subcommand registered inside
``cli.admin_cli``, all of that has already happened -- using whatever
``REPO_PATH``/``MIND`` existed *before* any subcommand body could set
them. Registering ``external-verify`` as an ordinary Typer subcommand
therefore cannot satisfy "bind the environment before the heavy runtime
imports."

This module is deliberately import-light at module scope: stdlib plus
Rich (for output consistent with the rest of ``cli/``'s presentation
layer -- ``architecture.channels.cli_rendering_allowed``). Rich has no
CORE-internal coupling, so importing it here carries none of the
import-order risk this module exists to avoid. ``cli.admin_cli`` can
therefore import this module unconditionally, at the very top of the
file, before its own heavy imports, and decide -- via
:func:`matches_route` -- whether to dispatch here (via :func:`run`) and
exit, or fall through to the ordinary Typer application unchanged. It is
NOT a general command router: it recognizes exactly one fixed route and
performs no passthrough of arbitrary commands.

Deliberately does NOT import ``cli.utils`` (for its ``console``/exit-code
helpers): ``cli/utils/__init__.py`` eagerly imports ``decorators.py``,
which imports ``shared.infrastructure.database.session_manager``, which
imports ``shared.config`` -- constructing the ``Settings()`` singleton
before this guard has bound ``REPO_PATH``/``MIND``. Two local ``Console``
instances are constructed directly from ``rich.console`` instead.

Verification only: no mutation, no database connection, no `.intent/`
writes, no ProposalExecutor/ActionExecutor/worker invocation.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from urllib.parse import urlsplit

from rich.console import Console


# Fixed, generous width rather than the default terminal-width detection:
# this command's output is a verification report an operator or script may
# grep/parse, and Rich's default wrapping would otherwise insert a
# mid-string newline into a long target path, corrupting it.
_console = Console(width=4096)
_err_console = Console(stderr=True, width=4096)

ROUTE: tuple[str, str] = ("runtime", "external-verify")

_RECURSION_GUARD_ENV = "CORE_EXTERNAL_VERIFY_ACTIVE"

# Exit codes distinguish verified success from a pre-flight binding
# refusal (bad target/env, or recursive invocation) from a post-guard
# internal bootstrap failure (construction exception, or runtime roots
# disagreeing after CoreContext was built). Values deliberately mirror
# the existing cli.utils.exit_codes convention (EXIT_OK / EXIT_CONFIG_
# ERROR / EXIT_INTERNAL_ERROR, F-10.1b) rather than inventing a new
# taxonomy -- but that module is NOT imported here: cli.utils.__init__
# eagerly imports decorators.py, which imports shared.infrastructure.
# database.session_manager, which imports shared.config -- constructing
# the Settings() singleton before this guard has bound REPO_PATH/MIND.
# Defined locally to preserve the same import-ordering guarantee.
EXIT_VERIFIED = 0
EXIT_BINDING_REFUSED = 2
EXIT_INTERNAL_FAILURE = 64


# ID: 5d6f43d5-ea0a-47c2-86e7-1b1ed3c65f80
def matches_route(argv: list[str]) -> bool:
    """Return True if *argv* (``sys.argv[1:]``) invokes the external-verify
    route. Pure prefix match on the first two tokens -- no argument
    parsing, no imports, safe to call before anything else in the process
    has been touched."""
    return len(argv) >= 2 and tuple(argv[:2]) == ROUTE


def _sanitize_database_identity(database_url: str) -> str:
    """Return "host[:port]/dbname" for *database_url*, never credentials
    or query parameters. Falls back to a non-revealing placeholder if the
    URL cannot be parsed safely."""
    try:
        parts = urlsplit(database_url)
        host = parts.hostname
        dbname = parts.path.lstrip("/")
        if not host or not dbname:
            return "<database configuration present>"
        port = f":{parts.port}" if parts.port else ""
        return f"{host}{port}/{dbname}"
    except Exception:
        return "<database configuration present>"


# ID: 3731341e-6dea-4b27-9157-42f36749e157
def find_root_disagreements(
    *,
    git_service_repo_path: Path | None,
    settings_repo_path: Path | None,
    settings_mind: Path | None,
    bootstrap_registry_repo_path: Path | None,
    service_registry_repo_path: Path | None,
    intent_repository_root: Path | None,
    expected_target: Path,
    expected_mind: Path,
) -> list[str]:
    """Pure comparison over already-observed roots -- no imports, no I/O.

    *expected_target* and *expected_mind* must already be canonical
    (resolved); every ``*_repo_path``/``*_mind``/``*_root`` argument is
    resolved here before comparison. Returns one ``"<label>=<value>"``
    string per root that disagrees with its expected value; an empty list
    means every runtime root agrees.
    """
    observed = {
        "CoreContext.git_service.repo_path": (
            git_service_repo_path,
            expected_target,
        ),
        "Settings.REPO_PATH": (settings_repo_path, expected_target),
        "Settings.MIND": (settings_mind, expected_mind),
        "BootstrapRegistry.get_repo_path()": (
            bootstrap_registry_repo_path,
            expected_target,
        ),
        "ServiceRegistry.repo_path": (service_registry_repo_path, expected_target),
        "IntentRepository.root": (intent_repository_root, expected_mind),
    }
    disagreements: list[str] = []
    for label, (actual, expected) in observed.items():
        resolved_actual = actual.resolve() if actual is not None else None
        if resolved_actual != expected:
            disagreements.append(f"{label}={resolved_actual}")
    return disagreements


class _EnvironScope:
    """Restore a fixed set of environment variables to their prior state
    on exit, regardless of success or failure. Keeps this module's
    environment mutations scoped to one :func:`run` call so repeated
    invocations in one process (tests; a hypothetical long-lived host)
    never leak state to the next call."""

    def __init__(self, keys: list[str]) -> None:
        self._keys = keys
        self._prior: dict[str, str | None] = {}

    def __enter__(self) -> _EnvironScope:
        self._prior = {k: os.environ.get(k) for k in self._keys}
        return self

    def __exit__(self, *exc_info: object) -> None:
        for key, value in self._prior.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


# ID: 381823e7-4f3e-4fa7-a3d6-b7376b727c54
def run(argv: list[str]) -> int:
    """Execute the external-verify route. *argv* is ``sys.argv[1:]``
    (i.e. includes the leading ``"runtime", "external-verify"`` tokens
    already matched by :func:`matches_route`).

    Verification only: constructs the ordinary, unmodified CoreContext
    to prove a safe bootstrap is possible, then exits. Never executes a
    proposal, action, or worker; never mutates the target; never connects
    to the database (CoreContext wires a session *factory*, it does not
    open a session).
    """
    if os.environ.get(_RECURSION_GUARD_ENV):
        _err_console.print("REFUSED — recursive external-verify invocation detected")
        return EXIT_BINDING_REFUSED

    with _EnvironScope([_RECURSION_GUARD_ENV, "REPO_PATH", "MIND"]):
        os.environ[_RECURSION_GUARD_ENV] = "1"

        parser = argparse.ArgumentParser(
            prog="core-admin runtime external-verify",
            description=(
                "Verify a safe, fail-closed process binding to one "
                "external Git repository. Performs no mutation and does "
                "not connect to the database."
            ),
        )
        parser.add_argument(
            "--target",
            required=True,
            help="Path to the external target repository",
        )
        ns = parser.parse_args(argv[2:])

        try:
            canonical_target = Path(ns.target).resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            _err_console.print(
                f"REFUSED — target does not resolve to an existing path: "
                f"{ns.target} ({exc})"
            )
            return EXIT_BINDING_REFUSED

        canonical_mind = canonical_target / ".intent"

        # Bind the child/runtime environment BEFORE any CORE module that
        # constructs Settings() or the IntentRepository singleton is
        # imported below.
        os.environ["REPO_PATH"] = str(canonical_target)
        os.environ["MIND"] = str(canonical_mind)

        database_url = os.environ.get("DATABASE_URL")

        # CORE's own repository root, computed independently of
        # shared.config (which this function must not import yet) —
        # same technique shared/config.py itself uses for REPO_ROOT.
        core_repo_root = Path(__file__).resolve().parents[2]

        from shared.infrastructure.external_target_binding import (
            ExternalTargetBindingError,
            validate_external_target_binding,
        )

        try:
            validate_external_target_binding(
                canonical_target,
                repo_path_value=os.environ.get("REPO_PATH"),
                mind_value=os.environ.get("MIND"),
                database_url_value=database_url,
                core_repo_root=core_repo_root,
            )
        except ExternalTargetBindingError as exc:
            _err_console.print(f"REFUSED — {exc}")
            return EXIT_BINDING_REFUSED

        # Guard passed. Only now import the ordinary runtime/bootstrap
        # components — unmodified, exactly as cli.admin_cli itself uses
        # them.
        try:
            from body.infrastructure.bootstrap import create_core_context
            from body.services.service_registry import service_registry
            from shared.config import settings
            from shared.infrastructure.bootstrap_registry import (
                bootstrap_registry,
            )
            from shared.infrastructure.intent.intent_repository import (
                get_intent_repository,
            )

            core_context = create_core_context(service_registry)

            disagreements = find_root_disagreements(
                git_service_repo_path=core_context.git_service.repo_path,
                settings_repo_path=settings.REPO_PATH,
                settings_mind=settings.MIND,
                bootstrap_registry_repo_path=bootstrap_registry.get_repo_path(),
                service_registry_repo_path=(
                    Path(service_registry.repo_path)
                    if service_registry.repo_path is not None
                    else None
                ),
                intent_repository_root=get_intent_repository().root,
                expected_target=canonical_target,
                expected_mind=canonical_mind,
            )

            if disagreements:
                _err_console.print("REFUSED — runtime roots disagree after bootstrap:")
                for disagreement in disagreements:
                    _err_console.print(f"  {disagreement}")
                return EXIT_INTERNAL_FAILURE

            git_sha = "<unavailable>"
            tree_hash = "<unavailable>"
            try:
                git_sha = core_context.git_service.get_current_commit()
            except Exception:
                pass
            try:
                tree_hash = core_context.git_service.write_tree()
            except Exception:
                pass

            db_identity = (
                _sanitize_database_identity(database_url) if database_url else "<none>"
            )

            _console.print(f"Target:         {canonical_target}")
            _console.print(f"Target .intent: {canonical_mind}")
            _console.print(f"Git SHA:        {git_sha}")
            _console.print(f"Git tree hash:  {tree_hash}")
            _console.print(f"Database:       {db_identity}")
            _console.print("VERIFIED — no mutation executed")
            return EXIT_VERIFIED

        except ExternalTargetBindingError as exc:
            # Defensive: the guard above already ran successfully, so this
            # should not trigger in practice.
            _err_console.print(f"REFUSED — {exc}")
            return EXIT_BINDING_REFUSED
        except Exception as exc:
            _err_console.print(f"INTERNAL BOOTSTRAP FAILURE — {exc}")
            return EXIT_INTERNAL_FAILURE
