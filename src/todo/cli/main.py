"""Main CLI application entry point."""

import asyncio
import contextlib
import json
from datetime import date, datetime, timedelta
from datetime import time as dt_time
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from ..ai.background import BackgroundEnrichmentService
from ..ai.enrichment_service import EnrichmentService
from ..ai.event_parser import EventParser
from ..core.config import get_app_config
from ..core.dates import parse_datetime, parse_due_date
from ..db.connection import DatabaseConnection
from ..db.migrations import MigrationManager
from ..db.repository import (
    AIEnrichmentRepository,
    ContactRepository,
    EventRepository,
    TodoRepository,
)
from ..gcal.client import CalendarAuthError, GoogleCalendarClient
from ..models import AIProvider

console = Console()
# Status/warning output in --json mode goes here so stdout stays pure JSON.
console_err = Console(stderr=True)
app = typer.Typer(
    name="todo",
    help="AI-powered terminal todo application for developers",
    add_completion=False,
    no_args_is_help=True,
)

# Global variables - initialized lazily
config = None
db = None
migration_manager = None
todo_repo = None
ai_repo = None
enrichment_service = None
background_service = None
event_repo = None
contact_repo = None
event_parser = None
gcal_client = None


def _initialize_services():
    """Initialize services lazily - only when actually needed."""
    global \
        config, \
        db, \
        migration_manager, \
        todo_repo, \
        ai_repo, \
        enrichment_service, \
        background_service, \
        event_repo, \
        contact_repo, \
        event_parser, \
        gcal_client

    if db is not None:
        return  # Already initialized

    try:
        config = get_app_config()
        db = DatabaseConnection(config.database.database_path)

        # Initialize database schema if needed
        migration_manager = MigrationManager(db)
        if not migration_manager.is_schema_initialized():
            console.print(
                "[yellow]⚠ Database not initialized. Initializing...[/yellow]"
            )
            migration_manager.run_migrations()

        # Ensure newer tables/columns exist even on databases initialized
        # before they were added. Idempotent.
        migration_manager.ensure_events_schema()
        migration_manager.ensure_completion_note()

        todo_repo = TodoRepository(db)
        ai_repo = AIEnrichmentRepository(db)
        enrichment_service = EnrichmentService(db)
        background_service = BackgroundEnrichmentService(db)
        event_repo = EventRepository(db)
        contact_repo = ContactRepository(db)
        event_parser = EventParser()
        gcal_client = GoogleCalendarClient(config.calendar)
    except RuntimeError as e:
        # Handle database lock errors gracefully
        console.print(f"[red]✗ Database Error:[/red] {e}")
        console.print("\n[yellow]💡 Troubleshooting tips:[/yellow]")
        console.print(
            "• Check if another todo instance is running: [dim]ps aux | grep todo[/dim]"
        )
        console.print("• Kill any hanging processes: [dim]pkill -f todo[/dim]")
        console.print("• If the issue persists, restart your terminal or reboot")
        import sys

        sys.exit(1)
    except Exception as e:
        console.print(f"[red]✗ Unexpected error initializing database:[/red] {e}")
        console.print(
            "[yellow]💡 Please check your database configuration and try again.[/yellow]"
        )
        import sys

        sys.exit(1)


def _enum_val(value: Any) -> Any:
    """Return .value for enums, otherwise the value unchanged."""
    return value.value if hasattr(value, "value") else value


def _emit_json(payload: Any) -> None:
    """Print a JSON payload to stdout (datetimes serialized via str)."""
    print(json.dumps(payload, default=str))


def _enrichment_to_dict(enrichment: Any) -> dict[str, Any] | None:
    """Serialize an AI enrichment record to a plain dict."""
    if not enrichment:
        return None
    return {
        "category": enrichment.suggested_category,
        "priority": _enum_val(enrichment.suggested_priority),
        "size": _enum_val(enrichment.suggested_size),
        "estimated_duration_minutes": enrichment.estimated_duration_minutes,
        "confidence": enrichment.confidence_score,
        "reasoning": enrichment.reasoning,
    }


def _todo_to_dict(todo: Any, ai_enrichment: Any = None) -> dict[str, Any]:
    """Serialize a Todo (optionally with AI enrichment) to a plain dict."""
    if todo.category_id and todo.category:
        category = getattr(todo.category, "name", str(todo.category))
    elif ai_enrichment and ai_enrichment.suggested_category:
        category = ai_enrichment.suggested_category
    else:
        category = None
    return {
        "id": todo.id,
        "title": todo.title,
        "description": todo.description,
        "status": _enum_val(todo.status),
        "priority": _enum_val(todo.final_priority),
        "size": _enum_val(todo.final_size),
        "category": category,
        "points_earned": todo.total_points_earned,
        "due_date": todo.due_date,
        "is_overdue": todo.is_overdue,
        "created_at": todo.created_at,
        "completed_at": todo.completed_at,
        "completion_note": todo.completion_note,
        "ai_enriched": ai_enrichment is not None,
    }


def _event_to_dict(event: Any) -> dict[str, Any]:
    """Serialize an Event to a plain dict."""
    return {
        "id": event.id,
        "title": event.title,
        "description": event.description,
        "start_at": event.start_at,
        "end_at": event.end_at,
        "all_day": event.all_day,
        "location": event.location,
        "status": _enum_val(event.status),
        "attendees": list(event.attendees),
        "google_event_id": event.google_event_id,
        "is_synced": event.is_synced,
        "created_at": event.created_at,
    }


def _push_event_to_google(event: Any) -> str | None:
    """Push an event to Google Calendar and persist its id.

    Returns None on success, or an error message string on failure.
    """
    try:
        gid = gcal_client.push_event(event)
    except CalendarAuthError as e:
        return str(e)
    except Exception as e:  # noqa: BLE001 - report any push failure to the user
        return f"Google Calendar push failed: {e}"
    event_repo.set_google_ids(event.id, gid, gcal_client.calendar_id)
    event.google_event_id = gid
    event.google_calendar_id = gcal_client.calendar_id
    return None


def _remove_event_from_google(google_event_id: str | None) -> None:
    """Best-effort delete of a Google Calendar event; ignores failures."""
    if not google_event_id:
        return
    with contextlib.suppress(Exception):  # removal is best-effort
        gcal_client.delete_event(google_event_id)


@app.command("version")
def version() -> None:
    """Show application version."""
    console.print("todo version 0.1.0")


@app.command("add")
def add_todo(
    task: str,
    description: str | None = typer.Option(
        None, "--desc", "-d", help="Task description"
    ),
    no_ai: bool = typer.Option(False, "--no-ai", help="Skip AI enrichment"),
    provider: str | None = typer.Option(
        None, "--provider", "-p", help="AI provider (openai/anthropic)"
    ),
    due: str | None = typer.Option(
        None,
        "--due",
        "-D",
        help="Due date, e.g. 'today', 'EOW', 'next monday', '6/11'",
    ),
    json_out: bool = typer.Option(
        False, "--json", "-j", help="Emit result as JSON (machine-readable)"
    ),
) -> None:
    """Add a new todo task with optional AI enrichment."""
    _initialize_services()

    # In JSON mode, status/errors go to stderr so stdout stays pure JSON.
    out = console_err if json_out else console

    # Validate input
    if not task or not task.strip():
        out.print("[red]✗ Task title cannot be empty[/red]")
        if json_out:
            _emit_json({"error": "Task title cannot be empty"})
        return

    # Parse the due date up front so a bad value fails before we create anything.
    due_date = None
    if due:
        try:
            due_date = parse_due_date(due)
        except ValueError as e:
            out.print(f"[red]✗ {e}[/red]")
            if json_out:
                _emit_json({"error": str(e)})
            return

    # Create the basic todo
    try:
        todo = todo_repo.create_todo(task.strip(), description)
        if due_date:
            todo_repo.update_todo(todo.id, {"due_date": due_date})
        if not json_out:
            console.print(f"[green]✓ Added task:[/green] {task.strip()}")
            console.print(f"[dim]Task ID: {todo.id}[/dim]")
            if due_date:
                console.print(f"[dim]Due: {due_date.isoformat()}[/dim]")
    except Exception as e:
        error_msg = str(e)
        if "string_too_short" in error_msg or "at least 1 character" in error_msg:
            error_msg = "Task title cannot be empty"
            out.print("[red]✗ Task title cannot be empty[/red]")
        else:
            out.print(f"[red]✗ Error creating task: {error_msg}[/red]")
        if json_out:
            _emit_json({"error": error_msg})
        return

    # AI enrichment
    enrichment = None
    if not no_ai and config.ai.enable_auto_enrichment:
        out.print("\n[blue]🤖 AI analyzing task...[/blue]")

        ai_provider = None
        if provider:
            try:
                ai_provider = AIProvider(provider)
            except ValueError:
                out.print(f"[red]Invalid provider: {provider}[/red]")
                if json_out:
                    _emit_json({"error": f"Invalid provider: {provider}"})
                return

        # Get AI enrichment
        enrichment = asyncio.run(
            _enrich_todo_async(todo.id, task, description, ai_provider)
        )

        if enrichment:
            # Auto-apply high confidence suggestions
            if enrichment.confidence_score >= config.ai.confidence_threshold:
                _apply_enrichment(todo.id, enrichment)
                if not json_out:
                    _display_enrichment_results(enrichment)
                    console.print(
                        "[green]✓ High confidence suggestions applied automatically[/green]"
                    )
            elif not json_out:
                _display_enrichment_results(enrichment)
                console.print(
                    f"[yellow]⚠ Suggestions available (confidence: {enrichment.confidence_score:.1%})[/yellow]"
                )
                console.print(
                    "[dim]Use 'todo show <id>' to review and apply suggestions[/dim]"
                )
        elif not json_out:
            console.print("[red]✗ AI enrichment failed[/red]")

    if json_out:
        # Re-fetch so applied enrichment is reflected in the payload.
        todo = todo_repo.get_by_id(todo.id) or todo
        payload = _todo_to_dict(todo, enrichment)
        payload["enrichment"] = _enrichment_to_dict(enrichment)
        _emit_json(payload)


