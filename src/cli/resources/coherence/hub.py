# src/cli/resources/coherence/hub.py
import typer


app = typer.Typer(
    name="coherence",
    help=(
        "Constitutional Coherence Checker — scan ADRs, rule domains, and "
        "northstar documents for candidate contradictions, gaps, and drift. "
        "Governing ADR: ADR-067."
    ),
    no_args_is_help=True,
)
