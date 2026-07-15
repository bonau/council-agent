"""Council Agent CLI entry point."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from council_agent.config.presets import get_preset_by_name, list_presets
from council_agent.config.settings import get_settings
from council_agent.orchestrator import run_council
from council_agent.sandbox.config import (
    apply_workspace_root,
    init_sandbox,
    is_sandbox_initialized,
    resolve_workspace_root,
)
from council_agent.sandbox.session import SessionManager

app = typer.Typer(
    name="council",
    help="OpenRouter + CrewAI three-phase council CLI (plan, execute, verify).",
    no_args_is_help=True,
)
presets_app = typer.Typer(help="Manage model presets.")
sandbox_app = typer.Typer(help="Manage local sandbox workspace and sessions.")
app.add_typer(presets_app, name="presets")
app.add_typer(sandbox_app, name="sandbox")
console = Console()

def _configure_workspace(workspace: Path | None) -> Path:
    """Resolve workspace root, apply it to settings/guard caches, and return it."""
    root = resolve_workspace_root(workspace)
    apply_workspace_root(root)
    return root


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


@sandbox_app.command("init")
def sandbox_init(
    workspace: Path | None = typer.Option(
        None,
        "--workspace",
        "-w",
        help="Workspace root override (also sets WorkspaceGuard root).",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
) -> None:
    """Initialize `.council/` in the current directory (or --workspace)."""
    target = Path(workspace).resolve() if workspace is not None else Path.cwd()
    already = is_sandbox_initialized(target)
    config = init_sandbox(target)
    apply_workspace_root(Path(config.workspace_root))

    action = "already initialized" if already else "initialized"
    console.print(
        Panel(
            f"[bold]Status:[/bold] {action}\n"
            f"[bold]Workspace root:[/bold] {config.workspace_root}\n"
            f"[bold]Config:[/bold] {target / '.council' / 'config.yaml'}",
            title="Sandbox Init",
            border_style="green",
        )
    )


@sandbox_app.command("status")
def sandbox_status(
    workspace: Path | None = typer.Option(
        None,
        "--workspace",
        "-w",
        help="Workspace root override (also sets WorkspaceGuard root).",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
) -> None:
    """Show sandbox workspace root and latest session summary."""
    project = Path(workspace).resolve() if workspace is not None else Path.cwd()

    if not is_sandbox_initialized(project):
        console.print(
            Panel(
                f"[bold]Initialized:[/bold] no\n"
                f"[bold]Project:[/bold] {project}\n"
                "Run [cyan]council sandbox init[/cyan] to create `.council/`.",
                title="Sandbox Status",
                border_style="yellow",
            )
        )
        raise typer.Exit(code=0)

    root = resolve_workspace_root(workspace, search_from=project)
    apply_workspace_root(root)
    latest = SessionManager.latest(project)

    if latest is None:
        session_text = "No sessions yet."
    else:
        session_text = (
            f"id={latest.meta.session_id}\n"
            f"prompt={latest.meta.prompt!r}\n"
            f"preset={latest.meta.preset}\n"
            f"tool_calls={latest.meta.tool_call_count}\n"
            f"started_at={latest.meta.started_at}\n"
            f"ended_at={latest.meta.ended_at}\n"
            f"status={latest.meta.status}"
        )

    console.print(
        Panel(
            f"[bold]Initialized:[/bold] yes\n"
            f"[bold]Workspace root:[/bold] {root}\n"
            f"[bold]Project:[/bold] {project}\n\n"
            f"[bold]Latest session:[/bold]\n{session_text}",
            title="Sandbox Status",
            border_style="blue",
        )
    )


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
    workspace: Path | None = typer.Option(
        None,
        "--workspace",
        "-w",
        help="Workspace root override (also sets WorkspaceGuard root).",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
) -> None:
    """Run the full planning → execution → verification pipeline."""
    _configure_workspace(workspace)
    settings = get_settings()
    preset_name = preset or settings.council_default_preset
    selected = get_preset_by_name(settings.presets_dir, preset_name)

    console.print(
        Panel(
            f"[bold]Preset:[/bold] {selected.name}\n"
            f"[bold]Workspace:[/bold] {settings.council_workspace_root}\n"
            f"[bold]Task:[/bold] {prompt}",
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