async def _enrich_todo_async(
    todo_id: int, title: str, description: str | None, provider: AIProvider | None
) -> Any | None:
    """Run AI enrichment asynchronously."""
    enrichment = await enrichment_service.enrich_todo(
        title, description, None, provider
    )
    if enrichment:
        enrichment.todo_id = todo_id
        ai_repo.save_enrichment(enrichment)
    return enrichment


def _display_enrichment_results(enrichment) -> None:
    """Display AI enrichment results in a nice table."""
    table = Table(title="🤖 AI Suggestions", show_header=True, header_style="bold blue")
    table.add_column("Aspect", style="cyan", no_wrap=True)
    table.add_column("Suggestion", style="white")
    table.add_column("Confidence", style="green", justify="right")

    table.add_row(
        "Category",
        enrichment.suggested_category or "N/A",
        f"{enrichment.confidence_score:.1%}",
    )
    table.add_row(
        "Priority",
        enrichment.suggested_priority.value if enrichment.suggested_priority else "N/A",
        f"{enrichment.confidence_score:.1%}",
    )
    table.add_row(
        "Size",
        enrichment.suggested_size.value if enrichment.suggested_size else "N/A",
        f"{enrichment.confidence_score:.1%}",
    )
    table.add_row(
        "Duration",
        f"{enrichment.estimated_duration_minutes}min"
        if enrichment.estimated_duration_minutes
        else "N/A",
        f"{enrichment.confidence_score:.1%}",
    )

    console.print(table)

    if enrichment.reasoning:
        console.print(f"\n[dim]Reasoning: {enrichment.reasoning}[/dim]")


def _apply_enrichment(todo_id: int, enrichment) -> None:
    """Apply AI enrichment to a todo."""
    try:
        # Prepare updates based on AI suggestions
        updates = {}

        if enrichment.suggested_size:
            updates["final_size"] = enrichment.suggested_size.value

        if enrichment.suggested_priority:
            updates["final_priority"] = enrichment.suggested_priority.value

        # Apply updates to the todo
        if updates:
            todo_repo.update_todo(todo_id, updates)

    except Exception as e:
        # Don't fail silently, but don't crash the CLI either
        console.print(
            f"[yellow]⚠ Warning: Could not apply AI suggestions: {e}[/yellow]"
        )


@app.command("list")
@app.command("ls")
def list_todos(
    limit: int = typer.Option(
        10, "--limit", "-l", help="Maximum number of todos to show"
    ),
    all_todos: bool = typer.Option(
        False, "--all", "-a", help="Show all todos including completed"
    ),
    json_out: bool = typer.Option(
        False, "--json", "-j", help="Emit todos as JSON (machine-readable)"
    ),
) -> None:
    """List active todos with AI enrichment status."""
    _initialize_services()

    try:
        if all_todos:
            # For now, just show active todos
            todos = todo_repo.get_all()[:limit]
        else:
            todos = todo_repo.get_active_todos(limit)
    except Exception as e:
        error_msg = str(e)
        if json_out:
            _emit_json({"error": error_msg, "todos": []})
            return
        if "string_too_short" in error_msg or "at least 1 character" in error_msg:
            console.print(
                "[red]✗ Found invalid todos with empty titles in database[/red]"
            )
            console.print(
                "[dim]Run 'todo db' to check database status or contact support[/dim]"
            )
        else:
            console.print(f"[red]✗ Error retrieving todos: {error_msg}[/red]")
        return

    if json_out:
        _emit_json(
            {
                "todos": [
                    _todo_to_dict(todo, ai_repo.get_latest_by_todo_id(todo.id))
                    for todo in todos
                ]
            }
        )
        return

    if not todos:
        console.print("[yellow]No active todos found[/yellow]")
        console.print("[dim]Use 'todo add <task>' to create your first todo![/dim]")
        return

    # Create table
    table = Table(title="📋 Your Todos", show_header=True, header_style="bold blue")
    table.add_column("ID", style="cyan", width=3)
    table.add_column("Task", style="white")
    table.add_column("Category", style="blue", width=10)
    table.add_column("Status", style="green")
    table.add_column("Priority", style="yellow")
    table.add_column("Due", style="cyan", width=10)
    table.add_column("AI", style="magenta", width=3)

    for todo in todos:
        # Check if todo has AI enrichment
        ai_enrichment = ai_repo.get_latest_by_todo_id(todo.id)
        ai_status = "✓" if ai_enrichment else "○"

        # Format category
        if todo.category_id and todo.category:
            category = (
                todo.category.name
                if hasattr(todo.category, "name")
                else str(todo.category)
            )
        elif ai_enrichment and ai_enrichment.suggested_category:
            category = ai_enrichment.suggested_category
        else:
            category = "General"

        # Format priority
        if todo.final_priority:
            priority = (
                todo.final_priority.value.upper()
                if hasattr(todo.final_priority, "value")
                else str(todo.final_priority).upper()
            )
        else:
            priority = "N/A"

        # Format status
        status_icon = "✓" if str(todo.status).lower() == "completed" else "○"
        status_value = (
            todo.status.value if hasattr(todo.status, "value") else str(todo.status)
        )
        status_text = f"{status_icon} {status_value.title()}"

        # Format due date (red when overdue)
        if todo.due_date:
            due_text = todo.due_date.isoformat()
            if todo.is_overdue:
                due_text = f"[red]{due_text}[/red]"
        else:
            due_text = "—"

        table.add_row(
            str(todo.id),
            todo.title[:60] + "..." if len(todo.title) > 60 else todo.title,
            category[:10],  # Truncate category to fit column width
            status_text,
            priority,
            due_text,
            ai_status,
        )

    console.print(table)


