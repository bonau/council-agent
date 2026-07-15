"""Council Agent CLI entry point."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from council_agent.config.presets import get_preset_by_name, list_presets
from council_agent.config.settings import get_settings
from council_agent.orchestrator import run_council

app = typer.Typer(
    name="council",
    help="OpenRouter + CrewAI three-phase council CLI (plan, execute, verify).",
    no_args_is_help=True,
)
presets_app = typer.Typer(help="Manage model presets.")
app.add_typer(presets_app, name="presets")
console = Console()


@presets_app.command("list")
def presets_list() -> None:
    """List available model presets."""
    settings = get_settings()
    presets = list_presets(settings.presets_dir)

    table = Table(title="Available Presets")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("Planning")
    table.add_column("Execution")
    table.add_column("Verification")
    table.add_column("Escalation")

    for preset in presets:
        table.add_row(
            preset.name,
            preset.description,
            preset.planning.model,
            preset.execution.model,
            preset.verification.model,
            preset.escalation.model,
        )

    console.print(table)


@app.command("run")
def run(
    prompt: str = typer.Argument(..., help="Task prompt for the council to process."),
    preset: str = typer.Option(
        None,
        "--preset",
        "-p",
        help="Preset name (default: COUNCIL_DEFAULT_PRESET).",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show CrewAI verbose output during each phase.",
    ),
) -> None:
    """Run the full planning → execution → verification pipeline."""
    settings = get_settings()
    preset_name = preset or settings.council_default_preset
    selected = get_preset_by_name(settings.presets_dir, preset_name)

    console.print(
        Panel(
            f"[bold]Preset:[/bold] {selected.name}\n[bold]Task:[/bold] {prompt}",
            title="Council Agent",
            border_style="blue",
        )
    )

    with console.status("[bold green]Running council pipeline..."):
        result = run_council(
            prompt=prompt,
            preset=selected,
            api_key=settings.openrouter_api_key,
            verbose=verbose,
        )

    if verbose:
        console.print(Panel(result.plan.raw, title="Planning", border_style="yellow"))
        console.print(
            Panel(result.execution.raw, title="Execution", border_style="green")
        )
        console.print(
            Panel(result.verdict.raw, title="Verification", border_style="magenta")
        )

    status_style = "green" if result.verdict.status.value == "PASS" else "red"
    console.print(
        f"\n[bold]Verdict:[/bold] [{status_style}]{result.verdict.status.value}[/]"
    )
    console.print(f"[bold]Summary:[/bold] {result.verdict.summary}")
    if result.escalated:
        console.print("[bold yellow]Escalation:[/bold yellow] applied")

    console.print(Panel(result.final_output, title="Final Output", border_style="cyan"))


if __name__ == "__main__":
    app()
