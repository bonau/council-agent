"""Council Agent CLI entry point."""

from __future__ import annotations

import sys
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
from council_agent.security import (
    AuditIntegrityError,
    AuditIntegrityReport,
    AuditRecord,
    default_audit_events_path,
    export_audit_events,
    filter_audit_events,
    load_audit_events_with_integrity,
    resolve_cli_confirm_mode,
)

app = typer.Typer(
    name="council",
    help="OpenRouter + CrewAI three-phase council CLI (plan, execute, verify).",
    no_args_is_help=True,
)
presets_app = typer.Typer(help="Manage model presets.")
sandbox_app = typer.Typer(help="Manage local sandbox workspace and sessions.")
audit_app = typer.Typer(help="Show and export structured tool audit logs.")
app.add_typer(presets_app, name="presets")
app.add_typer(sandbox_app, name="sandbox")
app.add_typer(audit_app, name="audit")
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


def _resolve_audit_project(workspace: Path | None) -> Path:
    return Path(workspace).resolve() if workspace is not None else Path.cwd()


def _load_validated_audit(
    events_path: Path,
) -> tuple[list[AuditRecord], AuditIntegrityReport]:
    try:
        return load_audit_events_with_integrity(events_path)
    except AuditIntegrityError as exc:
        console.print(
            Panel(
                str(exc),
                title="Audit Integrity Error",
                border_style="red",
            )
        )
        raise typer.Exit(code=1) from exc


@audit_app.command("show")
def audit_show(
    limit: int = typer.Option(
        50,
        "--limit",
        "-n",
        help="Maximum number of recent events to display.",
        min=1,
    ),
    session: str | None = typer.Option(
        None,
        "--session",
        "-s",
        help="Filter events by session id.",
    ),
    workspace: Path | None = typer.Option(
        None,
        "--workspace",
        "-w",
        help="Project root containing `.council/` (default: cwd).",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
) -> None:
    """Display recent structured audit events."""
    project = _resolve_audit_project(workspace)
    events_path = default_audit_events_path(project)
    all_events, integrity = _load_validated_audit(events_path)
    events = filter_audit_events(
        all_events,
        session_id=session,
    )

    if not events:
        console.print(
            Panel(
                "No audit events."
                + (
                    f"\nFilter session={session}"
                    if session
                    else f"\nLog: {events_path}"
                )
                + f"\nIntegrity: {integrity.status}",
                title="Audit Show",
                border_style="yellow",
            )
        )
        raise typer.Exit(code=0)

    # Show the most recent `limit` events while preserving chronological order.
    shown = events[-limit:]
    table = Table(
        title=(
            f"Audit events ({len(shown)} of {len(events)}; "
            f"integrity={integrity.status})"
        )
    )
    table.add_column("Seq", justify="right")
    table.add_column("Timestamp", style="dim")
    table.add_column("Tool", style="cyan")
    table.add_column("Success")
    table.add_column("Session")
    table.add_column("Error", overflow="fold")

    for event in shown:
        table.add_row(
            str(event.sequence) if event.sequence is not None else "-",
            event.timestamp,
            event.tool,
            (
                "pending"
                if event.success is None
                else "yes"
                if event.success
                else "no"
            ),
            event.session_id or "-",
            event.error or "",
        )

    console.print(table)


@audit_app.command("export")
def audit_export(
    output: Path = typer.Argument(
        ...,
        help="Destination file path for the export (JSONL by default).",
    ),
    session: str | None = typer.Option(
        None,
        "--session",
        "-s",
        help="Filter events by session id.",
    ),
    workspace: Path | None = typer.Option(
        None,
        "--workspace",
        "-w",
        help="Project root containing `.council/` (default: cwd).",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    fmt: str = typer.Option(
        "jsonl",
        "--format",
        "-f",
        help="Export format: jsonl or json.",
    ),
) -> None:
    """Export audit events to a file."""
    if fmt not in {"jsonl", "json"}:
        console.print("[red]Invalid --format; use jsonl or json.[/red]")
        raise typer.Exit(code=1)

    project = _resolve_audit_project(workspace)
    events_path = default_audit_events_path(project)
    all_events, integrity = _load_validated_audit(events_path)
    events = filter_audit_events(
        all_events,
        session_id=session,
    )
    dest = export_audit_events(events, output, format=fmt)
    console.print(
        Panel(
            f"[bold]Exported:[/bold] {len(events)} event(s)\n"
            f"[bold]Format:[/bold] {fmt}\n"
            f"[bold]Integrity:[/bold] {integrity.status}\n"
            f"[bold]Output:[/bold] {dest.resolve()}",
            title="Audit Export",
            border_style="green",
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
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompts for dangerous/write operations (CI).",
    ),
) -> None:
    """Run the full planning → execution → verification pipeline."""
    _configure_workspace(workspace)
    settings = get_settings()
    preset_name = preset or settings.council_default_preset
    selected = get_preset_by_name(settings.presets_dir, preset_name)
    confirm_mode = resolve_cli_confirm_mode(yes=yes, is_tty=sys.stdin.isatty())

    console.print(
        Panel(
            f"[bold]Preset:[/bold] {selected.name}\n"
            f"[bold]Workspace:[/bold] {settings.council_workspace_root}\n"
            f"[bold]Confirm:[/bold] {confirm_mode.value}\n"
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
            confirm_mode=confirm_mode,
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
