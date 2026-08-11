"""Council Agent CLI entry point."""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer
from pydantic import SecretStr
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from council_agent.config.presets import get_preset_by_name, list_presets
from council_agent.config.settings import get_settings
from council_agent.llm.openrouter import OpenRouterCredential
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
    TrustGrant,
    TrustGrantStore,
    TrustStoreError,
    TrustStoreReason,
    TrustTier,
    default_audit_events_path,
    export_audit_events,
    filter_audit_events,
    load_audit_events_with_integrity,
    local_cli_principal,
    parse_trust_tier,
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
trust_app = typer.Typer(
    help="Manage the authenticated user-owned trust grant store (not Trust Tier)."
)
app.add_typer(presets_app, name="presets")
app.add_typer(sandbox_app, name="sandbox")
app.add_typer(audit_app, name="audit")
app.add_typer(trust_app, name="trust")
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


_DEFAULT_CLI_PRINCIPAL_SCOPES = (
    "read,filesystem:mutate,test,shell,high-risk:manage"
)


def _trust_identity() -> tuple[Any, SecretStr]:
    """Load host-process trust identity without reading project `.env`."""

    raw_verifier = os.environ.get("COUNCIL_AUTH_SECRET")
    if raw_verifier is None or not raw_verifier:
        raise TrustStoreError(
            "COUNCIL_AUTH_SECRET is required for trust-store administration",
            reason=TrustStoreReason.AUTHENTICATION_MISSING,
        )
    principal = local_cli_principal(
        os.environ.get("COUNCIL_PRINCIPAL_ID") or None,
        os.environ.get(
            "COUNCIL_PRINCIPAL_SCOPES",
            _DEFAULT_CLI_PRINCIPAL_SCOPES,
        ),
    )
    return principal, SecretStr(raw_verifier)


def _trust_runtime(
    workspace: Path | None,
) -> tuple[
    TrustGrantStore,
    Any,
    Any,
    Any,
    str,
    str,
]:
    """Build one provider-independent, authenticated trust command runtime."""

    principal, verifier = _trust_identity()
    project = Path(workspace).resolve() if workspace is not None else Path.cwd().resolve()
    store = TrustGrantStore(project)
    request_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    manager, provider = store.service_authentication(
        verifier,
        request_id=request_id,
        session_id=session_id,
    )
    return store, principal, manager, provider, request_id, session_id