@app.command("done")
@app.command("complete")
def complete_todo(
    todo_ids: list[int] = typer.Argument(
        ..., help="One or more todo IDs to mark as completed"
    ),
    note: str | None = typer.Option(
        None, "--note", "-n", help="Completion note (applied to each todo)"
    ),
    json_out: bool = typer.Option(
        False, "--json", "-j", help="Emit result as JSON (machine-readable)"
    ),
) -> None:
    """Mark one or more todos as completed.

    Examples:
        todo done 42                    # Complete single todo
        todo done 10 11 12             # Complete multiple todos
        todo complete 5 7 9            # Same using 'complete' alias
    """
    _initialize_services()

    # In JSON mode, human-readable progress goes to stderr; JSON to stdout.
    out = console_err if json_out else console

    completed_count = 0
    failed_count = 0
    total_points = 0
    all_achievements = []
    completed_ids: list[int] = []
    failed_ids: list[int] = []

    for todo_id in todo_ids:
        try:
            todo = todo_repo.complete_todo(todo_id, note=note)

            if todo:
                completed_count += 1
                completed_ids.append(todo_id)
                out.print(f"[green]✓ Completed:[/green] {todo.title}")

                # Display gamification results
                if hasattr(todo, "scoring_result") and todo.scoring_result:
                    scoring = todo.scoring_result
                    total_points += scoring["total_points"]

                    # Points breakdown (show for each todo)
                    if scoring["bonus_points"] > 0:
                        out.print(
                            f"[yellow]  🎉 Earned {scoring['total_points']} points! "
                            f"({scoring['base_points']} base + {scoring['bonus_points']} bonus)[/yellow]"
                        )
                    else:
                        out.print(
                            f"[yellow]  🎉 Earned {scoring['total_points']} points![/yellow]"
                        )

                    # Collect achievements for summary at the end
                    if scoring.get("achievements_unlocked"):
                        all_achievements.extend(scoring["achievements_unlocked"])

                elif todo.total_points_earned:
                    # Fallback for basic points display
                    total_points += todo.total_points_earned
                    out.print(
                        f"[yellow]  🎉 Earned {todo.total_points_earned} points![/yellow]"
                    )
            else:
                failed_count += 1
                failed_ids.append(todo_id)
                out.print(f"[red]✗ Todo {todo_id} not found or already completed[/red]")
        except Exception as e:
            failed_count += 1
            failed_ids.append(todo_id)
            error_msg = str(e)
            if "foreign key constraint" in error_msg.lower():
                out.print(
                    f"[red]✗ Cannot complete todo {todo_id}: This todo has related data that must be cleaned up first[/red]"
                )
            elif "not found" in error_msg.lower():
                out.print(f"[red]✗ Todo {todo_id} not found[/red]")
            else:
                out.print(f"[red]✗ Error completing todo {todo_id}: {error_msg}[/red]")

    # Summary for multiple todos
    if len(todo_ids) > 1:
        out.print()
        if completed_count > 0:
            out.print(f"[green]📊 Summary: {completed_count} todos completed[/green]")
            if total_points > 0:
                out.print(f"[yellow]🎯 Total points earned: {total_points}[/yellow]")

            # Show unique achievements unlocked
            if all_achievements:
                unique_achievements = {a.name: a for a in all_achievements}
                out.print(
                    f"[bold magenta]🏆 Achievements unlocked: {len(unique_achievements)}[/bold magenta]"
                )
                for achievement in unique_achievements.values():
                    out.print(
                        f"[bold magenta]  • {achievement.icon} {achievement.name}[/bold magenta]"
                    )
                    out.print(
                        f"[dim]    {achievement.description} (+{achievement.bonus_points} bonus points)[/dim]"
                    )

        if failed_count > 0:
            out.print(
                f"[red]❌ Failed: {failed_count} todos could not be completed[/red]"
            )

    # Show streak and level info from the last completed todo (if any)
    if completed_count > 0 and len(todo_ids) > 1:
        # Get the latest scoring result to show streak/level info
        try:
            from ..core.scoring import ScoringService

            scoring_service = ScoringService(db)
            progress = scoring_service.get_user_progress()

            if progress["current_streak"] > 1:
                out.print(
                    f"[blue]🔥 Current streak: {progress['current_streak']} days[/blue]"
                )

            # Check if we leveled up (simplified check)
            if total_points > 0:  # Only show if we earned points
                out.print(
                    f"[cyan]⭐ Current level: {progress['level']} ({progress['points_to_next_level']} points to next level)[/cyan]"
                )
        except Exception:
            # Don't fail the whole command if we can't get progress info
            pass

    if json_out:
        unique_achievements = {a.name: a for a in all_achievements}
        _emit_json(
            {
                "completed": completed_ids,
                "failed": failed_ids,
                "points_earned": total_points,
                "achievements": [
                    {
                        "name": a.name,
                        "icon": a.icon,
                        "description": a.description,
                        "bonus_points": a.bonus_points,
                    }
                    for a in unique_achievements.values()
                ],
            }
        )


@app.command("delete")
@app.command("rm")
def delete_todo_cmd(
    todo_ids: list[int] = typer.Argument(..., help="One or more todo IDs to delete"),
    force: bool = typer.Option(
        False, "--force", "-f", help="Skip the confirmation prompt"
    ),
    json_out: bool = typer.Option(
        False, "--json", "-j", help="Emit result as JSON (machine-readable)"
    ),
) -> None:
    """Permanently delete one or more todos and their AI enrichment.

    Unlike 'done', this removes the todo entirely and awards no points.
    This cannot be undone.

    Examples:
        todo delete 42            # Delete a single todo (asks to confirm)
        todo rm 10 11 12 --force  # Delete several without confirming
    """
    _initialize_services()

    out = console_err if json_out else console

    # Deletion is irreversible. Require confirmation, or --force. JSON mode
    # cannot prompt, so it must pass --force explicitly.
    if not force:
        if json_out:
            _emit_json({"error": "Refusing to delete without --force in --json mode"})
            return
        plural = "s" if len(todo_ids) > 1 else ""
        if not typer.confirm(
            f"Permanently delete {len(todo_ids)} todo{plural}? This cannot be undone."
        ):
            console.print("[yellow]Aborted[/yellow]")
            return

    deleted: list[int] = []
    failed: list[int] = []
    for todo_id in todo_ids:
        try:
            if todo_repo.delete_todo(todo_id):
                deleted.append(todo_id)
                out.print(f"[green]🗑  Deleted todo {todo_id}[/green]")
            else:
                failed.append(todo_id)
                out.print(f"[red]✗ Todo {todo_id} not found[/red]")
        except Exception as e:
            failed.append(todo_id)
            out.print(f"[red]✗ Error deleting todo {todo_id}: {e}[/red]")

    if json_out:
        _emit_json({"deleted": deleted, "failed": failed})


@app.command("due")
def set_due(
    todo_id: int,
    when: str | None = typer.Argument(
        None, help="Due date, e.g. 'today', 'EOW', 'next monday', '6/11'"
    ),
    clear: bool = typer.Option(False, "--clear", help="Clear the due date"),
    json_out: bool = typer.Option(
        False, "--json", "-j", help="Emit result as JSON (machine-readable)"
    ),
) -> None:
    """Set or change a todo's due date.

    Examples:
        todo due 42 today
        todo due 42 "next monday"
        todo due 42 07/04/2026
        todo due 42 --clear        # remove the due date
    """
    _initialize_services()

    out = console_err if json_out else console

    todo = todo_repo.get_by_id(todo_id)
    if not todo:
        if json_out:
            _emit_json({"error": f"Todo {todo_id} not found"})
        else:
            out.print(f"[red]✗ Todo {todo_id} not found[/red]")
        return

    if clear:
        due_date = None
    elif when:
        try:
            due_date = parse_due_date(when)
        except ValueError as e:
            if json_out:
                _emit_json({"error": str(e)})
            else:
                out.print(f"[red]✗ {e}[/red]")
            return
    else:
        msg = "Provide a due date or use --clear"
        if json_out:
            _emit_json({"error": msg})
        else:
            out.print(f"[red]✗ {msg}[/red]")
        return

    todo_repo.update_todo(todo_id, {"due_date": due_date})
    updated = todo_repo.get_by_id(todo_id) or todo

    if json_out:
        _emit_json(_todo_to_dict(updated, ai_repo.get_latest_by_todo_id(todo_id)))
        return

    if due_date:
        console.print(f"[green]✓ Todo {todo_id} due {due_date.isoformat()}[/green]")
    else:
        console.print(f"[green]✓ Cleared due date for todo {todo_id}[/green]")


