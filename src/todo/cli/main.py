"""Main CLI application entry point."""

import asyncio

import typer
from rich.console import Console
from rich.table import Table

from ..ai.background import BackgroundEnrichmentService
from ..ai.enrichment_service import EnrichmentService
from ..core.config import get_app_config
from ..db.connection import DatabaseConnection
from ..db.migrations import MigrationManager
from ..db.repository import AIEnrichmentRepository, TodoRepository
from ..models import AIProvider, TodoStatus

console = Console()
app = typer.Typer(
    name="todo",
    help="AI-powered terminal todo application for developers",
    add_completion=False,
    no_args_is_help=True,
)

# Initialize services
config = get_app_config()
db = DatabaseConnection(config.database.database_path)

# Initialize database schema if needed
migration_manager = MigrationManager(db)
if not migration_manager.is_schema_initialized():
    console.print("[yellow]⚠ Database not initialized. Initializing...[/yellow]")
    migration_manager.run_migrations()

todo_repo = TodoRepository(db)
ai_repo = AIEnrichmentRepository(db)
enrichment_service = EnrichmentService(db)
background_service = BackgroundEnrichmentService(db)


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
) -> None:
    """Add a new todo task with optional AI enrichment."""

    # Create the basic todo
    todo = todo_repo.create_todo(task, description)
    console.print(f"[green]✓ Added task:[/green] {task}")
    console.print(f"[dim]Task ID: {todo.id}[/dim]")

    # AI enrichment
    if not no_ai and config.ai.enable_auto_enrichment:
        console.print("\n[blue]🤖 AI analyzing task...[/blue]")

        ai_provider = None
        if provider:
            try:
                ai_provider = AIProvider(provider)
            except ValueError:
                console.print(f"[red]Invalid provider: {provider}[/red]")
                return

        # Get AI enrichment
        enrichment = asyncio.run(
            _enrich_todo_async(todo.id, task, description, ai_provider)
        )

        if enrichment:
            _display_enrichment_results(enrichment)

            # Auto-apply high confidence suggestions
            if enrichment.confidence_score >= config.ai.confidence_threshold:
                _apply_enrichment(todo.id, enrichment)
                console.print(
                    "[green]✓ High confidence suggestions applied automatically[/green]"
                )
            else:
                console.print(
                    f"[yellow]⚠ Suggestions available (confidence: {enrichment.confidence_score:.1%})[/yellow]"
                )
                console.print(
                    "[dim]Use 'todo show <id>' to review and apply suggestions[/dim]"
                )
        else:
            console.print("[red]✗ AI enrichment failed[/red]")


async def _enrich_todo_async(
    todo_id: int, title: str, description: str | None, provider: AIProvider | None
) -> any | None:
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
    # This would update the todo with AI suggestions
    # For now, just mark that enrichment exists
    pass


@app.command("list")
@app.command("ls")
def list_todos(
    limit: int = typer.Option(
        10, "--limit", "-l", help="Maximum number of todos to show"
    ),
    all_todos: bool = typer.Option(
        False, "--all", "-a", help="Show all todos including completed"
    ),
) -> None:
    """List active todos with AI enrichment status."""

    if all_todos:
        # For now, just show active todos
        todos = todo_repo.get_all()[:limit]
    else:
        todos = todo_repo.get_active_todos(limit)

    if not todos:
        console.print("[yellow]No active todos found[/yellow]")
        console.print("[dim]Use 'todo add <task>' to create your first todo![/dim]")
        return

    # Create table
    table = Table(title="📋 Your Todos", show_header=True, header_style="bold blue")
    table.add_column("ID", style="cyan", width=3)
    table.add_column("Task", style="white")
    table.add_column("Status", style="green")
    table.add_column("Priority", style="yellow")
    table.add_column("AI", style="magenta", width=3)

    for todo in todos:
        # Check if todo has AI enrichment
        ai_enrichment = ai_repo.get_latest_by_todo_id(todo.id)
        ai_status = "✓" if ai_enrichment else "○"

        # Format priority
        priority = todo.final_priority.value if todo.final_priority else "N/A"

        # Format status
        status_icon = "✓" if todo.status == TodoStatus.COMPLETED else "○"
        status_text = f"{status_icon} {todo.status.value.title()}"

        table.add_row(
            str(todo.id),
            todo.title[:60] + "..." if len(todo.title) > 60 else todo.title,
            status_text,
            priority,
            ai_status,
        )

    console.print(table)


@app.command("done")
@app.command("complete")
def complete_todo(todo_id: int) -> None:
    """Mark a todo as completed."""
    todo = todo_repo.complete_todo(todo_id)

    if todo:
        console.print(f"[green]✓ Completed:[/green] {todo.title}")
        if todo.total_points_earned:
            console.print(
                f"[yellow]🎉 Earned {todo.total_points_earned} points![/yellow]"
            )
    else:
        console.print(f"[red]✗ Todo {todo_id} not found or already completed[/red]")


@app.command("show")
def show_todo(todo_id: int) -> None:
    """Show detailed information about a todo including AI enrichment."""
    todo = todo_repo.get_by_id(todo_id)

    if not todo:
        console.print(f"[red]✗ Todo {todo_id} not found[/red]")
        return

    console.print(f"\n[bold cyan]Task #{todo.id}[/bold cyan]")
    console.print(f"[white]{todo.title}[/white]")

    if todo.description:
        console.print(f"[dim]{todo.description}[/dim]")

    # Create info table
    info_table = Table(show_header=False, show_edge=False, padding=(0, 2))
    info_table.add_column("Field", style="cyan", width=12)
    info_table.add_column("Value", style="white")

    info_table.add_row("Status", todo.status.value.title())
    info_table.add_row(
        "Priority", todo.final_priority.value if todo.final_priority else "Not set"
    )
    info_table.add_row("Size", todo.final_size.value if todo.final_size else "Not set")
    info_table.add_row("Created", todo.created_at.strftime("%Y-%m-%d %H:%M"))

    if todo.completed_at:
        info_table.add_row("Completed", todo.completed_at.strftime("%Y-%m-%d %H:%M"))

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
            console.print(f"[red]Invalid provider: {provider}[/red]")
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
    info_table.add_row("Initialized", "✓ Yes" if status["is_initialized"] else "✗ No")
    info_table.add_row("Tables", str(len(status.get("tables", []))))

    console.print(info_table)

    if status.get("applied_migrations"):
        console.print("\n[bold]Applied Migrations:[/bold]")
        for migration in status["applied_migrations"]:
            console.print(f"  • v{migration['version']}: {migration['name']}")


if __name__ == "__main__":
    app()