def _parse_trust_resource(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError("Trust resource must be valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Trust resource must be a JSON object")
    return parsed


def _parse_trust_expiry(value: str | None) -> datetime | None:
    if value is None:
        return None
    normalized = f"{value[:-1]}+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("Trust expiry must be an ISO-8601 datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Trust expiry must include a timezone")
    return parsed


def _trust_failure(error: Exception) -> None:
    reason = (
        f"\n[bold]Reason:[/bold] {error.reason.value}"
        if isinstance(error, TrustStoreError)
        else ""
    )
    console.print(
        Panel(
            f"{error}{reason}",
            title="Trust Store Error",
            border_style="red",
        )
    )
    raise typer.Exit(code=1) from error


@trust_app.command("grant")
def trust_grant(
    action: str = typer.Argument(
        ...,
        help="Exact recognized top-level action (for example read_file).",
    ),
    resource: str = typer.Argument(
        ...,
        help='Exact JSON resource object (for example {"path":"README.md"}).',
    ),
    scopes: list[str] = typer.Option(
        ...,
        "--scope",
        "-s",
        help="Grant scope; repeat for multiple exact scopes.",
    ),
    expires_at: str | None = typer.Option(
        None,
        "--expires-at",
        help="Optional timezone-aware ISO-8601 expiry.",
    ),
    workspace: Path | None = typer.Option(
        None,
        "--workspace",
        "-w",
        help="Workspace used only to enforce store separation (default: cwd).",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
) -> None:
    """Create one exact self-grant; does not enable Trust Tier runtime."""

    try:
        parsed_resource = _parse_trust_resource(resource)
        expiry = _parse_trust_expiry(expires_at)
        (
            store,
            principal,
            manager,
            provider,
            request_id,
            session_id,
        ) = _trust_runtime(workspace)
        grant = store.grant(
            principal,
            action,
            parsed_resource,
            scopes,
            expires_at=expiry,
            session_id=session_id,
            request_id=request_id,
            authentication_manager=manager,
            step_up_provider=provider,
        )
    except (TrustStoreError, TypeError, ValueError) as exc:
        _trust_failure(exc)
        return
    console.print(
        Panel(
            f"[bold]Grant ID:[/bold] {grant.grant_id}\n"
            f"[bold]Principal:[/bold] {grant.principal_ref}\n"
            f"[bold]Action:[/bold] {grant.action}\n"
            f"[bold]Resource:[/bold] {grant.canonical_resource}\n"
            f"[bold]Scopes:[/bold] "
            f"{', '.join(scope.value for scope in grant.scopes)}\n"
            f"[bold]Expires:[/bold] "
            f"{grant.expires_at.isoformat() if grant.expires_at else 'never'}\n"
            "[bold]Runtime:[/bold] store only; Trust Tier is not enabled",
            title="Trust Grant Created",
            border_style="green",
        )
    )


@trust_app.command("revoke")
def trust_revoke(
    grant_id: str = typer.Argument(..., help="Exact grant ID to revoke."),
    workspace: Path | None = typer.Option(
        None,
        "--workspace",
        "-w",
        help="Workspace used only to enforce store separation (default: cwd).",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
) -> None:
    """Persistently revoke one self-owned grant."""

    try:
        (
            store,
            principal,
            manager,
            provider,
            request_id,
            session_id,
        ) = _trust_runtime(workspace)
        grant = store.revoke(
            principal,
            grant_id,
            session_id=session_id,
            request_id=request_id,
            authentication_manager=manager,
            step_up_provider=provider,
        )
    except (TrustStoreError, TypeError, ValueError) as exc:
        _trust_failure(exc)
        return
    console.print(
        Panel(
            f"[bold]Grant ID:[/bold] {grant.grant_id}\n"
            f"[bold]Revoked at:[/bold] {grant.revoked_at.isoformat()}\n"
            "[bold]Effective:[/bold] immediately; persisted across restart",
            title="Trust Grant Revoked",
            border_style="yellow",
        )
    )


@trust_app.command("list")
def trust_list(
    include_inactive: bool = typer.Option(
        False,
        "--all",
        help="Include expired and revoked records.",
    ),
    workspace: Path | None = typer.Option(
        None,
        "--workspace",
        "-w",
        help="Workspace used only to enforce store separation (default: cwd).",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
) -> None:
    """List authenticated principal-owned grants from the user store."""

    try:
        (
            store,
            principal,
            manager,
            provider,
            request_id,
            session_id,
        ) = _trust_runtime(workspace)
        grants = store.list(
            principal,
            include_inactive=include_inactive,
            session_id=session_id,
            request_id=request_id,
            authentication_manager=manager,
            step_up_provider=provider,
        )
    except (TrustStoreError, TypeError, ValueError) as exc:
        _trust_failure(exc)
        return
    if not grants:
        console.print(
            Panel(
                f"No {'matching' if include_inactive else 'active'} trust grants.\n"
                f"Principal: {principal.audit_ref}\n"
                f"Store: {store.root}\n"
                "Trust Tier runtime is not enabled.",
                title="Trust Grants",
                border_style="yellow",
            )
        )
        return

    table = Table(title=f"Trust grants ({len(grants)}; store only)")
    table.add_column("ID", style="cyan", overflow="fold")
    table.add_column("Action")
    table.add_column("Resource", overflow="fold")
    table.add_column("Scopes", overflow="fold")
    table.add_column("Status")
    table.add_column("Expires")
    now = datetime.now(timezone.utc)
    for grant in grants:
        table.add_row(
            grant.grant_id,
            grant.action,
            grant.canonical_resource,
            ",".join(scope.value for scope in grant.scopes),
            _trust_grant_status(grant, now),
            grant.expires_at.isoformat() if grant.expires_at else "never",
        )
    console.print(table)
    console.print("[dim]Store foundation only; Trust Tier runtime is not enabled.[/dim]")


def _trust_grant_status(grant: TrustGrant, now: datetime) -> str:
    if grant.revoked_at is not None:
        return "revoked"
    if grant.expires_at is not None and now >= grant.expires_at:
        return "expired"
    return "active"


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
        help=(
            "Skip interaction prompts for dangerous/write operations (CI) only; "
            "does not grant scopes, authenticate, create a trust grant, select "
            "a Trust Tier, or elevate privilege."
        ),
    ),
    trust_tier: int = typer.Option(
        int(TrustTier.TIER_0),
        "--trust-tier",
        help=(
            "Trust Tier 0/1/2 for this run (default 0). Independent of --yes and "
            "of `council trust` store administration. Tier 2 requires "
            "high-risk:manage and fresh step-up authentication."
        ),
    ),
) -> None:
    """Run the full planning → execution → verification pipeline."""
    _configure_workspace(workspace)
    settings = get_settings()
    preset_name = preset or settings.council_default_preset
    selected = get_preset_by_name(settings.presets_dir, preset_name)
    confirm_mode = resolve_cli_confirm_mode(yes=yes, is_tty=sys.stdin.isatty())
    try:
        selected_tier = parse_trust_tier(trust_tier)
        provider_credential = OpenRouterCredential(
            settings.openrouter_api_key.get_secret_value(),
        )
        principal = local_cli_principal(
            settings.council_principal_id,
            settings.council_principal_scopes,
        )
    except ValueError as exc:
        console.print(
            Panel(
                str(exc),
                title="Configuration Error",
                border_style="red",
            )
        )
        raise typer.Exit(code=2) from exc
    scope_summary = ", ".join(
        sorted(scope.value for scope in principal.scopes)
    )
    authentication_verifier = settings.council_auth_secret
    if (
        authentication_verifier is not None
        and not authentication_verifier.get_secret_value()
    ):
        authentication_verifier = None
    step_up_status = (
        "configured" if authentication_verifier is not None else "not configured"
    )

    console.print(
        Panel(
            f"[bold]Preset:[/bold] {selected.name}\n"
            f"[bold]Workspace:[/bold] {settings.council_workspace_root}\n"
            f"[bold]Confirm:[/bold] {confirm_mode.value}\n"
            f"[bold]Trust tier:[/bold] {int(selected_tier)}\n"
            f"[bold]Principal:[/bold] {principal.audit_ref}\n"
            f"[bold]Scopes:[/bold] {scope_summary}\n"
            f"[bold]High-risk step-up:[/bold] {step_up_status}\n"
            f"[bold]Task:[/bold] {prompt}",
            title="Council Agent",
            border_style="blue",
        )
    )

    try:
        with console.status("[bold green]Running council pipeline..."):
            result = run_council(
                prompt=prompt,
                preset=selected,
                provider_credential=provider_credential,
                principal=principal,
                verbose=verbose,
                confirm_mode=confirm_mode,
                authentication_verifier=authentication_verifier,
                trust_tier=selected_tier,
            )
    except ValueError as exc:
        console.print(
            Panel(str(exc), title="Trust Tier Error", border_style="red")
        )
        raise typer.Exit(code=2) from exc

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
    if result.final_attempt_id is not None:
        console.print(f"[bold]Final attempt:[/bold] {result.final_attempt_id}")
        console.print(f"[bold]Attempts:[/bold] {len(result.attempts)}")
    if result.stop_reason is not None:
        console.print(f"[bold]Stop reason:[/bold] {result.stop_reason.value}")
    if result.escalated:
        console.print("[bold yellow]Escalation:[/bold yellow] applied")

    console.print(Panel(result.final_output, title="Final Output", border_style="cyan"))


if __name__ == "__main__":
    app()