@app.command("show")
def show_todo(
    todo_id: int,
    json_out: bool = typer.Option(
        False, "--json", "-j", help="Emit todo as JSON (machine-readable)"
    ),
) -> None:
    """Show detailed information about a todo including AI enrichment."""
    _initialize_services()
    todo = todo_repo.get_by_id(todo_id)

    if not todo:
        if json_out:
            _emit_json({"error": f"Todo {todo_id} not found"})
        else:
            console.print(f"[red]✗ Todo {todo_id} not found[/red]")
        return

    if json_out:
        ai_enrichment = ai_repo.get_latest_by_todo_id(todo_id)
        payload = _todo_to_dict(todo, ai_enrichment)
        payload["enrichment"] = _enrichment_to_dict(ai_enrichment)
        _emit_json(payload)
        return

    console.print(f"\n[bold cyan]Task #{todo.id}[/bold cyan]")
    console.print(f"[white]{todo.title}[/white]")

    if todo.description:
        console.print(f"[dim]{todo.description}[/dim]")

    # Create info table
    info_table = Table(show_header=False, show_edge=False, padding=(0, 2))
    info_table.add_column("Field", style="cyan", width=12)
    info_table.add_column("Value", style="white")

    # Format status
    status_value = (
        todo.status.value if hasattr(todo.status, "value") else str(todo.status)
    )
    info_table.add_row("Status", status_value.title())

    # Format priority
    if todo.final_priority:
        priority_value = (
            todo.final_priority.value
            if hasattr(todo.final_priority, "value")
            else str(todo.final_priority)
        )
    else:
        priority_value = "Not set"
    info_table.add_row("Priority", str(priority_value))

    # Format size
    if todo.final_size:
        size_value = (
            todo.final_size.value
            if hasattr(todo.final_size, "value")
            else str(todo.final_size)
        )
    else:
        size_value = "Not set"
    info_table.add_row("Size", str(size_value))
    info_table.add_row("Created", todo.created_at.strftime("%Y-%m-%d %H:%M"))

    if todo.completed_at:
        info_table.add_row("Completed", todo.completed_at.strftime("%Y-%m-%d %H:%M"))

    if todo.completion_note:
        info_table.add_row("Note", todo.completion_note)

    if todo.total_points_earned:
        info_table.add_row("Points", str(todo.total_points_earned))

    console.print(info_table)

    # Show AI analysis if available
    ai_enrichment = ai_repo.get_latest_by_todo_id(todo_id)
    if ai_enrichment:
        console.print("\n[bold blue]🤖 AI Analysis[/bold blue]")
        _display_enrichment_results(ai_enrichment)
    else:
        console.print("\n[dim]No AI analysis available[/dim]")
        console.print("[dim]Use 'todo enrich <id>' to analyze with AI[/dim]")


@app.command("enrich")
def enrich_todo(
    todo_id: int,
    provider: str | None = typer.Option(
        None, "--provider", "-p", help="AI provider (openai/anthropic)"
    ),
) -> None:
    """Manually enrich a todo with AI analysis."""
    try:
        todo = todo_repo.get_by_id(todo_id)

        if not todo:
            console.print(f"[red]✗ Todo {todo_id} not found[/red]")
            return

        console.print(f"[blue]🤖 Analyzing task: {todo.title}...[/blue]")

        ai_provider = None
        if provider:
            try:
                ai_provider = AIProvider(provider)
            except ValueError:
                console.print(f"[red]✗ Invalid AI provider: {provider}[/red]")
                console.print("[dim]Available providers: openai, anthropic[/dim]")
                return

        # Get AI enrichment
        enrichment = asyncio.run(
            _enrich_todo_async(todo_id, todo.title, todo.description, ai_provider)
        )

        if enrichment:
            _display_enrichment_results(enrichment)
            console.print("\n[green]✓ AI analysis completed and saved[/green]")
        else:
            console.print("[red]✗ AI enrichment failed[/red]")

    except Exception as e:
        error_msg = str(e)
        if "todo" in error_msg.lower() and "not found" in error_msg.lower():
            console.print(f"[red]✗ Todo {todo_id} not found[/red]")
        else:
            console.print(f"[red]✗ Error enriching todo: {error_msg}[/red]")


@app.command("stats")
def show_stats(
    json_out: bool = typer.Option(
        False, "--json", "-j", help="Emit stats as JSON (machine-readable)"
    ),
) -> None:
    """Show user progress and statistics."""
    _initialize_services()

    from ..core.scoring import ScoringService

    try:
        scoring_service = ScoringService(db)
        progress = scoring_service.get_user_progress()

        if json_out:
            _emit_json(progress)
            return

        console.print("\n[bold cyan]📊 Your Progress[/bold cyan]")

        # Create stats table
        stats_table = Table(show_header=False, show_edge=False, padding=(0, 2))
        stats_table.add_column("Metric", style="cyan", width=20)
        stats_table.add_column("Value", style="white")

        stats_table.add_row("Level", f"⭐ {progress['level']}")
        stats_table.add_row("Total Points", f"🎯 {progress['total_points']}")
        stats_table.add_row(
            "Points to Next Level", f"📈 {progress['points_to_next_level']}"
        )
        stats_table.add_row("Current Streak", f"🔥 {progress['current_streak']} days")
        stats_table.add_row("Longest Streak", f"🏆 {progress['longest_streak']} days")
        stats_table.add_row("Tasks Completed", f"✅ {progress['total_completed']}")

        # Today's progress
        stats_table.add_row("", "")  # Spacer
        stats_table.add_row("Today's Tasks", f"📋 {progress['tasks_completed_today']}")
        stats_table.add_row("Daily Goal", f"🎯 {progress['daily_goal']}")
        stats_table.add_row("Today's Points", f"🎉 {progress['points_earned_today']}")

        goal_status = (
            "✅ Met"
            if progress["daily_goal_met"]
            else f"⏳ {progress['daily_goal'] - progress['tasks_completed_today']} more to go"
        )
        stats_table.add_row("Goal Status", goal_status)

        # Add achievement summary to stats
        from ..core.achievements import AchievementService

        achievement_service = AchievementService(db)
        user_stats = scoring_service.user_stats_repo.get_current_stats()
        if user_stats:
            achievement_summary = achievement_service.get_achievements_summary(
                user_stats
            )

            stats_table.add_row("", "")  # Spacer
            stats_table.add_row(
                "Achievements",
                f"🏆 {achievement_summary['total_unlocked']}/{achievement_summary['total_possible']} ({achievement_summary['completion_percentage']}%)",
            )

            if achievement_summary["next_milestone"]:
                milestone = achievement_summary["next_milestone"]
                stats_table.add_row(
                    "Next Milestone",
                    f"{milestone['icon']} {milestone['name']} ({milestone['percentage']:.1f}%)",
                )

        console.print(stats_table)

        # Progress bar for level
        if progress["points_to_next_level"] > 0:
            # Calculate progress within current level
            # For level 1: 0-99 points (need 100 total)
            # For level 2: 100-249 points (need 250 total), etc.
            scoring_service = ScoringService(db)
            current_level = progress["level"]
            total_points = progress["total_points"]

            # Get the points needed for current level and next level
            if current_level <= len(scoring_service.level_thresholds):
                current_level_threshold = (
                    scoring_service.level_thresholds[current_level - 1]
                    if current_level > 1
                    else 0
                )
                next_level_threshold = (
                    scoring_service.level_thresholds[current_level]
                    if current_level < len(scoring_service.level_thresholds)
                    else float("inf")
                )

                if next_level_threshold != float("inf"):
                    # Points earned toward this level
                    points_in_level = total_points - current_level_threshold
                    # Total points needed for this level
                    points_needed_for_level = (
                        next_level_threshold - current_level_threshold
                    )
                    # Progress percentage
                    progress_pct = (points_in_level / points_needed_for_level) * 100

                    from rich.progress import BarColumn, Progress, TextColumn

                    with Progress(
                        TextColumn("[bold blue]Level Progress"),
                        BarColumn(bar_width=30),
                        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                        console=console,
                    ) as progress_bar:
                        task = progress_bar.add_task("Level", total=100)
                        progress_bar.update(
                            task, completed=max(0, min(100, progress_pct))
                        )

    except Exception as e:
        if json_out:
            _emit_json({"error": str(e)})
        else:
            console.print(f"[red]✗ Error retrieving stats: {e}[/red]")


@app.command("dashboard")
def show_dashboard(
    days: int = typer.Option(30, "--days", "-d", help="Number of days to analyze"),
) -> None:
    """Show productivity dashboard with insights and analytics."""
    from rich.columns import Columns
    from rich.panel import Panel
    from rich.table import Table

    from ..core.analytics import AnalyticsService
    from ..core.goals import GoalService
    from ..core.scoring import ScoringService

    try:
        analytics_service = AnalyticsService(db)
        goal_service = GoalService(db)
        scoring_service = ScoringService(db)

        # Get current user stats
        user_stats = scoring_service.user_stats_repo.get_current_stats()
        if not user_stats:
            user_stats = scoring_service._initialize_user_stats()

        # Update goal progress
        goal_service.update_goal_progress(user_stats)

        console.print(
            f"\n[bold cyan]📊 Productivity Dashboard[/bold cyan] [dim]({days} days)[/dim]\n"
        )

        # Generate productivity report
        report = analytics_service.generate_productivity_report(days)

        # --- Left Column: Overview Stats ---
        overview_table = Table(show_header=False, box=None)
        overview_table.add_column("Metric", style="cyan")
        overview_table.add_column("Value", style="bold white")

        overview_table.add_row("📝 Tasks Completed", str(report["total_completed"]))
        overview_table.add_row(
            "📈 Completion Rate", f"{report['completion_rate']:.1f}%"
        )
        overview_table.add_row("🔥 Current Streak", f"{report['current_streak']} days")
        overview_table.add_row("⭐ Total Points", str(report["total_points"]))

        # Trend indicator
        trend_icon = (
            "📈"
            if report["trend"]["direction"] == "improving"
            else "📉"
            if report["trend"]["direction"] == "declining"
            else "➡️"
        )
        overview_table.add_row(
            "📊 Trend", f"{trend_icon} {report['trend']['direction']}"
        )

        overview_panel = Panel(overview_table, title="📋 Overview", border_style="blue")

        # --- Right Column: Goals Progress ---
        goals_summary = goal_service.get_goals_summary()

        if goals_summary["total_goals"] > 0:
            goals_table = Table(show_header=True, header_style="bold green")
            goals_table.add_column("Goal", style="white", width=15)
            goals_table.add_column("Progress", style="cyan", width=20)
            goals_table.add_column("Days Left", style="yellow", width=8)

            for goal_data in goals_summary["goals"]:
                # Progress bar representation
                progress_bar = "█" * int(goal_data["progress"] / 10) + "░" * (
                    10 - int(goal_data["progress"] / 10)
                )
                progress_text = f"{progress_bar} {goal_data['progress']:.0f}%"

                # Status icon
                status_icon = "✅" if goal_data["completed"] else "🎯"
                goal_name = (
                    f"{status_icon} {goal_data['category'].replace('_', ' ').title()}"
                )

                goals_table.add_row(
                    goal_name, progress_text, str(goal_data["days_remaining"])
                )

            goals_panel = Panel(
                goals_table,
                title=f"🎯 Goals ({goals_summary['completed_goals']}/{goals_summary['total_goals']})",
                border_style="green",
            )
        else:
            goals_panel = Panel(
                "[dim]No active goals set.\nUse 'todo goal create' to set goals![/dim]",
                title="🎯 Goals",
                border_style="green",
            )

        # Display overview and goals side by side
        console.print(Columns([overview_panel, goals_panel], equal=True))

        # --- Category Breakdown ---
        if report["category_breakdown"]:
            console.print("\n[bold cyan]📂 Category Breakdown[/bold cyan]")

            category_table = Table(show_header=True, header_style="bold magenta")
            category_table.add_column("Category", style="white", width=15)
            category_table.add_column("Tasks", style="cyan", width=8)
            category_table.add_column("Percentage", style="yellow", width=12)
            category_table.add_column("Distribution", style="magenta", width=20)

            for category_data in report["category_breakdown"]:
                # Visual bar for percentage
                bar_length = int(
                    category_data["percentage"] / 5
                )  # Scale to 20 chars max
                bar = "█" * bar_length + "░" * (20 - bar_length)

                category_table.add_row(
                    category_data["category"] or "Uncategorized",
                    str(category_data["count"]),
                    f"{category_data['percentage']:.1f}%",
                    bar,
                )

            console.print(category_table)

        # --- Weekly Summary ---
        weekly_summary = analytics_service.get_weekly_summary()
        console.print("\n[bold cyan]📅 This Week[/bold cyan]")

        weekly_table = Table(show_header=True, header_style="bold blue")
        weekly_table.add_column("Metric", style="white", width=20)
        weekly_table.add_column("This Week", style="bold cyan", width=12)
        weekly_table.add_column("Last Week", style="dim", width=12)
        weekly_table.add_column("Change", style="yellow", width=10)

        # Calculate changes
        def format_change(current, previous):
            if previous == 0:
                return "N/A" if current == 0 else "NEW"
            change = ((current - previous) / previous) * 100
            if change > 0:
                return f"+{change:.1f}%"
            elif change < 0:
                return f"{change:.1f}%"
            else:
                return "0%"

        weekly_table.add_row(
            "Tasks Completed",
            str(weekly_summary["current_week"]["completed_tasks"]),
            str(weekly_summary["previous_week"]["completed_tasks"]),
            format_change(
                weekly_summary["current_week"]["completed_tasks"],
                weekly_summary["previous_week"]["completed_tasks"],
            ),
        )

        weekly_table.add_row(
            "Points Earned",
            str(weekly_summary["current_week"]["points_earned"]),
            str(weekly_summary["previous_week"]["points_earned"]),
            format_change(
                weekly_summary["current_week"]["points_earned"],
                weekly_summary["previous_week"]["points_earned"],
            ),
        )

        weekly_table.add_row(
            "Active Days",
            str(weekly_summary["current_week"]["active_days"]),
            str(weekly_summary["previous_week"]["active_days"]),
            format_change(
                weekly_summary["current_week"]["active_days"],
                weekly_summary["previous_week"]["active_days"],
            ),
        )

        console.print(weekly_table)

        # --- Insights ---
        if report["insights"]:
            console.print("\n[bold cyan]💡 Insights & Recommendations[/bold cyan]")

            for _i, insight in enumerate(report["insights"], 1):
                icon = (
                    "🎯"
                    if "goal" in insight.lower()
                    else "💡"
                    if "tip" in insight.lower()
                    else "📈"
                )
                console.print(f"{icon} {insight}")

        # --- Goal Suggestions ---
        suggestions = goal_service.get_goal_suggestions(user_stats)
        if suggestions:
            console.print("\n[bold cyan]🎯 Suggested Goals[/bold cyan]")

            for i, suggestion in enumerate(suggestions, 1):
                difficulty_color = {
                    "easy": "green",
                    "moderate": "yellow",
                    "challenging": "red",
                }.get(suggestion["difficulty"], "white")

                console.print(
                    f"{i}. [{difficulty_color}]{suggestion['type'].value.title()}[/{difficulty_color}]: "
                    f"{suggestion['category'].value.replace('_', ' ').title()} - "
                    f"[bold]{suggestion['target_value']}[/bold]"
                )
                console.print(f"   [dim]{suggestion['reason']}[/dim]")

        console.print()

    except Exception as e:
        console.print(f"[red]✗ Error generating dashboard: {e}[/red]")


goal_app = typer.Typer(help="Goal management commands")


@goal_app.callback(invoke_without_command=True)
def goal_main(
    ctx: typer.Context,
) -> None:
    """Goal management - create, list, and track your productivity goals."""
    if ctx.invoked_subcommand is None:
        # Show helpful information when no subcommand is provided
        console.print("[bold cyan]🎯 Goal Management[/bold cyan]")
        console.print("\n[dim]Available commands:[/dim]")
        console.print("  [cyan]create[/cyan]  Create a new weekly or monthly goal")
        console.print("  [cyan]list[/cyan]    Show all current goals")
        console.print("  [cyan]delete[/cyan]  Delete a goal by ID")
        console.print("\n[dim]Examples:[/dim]")
        console.print("  [green]todo goal create weekly tasks_completed 10[/green]")
        console.print("  [green]todo goal list[/green]")
        console.print("  [green]todo goal delete 1[/green]")

        # Show current goals if any exist
        try:
            from ..core.goals import GoalService
            from ..db.repository import UserStatsRepository

            goal_service = GoalService(db)

            # Update goal progress before displaying
            user_stats_repo = UserStatsRepository(db)
            user_stats = user_stats_repo.get_current_stats()
            if user_stats:
                goal_service.update_goal_progress(user_stats)

            goals = goal_service.get_current_goals()

            if goals:
                console.print("\n[bold cyan]📋 Current Goals[/bold cyan]")
                from rich.table import Table

                table = Table(show_header=True, header_style="bold magenta")
                table.add_column("Goal", style="white", width=20)
                table.add_column("Progress", style="cyan", width=25)
                table.add_column("Status", style="yellow", width=12)
                table.add_column("Days Left", style="magenta", width=10)

                for goal in goals:
                    progress_bar = "█" * min(10, int(goal.progress_percentage / 10))
                    progress_bar += "░" * (10 - len(progress_bar))

                    status = "✅ Done" if goal.is_completed else "🎯 Active"

                    table.add_row(
                        f"{goal.type.value.title()} {goal.category.value.replace('_', ' ').title()}",
                        f"{progress_bar} {goal.current_value}/{goal.target_value} ({goal.progress_percentage:.0f}%)",
                        status,
                        str(goal.days_remaining),
                    )

                console.print(table)
            else:
                console.print("\n[dim]No active goals. Create one with:[/dim]")
                console.print(
                    "  [green]todo goal create weekly tasks_completed 10[/green]"
                )
        except Exception as e:
            console.print(f"[red]✗ Error loading goals: {e}[/red]")


@goal_app.command("create")
def create_goal(
    goal_type: str = typer.Argument(..., help="Goal type: weekly or monthly"),
    category: str = typer.Argument(
        ...,
        help="Category: tasks_completed, points_earned, streak_days, productivity_score",
    ),
    target: int = typer.Argument(..., help="Target value to achieve"),
) -> None:
    """Create a new goal."""
    from ..core.goals import GoalCategory, GoalService, GoalType

    try:
        goal_service = GoalService(db)

        # Validate inputs
        try:
            goal_type_enum = GoalType(goal_type.lower())
        except ValueError:
            console.print(
                f"[red]✗ Invalid goal type: {goal_type}. Use 'weekly' or 'monthly'[/red]"
            )
            return

        try:
            category_enum = GoalCategory(category.lower())
        except ValueError:
            console.print(
                f"[red]✗ Invalid category: {category}. Use 'tasks_completed', 'points_earned', 'streak_days', or 'productivity_score'[/red]"
            )
            return

        if target <= 0:
            console.print("[red]✗ Target must be a positive number[/red]")
            return

        # Create the goal
        goal = goal_service.create_goal(goal_type_enum, category_enum, target)

        console.print(
            f"[green]✅ Created {goal_type} goal:[/green] "
            f"{category.replace('_', ' ').title()} - {target}"
        )
        console.print(
            f"[dim]Period: {goal.period_start} to {goal.period_end} ({goal.days_remaining} days remaining)[/dim]"
        )

    except Exception as e:
        console.print(f"[red]✗ Error creating goal: {e}[/red]")


@goal_app.command("list")
def list_goals() -> None:
    """List all current goals."""
    from ..core.goals import GoalService
    from ..db.repository import UserStatsRepository

    try:
        goal_service = GoalService(db)

        # Update goal progress before displaying
        user_stats_repo = UserStatsRepository(db)
        user_stats = user_stats_repo.get_current_stats()
        if user_stats:
            goal_service.update_goal_progress(user_stats)

        goals = goal_service.get_current_goals()

        if not goals:
            console.print(
                "[yellow]No active goals found. Create one with 'todo goal create'![/yellow]"
            )
            return

        console.print("\n[bold cyan]🎯 Current Goals[/bold cyan]\n")

        goals_table = Table(show_header=True, header_style="bold green")
        goals_table.add_column("Goal", style="white", width=20)
        goals_table.add_column("Progress", style="cyan", width=25)
        goals_table.add_column("Status", style="yellow", width=10)
        goals_table.add_column("Days Left", style="magenta", width=10)

        for goal in goals:
            # Goal name
            goal_name = f"{goal.type.value.title()} {goal.category.value.replace('_', ' ').title()}"

            # Progress bar and text
            progress_bar = "█" * int(goal.progress_percentage / 10) + "░" * (
                10 - int(goal.progress_percentage / 10)
            )
            progress_text = f"{progress_bar} {goal.current_value}/{goal.target_value} ({goal.progress_percentage:.0f}%)"

            # Status
            status = "✅ Done" if goal.is_completed else "🎯 Active"

            goals_table.add_row(
                goal_name, progress_text, status, str(goal.days_remaining)
            )

        console.print(goals_table)
        console.print()

    except Exception as e:
        console.print(f"[red]✗ Error listing goals: {e}[/red]")


@goal_app.command("delete")
def delete_goal(goal_id: int = typer.Argument(..., help="Goal ID to delete")) -> None:
    """Delete a goal by ID."""
    from ..core.goals import GoalService

    try:
        goal_service = GoalService(db)

        if goal_service.delete_goal(goal_id):
            console.print(f"[green]✅ Deleted goal {goal_id}[/green]")
        else:
            console.print(f"[red]✗ Goal {goal_id} not found[/red]")

    except Exception as e:
        console.print(f"[red]✗ Error deleting goal: {e}[/red]")


app.add_typer(goal_app, name="goal")


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------
event_app = typer.Typer(help="Calendar event management")


def _emit_error(out, json_out: bool, message: str) -> None:
    """Report an error to stderr/console, and as JSON when in --json mode."""
    out.print(f"[red]✗ {message}[/red]")
    if json_out:
        _emit_json({"error": message})


@event_app.command("add")
def event_add(
    text: str,
    when: str | None = typer.Option(
        None, "--when", "-w", help="Date/time for flag mode, e.g. '2026-06-12 19:00'"
    ),
    duration: int | None = typer.Option(None, "--duration", help="Duration in minutes"),
    end: str | None = typer.Option(None, "--end", help="Explicit end date/time"),
    location: str | None = typer.Option(None, "--location", "-L"),
    description: str | None = typer.Option(None, "--desc", "-d"),
    invite: str | None = typer.Option(
        None, "--invite", "-i", help="Comma-separated aliases/emails to invite"
    ),
    no_ai: bool = typer.Option(False, "--no-ai", help="Skip AI parsing; use flags"),
    no_sync: bool = typer.Option(
        False, "--no-sync", help="Don't push to Google Calendar"
    ),
    json_out: bool = typer.Option(
        False, "--json", "-j", help="Emit result as JSON (machine-readable)"
    ),
) -> None:
    """Add a calendar event from natural language or explicit flags.

    Examples:
        todo event add "dinner with parents friday 7pm, invite wife and kids"
        todo event add "Dinner" --when "2026-06-12 19:00" --invite wife,kids --no-ai
    """
    _initialize_services()
    out = console_err if json_out else console

    title = text.strip()
    end_at = None
    all_day = False
    attendee_tokens: list[str] = []

    if no_ai or when:
        # Flag mode.
        if not when:
            _emit_error(out, json_out, "Flag mode needs --when (or use AI parsing)")
            return
        try:
            start_at = parse_datetime(when)
            if end:
                end_at = parse_datetime(end)
        except ValueError as e:
            _emit_error(out, json_out, str(e))
            return
        if invite:
            attendee_tokens = [t.strip() for t in invite.split(",") if t.strip()]
    else:
        # AI mode: the model extracts raw phrases; we resolve dates ourselves.
        draft = asyncio.run(event_parser.parse(text, datetime.now()))
        if not draft:
            _emit_error(out, json_out, "AI parsing failed — add manually with --when")
            return
        title = draft.title
        try:
            day = (
                parse_due_date(draft.date_phrase) if draft.date_phrase else date.today()
            )
        except ValueError:
            _emit_error(out, json_out, f"Could not understand the date in: {text!r}")
            return

        if draft.time:
            try:
                start_at = datetime.combine(day, parse_datetime(draft.time).time())
            except ValueError:
                start_at = datetime.combine(day, dt_time(0, 0))
                all_day = True
        else:
            start_at = datetime.combine(day, dt_time(0, 0))
            all_day = True

        if draft.end_time:
            try:
                end_at = datetime.combine(day, parse_datetime(draft.end_time).time())
            except ValueError:
                end_at = None
        elif draft.duration_minutes:
            end_at = start_at + timedelta(minutes=draft.duration_minutes)

        location = location or draft.location
        attendee_tokens = draft.attendees

    if duration and not end_at:
        end_at = start_at + timedelta(minutes=duration)

    event = event_repo.create_event(
        title,
        start_at,
        end_at=end_at,
        description=description,
        location=location,
        all_day=all_day,
    )

    emails = contact_repo.resolve(attendee_tokens) if attendee_tokens else []
    if emails:
        event_repo.set_attendees(event.id, emails)
        event.attendees = emails

    # Push to Google Calendar (best-effort) unless --no-sync.
    sync_error = None
    if no_sync:
        sync_error = "skipped"
    elif not gcal_client.is_authenticated():
        sync_error = "not-authenticated"
    else:
        sync_error = _push_event_to_google(event)

    if json_out:
        _emit_json(_event_to_dict(event))
        return

    console.print(f"[green]✓ Event:[/green] {event.title}")
    console.print(
        f"[dim]ID {event.id} · {event.start_at.strftime('%Y-%m-%d %H:%M')}[/dim]"
    )
    if event.location:
        console.print(f"[dim]Where: {event.location}[/dim]")
    if emails:
        console.print(f"[dim]Invitees: {', '.join(emails)}[/dim]")
    if event.is_synced:
        console.print("[dim]✓ Synced to Google Calendar[/dim]")
    elif sync_error == "not-authenticated":
        console.print(
            "[dim]Local only — run 'todo calendar auth' to sync to Google.[/dim]"
        )
    elif sync_error and sync_error != "skipped":
        console.print(f"[yellow]⚠ Not synced: {sync_error}[/yellow]")


@event_app.command("ls")
@event_app.command("list")
def event_list(
    all_events: bool = typer.Option(
        False, "--all", "-a", help="Include past and cancelled events"
    ),
    limit: int = typer.Option(20, "--limit", "-l"),
    json_out: bool = typer.Option(False, "--json", "-j", help="Emit events as JSON"),
) -> None:
    """List upcoming events (or all with --all)."""
    _initialize_services()

    events = event_repo.list_events(
        upcoming_only=not all_events,
        include_cancelled=all_events,
        limit=limit,
    )

    if json_out:
        _emit_json({"events": [_event_to_dict(e) for e in events]})
        return

    if not events:
        console.print("[yellow]No events found[/yellow]")
        console.print("[dim]Add one with 'todo event add <text>'[/dim]")
        return

    table = Table(title="📅 Events", show_header=True, header_style="bold blue")
    table.add_column("ID", style="cyan", width=3)
    table.add_column("Event", style="white")
    table.add_column("When", style="green")
    table.add_column("Where", style="blue")
    table.add_column("Invitees", style="magenta")
    table.add_column("Sync", style="yellow", width=4)

    for event in events:
        when = (
            event.start_at.strftime("%Y-%m-%d")
            if event.all_day
            else event.start_at.strftime("%Y-%m-%d %H:%M")
        )
        title = event.title
        if event.status.value == "cancelled":
            title = f"[strike]{title}[/strike]"
        table.add_row(
            str(event.id),
            title,
            when,
            event.location or "—",
            str(len(event.attendees)) if event.attendees else "—",
            "✓" if event.is_synced else "○",
        )

    console.print(table)


@event_app.command("show")
def event_show(
    event_id: int,
    json_out: bool = typer.Option(False, "--json", "-j"),
) -> None:
    """Show details for one event."""
    _initialize_services()

    event = event_repo.get_by_id(event_id)
    if not event:
        _emit_error(
            console_err if json_out else console,
            json_out,
            f"Event {event_id} not found",
        )
        return

    if json_out:
        _emit_json(_event_to_dict(event))
        return

    console.print(f"\n[bold cyan]Event #{event.id}[/bold cyan]")
    console.print(f"[white]{event.title}[/white]")
    if event.description:
        console.print(f"[dim]{event.description}[/dim]")
    info = Table(show_header=False, show_edge=False, padding=(0, 2))
    info.add_column("Field", style="cyan", width=12)
    info.add_column("Value", style="white")
    when = (
        event.start_at.strftime("%Y-%m-%d")
        if event.all_day
        else event.start_at.strftime("%Y-%m-%d %H:%M")
    )
    info.add_row("When", when)
    if event.end_at:
        info.add_row("Ends", event.end_at.strftime("%Y-%m-%d %H:%M"))
    info.add_row("Status", event.status.value.title())
    if event.location:
        info.add_row("Where", event.location)
    if event.attendees:
        info.add_row("Invitees", ", ".join(event.attendees))
    info.add_row("Synced", "Yes" if event.is_synced else "No")
    console.print(info)


@event_app.command("cancel")
def event_cancel(
    event_id: int,
    json_out: bool = typer.Option(False, "--json", "-j"),
) -> None:
    """Mark an event cancelled (kept in history; excluded from the default list)."""
    _initialize_services()

    event = event_repo.cancel_event(event_id)
    if not event:
        _emit_error(
            console_err if json_out else console,
            json_out,
            f"Event {event_id} not found",
        )
        return

    # Remove from Google Calendar if it was synced.
    if event.google_event_id:
        _remove_event_from_google(event.google_event_id)
        event_repo.set_google_ids(event_id, None, None)
        event.google_event_id = None
        event.google_calendar_id = None

    if json_out:
        _emit_json(_event_to_dict(event))
        return
    console.print(f"[green]✓ Cancelled event {event_id}:[/green] {event.title}")


@event_app.command("delete")
@event_app.command("rm")
def event_delete(
    event_id: int,
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    json_out: bool = typer.Option(False, "--json", "-j"),
) -> None:
    """Permanently delete an event (and its attendees). Cannot be undone."""
    _initialize_services()
    out = console_err if json_out else console

    if not force:
        if json_out:
            _emit_json({"error": "Refusing to delete without --force in --json mode"})
            return
        if not typer.confirm(f"Permanently delete event {event_id}?"):
            console.print("[yellow]Aborted[/yellow]")
            return

    existing = event_repo.get_by_id(event_id)
    deleted = event_repo.delete_event(event_id)
    if deleted and existing and existing.google_event_id:
        _remove_event_from_google(existing.google_event_id)
    if json_out:
        _emit_json({"deleted": event_id if deleted else None, "found": deleted})
        return
    if deleted:
        console.print(f"[green]🗑  Deleted event {event_id}[/green]")
    else:
        out.print(f"[red]✗ Event {event_id} not found[/red]")


@event_app.command("sync")
def event_sync(
    event_id: int | None = typer.Argument(
        None, help="Sync one event; omit to sync all unsynced"
    ),
    json_out: bool = typer.Option(False, "--json", "-j"),
) -> None:
    """Push unsynced events to Google Calendar."""
    _initialize_services()
    out = console_err if json_out else console

    if not gcal_client.is_authenticated():
        _emit_error(out, json_out, "Not authenticated — run 'todo calendar auth' first")
        return

    if event_id is not None:
        ev = event_repo.get_by_id(event_id)
        if not ev:
            _emit_error(out, json_out, f"Event {event_id} not found")
            return
        targets = [ev]
    else:
        targets = event_repo.get_unsynced()

    synced: list[int] = []
    failed: list[int] = []
    for ev in targets:
        if ev.is_synced:
            continue
        err = _push_event_to_google(ev)
        if err:
            failed.append(ev.id)
            if not json_out:
                out.print(f"[yellow]⚠ {ev.id}: {err}[/yellow]")
        else:
            synced.append(ev.id)

    if json_out:
        _emit_json({"synced": synced, "failed": failed})
        return
    console.print(f"[green]✓ Synced {len(synced)} event(s)[/green]")
    if failed:
        console.print(f"[red]✗ {len(failed)} failed[/red]")


app.add_typer(event_app, name="event")


# ---------------------------------------------------------------------------
# Google Calendar
# ---------------------------------------------------------------------------
calendar_app = typer.Typer(help="Google Calendar integration")


@calendar_app.command("auth")
def calendar_auth(
    no_browser: bool = typer.Option(
        False, "--no-browser", help="Don't open a browser (print the URL instead)"
    ),
    json_out: bool = typer.Option(False, "--json", "-j"),
) -> None:
    """Authenticate with Google Calendar (one-time OAuth).

    Prerequisite: a Google Cloud OAuth client. Create a project, enable the
    Google Calendar API, create an OAuth client (Desktop app), download
    credentials.json, and save it to ~/.config/todo/gcal_credentials.json.
    """
    _initialize_services()
    out = console_err if json_out else console

    if not gcal_client.has_credentials():
        _emit_error(
            out,
            json_out,
            f"No OAuth credentials at {gcal_client.credentials_path}. Save your "
            "downloaded credentials.json there, then re-run.",
        )
        return

    try:
        gcal_client.authenticate(open_browser=not no_browser)
    except CalendarAuthError as e:
        _emit_error(out, json_out, str(e))
        return

    if json_out:
        _emit_json(
            {
                "authenticated": True,
                "token_path": str(gcal_client.token_path),
                "calendar_id": gcal_client.calendar_id,
            }
        )
        return
    console.print("[green]✓ Authenticated with Google Calendar[/green]")
    console.print(f"[dim]Token saved to {gcal_client.token_path}[/dim]")


@calendar_app.command("status")
def calendar_status(
    json_out: bool = typer.Option(False, "--json", "-j"),
) -> None:
    """Show Google Calendar auth status."""
    _initialize_services()

    status = {
        "has_credentials": gcal_client.has_credentials(),
        "authenticated": gcal_client.is_authenticated(),
        "credentials_path": str(gcal_client.credentials_path),
        "token_path": str(gcal_client.token_path),
        "calendar_id": gcal_client.calendar_id,
    }
    if json_out:
        _emit_json(status)
        return
    creds = "✓" if status["has_credentials"] else "✗ missing"
    console.print(f"Credentials: {creds} ({status['credentials_path']})")
    console.print(
        "Authenticated: "
        + ("✓" if status["authenticated"] else "✗ — run: todo calendar auth")
    )
    console.print(f"Calendar: {status['calendar_id']}")


app.add_typer(calendar_app, name="calendar")


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------
contact_app = typer.Typer(help="Contact aliases for event invites")


@contact_app.command("add")
def contact_add(
    alias: str,
    emails: list[str] = typer.Argument(..., help="One or more emails for this alias"),
    json_out: bool = typer.Option(False, "--json", "-j"),
) -> None:
    """Map an alias to one or more emails (e.g. 'contact add kids a@x.com b@x.com')."""
    _initialize_services()

    for email in emails:
        contact_repo.add_contact(alias, email)
    all_emails = contact_repo.get_emails(alias)

    if json_out:
        _emit_json({"alias": alias.lower(), "emails": all_emails})
        return
    console.print(f"[green]✓ {alias.lower()}[/green] → {', '.join(all_emails)}")


@contact_app.command("ls")
@contact_app.command("list")
def contact_list(
    json_out: bool = typer.Option(False, "--json", "-j"),
) -> None:
    """List all contact aliases and their emails."""
    _initialize_services()

    contacts = contact_repo.list_contacts()
    if json_out:
        _emit_json({"contacts": contacts})
        return
    if not contacts:
        console.print("[yellow]No contacts[/yellow]")
        console.print("[dim]Add one with 'todo contact add <alias> <email>'[/dim]")
        return
    table = Table(title="👥 Contacts", show_header=True, header_style="bold blue")
    table.add_column("Alias", style="cyan")
    table.add_column("Emails", style="white")
    for alias, emails in contacts.items():
        table.add_row(alias, ", ".join(emails))
    console.print(table)


@contact_app.command("rm")
@contact_app.command("delete")
def contact_remove(
    alias: str,
    json_out: bool = typer.Option(False, "--json", "-j"),
) -> None:
    """Remove an alias and all its email mappings."""
    _initialize_services()

    removed = contact_repo.remove_alias(alias)
    if json_out:
        _emit_json({"alias": alias.lower(), "removed": removed})
        return
    if removed:
        console.print(f"[green]✓ Removed {alias.lower()} ({removed} email(s))[/green]")
    else:
        console.print(f"[yellow]No contact alias '{alias.lower()}'[/yellow]")


app.add_typer(contact_app, name="contact")


@app.command("achievements")
def show_achievements(
    unlocked: bool = typer.Option(
        False, "--unlocked", "-u", help="Show only unlocked achievements"
    ),
    progress: bool = typer.Option(
        False, "--progress", "-p", help="Show progress toward locked achievements"
    ),
) -> None:
    """Show achievements and progress."""
    _initialize_services()

    from rich.progress import BarColumn, Progress, TextColumn
    from rich.table import Table

    from ..core.achievements import AchievementService
    from ..core.scoring import ScoringService

    try:
        achievement_service = AchievementService(db)
        scoring_service = ScoringService(db)

        # Get current user stats
        user_stats = scoring_service.user_stats_repo.get_current_stats()
        if not user_stats:
            user_stats = scoring_service._initialize_user_stats()

        # Get achievement progress and summary
        achievement_progress = achievement_service.get_achievement_progress(user_stats)
        summary = achievement_service.get_achievements_summary(user_stats)

        # Show summary
        console.print("\n[bold cyan]🏆 Achievement Progress[/bold cyan]")
        console.print(
            f"[green]{summary['total_unlocked']}[/green] of [cyan]{summary['total_possible']}[/cyan] unlocked ([yellow]{summary['completion_percentage']}%[/yellow])"
        )

        if summary["recent_unlocks"] > 0:
            console.print(f"[dim]{summary['recent_unlocks']} unlocked recently[/dim]")

        # Show next milestone
        if summary["next_milestone"]:
            milestone = summary["next_milestone"]
            console.print(
                f"[dim]Next milestone: {milestone['icon']} {milestone['name']} ({milestone['percentage']:.1f}%)[/dim]"
            )

        console.print()

        # Filter achievements based on options
        if unlocked:
            filtered_achievements = {
                name: data
                for name, data in achievement_progress.items()
                if data["unlocked"]
            }
            table_title = "🏆 Unlocked Achievements"
        elif progress:
            filtered_achievements = {
                name: data
                for name, data in achievement_progress.items()
                if not data["unlocked"] and data["current"] > 0
            }
            table_title = "📊 Achievement Progress"
        else:
            filtered_achievements = achievement_progress
            table_title = "🏆 All Achievements"

        # Create achievements table
        table = Table(title=table_title, show_header=True, header_style="bold blue")
        table.add_column("Achievement", style="white", width=25)
        table.add_column("Description", style="dim", width=40)
        table.add_column("Progress", style="cyan", width=15)
        table.add_column("Reward", style="yellow", width=10)

        # Sort achievements by completion status and progress
        sorted_achievements = sorted(
            filtered_achievements.items(),
            key=lambda x: (not x[1]["unlocked"], -x[1]["percentage"], x[0]),
        )

        for name, data in sorted_achievements:
            # Status indicator
            if data["unlocked"]:
                status = f"[green]✅ {data['icon']} {name}[/green]"
                progress_text = "[green]UNLOCKED[/green]"
            else:
                status = f"[dim]{data['icon']} {name}[/dim]"
                if data["current"] == 0:
                    progress_text = f"[dim]0/{data['required']}[/dim]"
                else:
                    progress_text = f"[cyan]{data['current']}[/cyan]/[white]{data['required']}[/white] ([yellow]{data['percentage']:.1f}%[/yellow])"

            # Bonus points
            bonus_text = (
                f"+{data['bonus_points']} pts" if data["bonus_points"] > 0 else "-"
            )

            table.add_row(status, data["description"], progress_text, bonus_text)

        console.print(table)

        # Show progress bars for achievements in progress (if --progress flag)
        if progress and filtered_achievements:
            console.print("\n[bold]Progress Details:[/bold]")

            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(bar_width=20),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                console=console,
            ) as progress_bar:
                for name, data in sorted_achievements[:5]:  # Show top 5 in progress
                    if not data["unlocked"] and data["current"] > 0:
                        task = progress_bar.add_task(
                            f"{data['icon']} {name}", total=100
                        )
                        progress_bar.update(task, completed=data["percentage"])

    except Exception as e:
        console.print(f"[red]✗ Error retrieving achievements: {e}[/red]")


@app.command("db")
def database_info() -> None:
    """Show database status and information."""
    status = migration_manager.get_migration_status()

    console.print("\n[bold cyan]💾 Database Status[/bold cyan]")

    # Create info table
    info_table = Table(show_header=False, show_edge=False, padding=(0, 2))
    info_table.add_column("Field", style="cyan", width=15)
    info_table.add_column("Value", style="white")

    info_table.add_row("Database Path", config.database.database_path)
    info_table.add_row("Schema Version", str(status["current_version"]))
    info_table.add_row(
        "Initialized", "✓ Yes" if status["schema_initialized"] else "✗ No"
    )
    info_table.add_row("Tables", str(len(status.get("tables", []))))

    console.print(info_table)

    if status.get("applied_migrations"):
        console.print("\n[bold]Applied Migrations:[/bold]")
        for migration in status["applied_migrations"]:
            console.print(f"  • v{migration['version']}: {migration['name']}")


if __name__ == "__main__":
    app()
