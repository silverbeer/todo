"""Main CLI application entry point."""

import asyncio
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from ..ai.background import BackgroundEnrichmentService
from ..ai.enrichment_service import EnrichmentService
from ..core.config import get_app_config
from ..db.connection import DatabaseConnection
from ..db.migrations import MigrationManager
from ..db.repository import AIEnrichmentRepository, TodoRepository
from ..models import AIProvider

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

    # Validate input
    if not task or not task.strip():
        console.print("[red]✗ Task title cannot be empty[/red]")
        return

    # Create the basic todo
    try:
        todo = todo_repo.create_todo(task.strip(), description)
        console.print(f"[green]✓ Added task:[/green] {task.strip()}")
        console.print(f"[dim]Task ID: {todo.id}[/dim]")
    except Exception as e:
        error_msg = str(e)
        if "string_too_short" in error_msg or "at least 1 character" in error_msg:
            console.print("[red]✗ Task title cannot be empty[/red]")
        else:
            console.print(f"[red]✗ Error creating task: {error_msg}[/red]")
        return

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
) -> None:
    """List active todos with AI enrichment status."""

    try:
        if all_todos:
            # For now, just show active todos
            todos = todo_repo.get_all()[:limit]
        else:
            todos = todo_repo.get_active_todos(limit)
    except Exception as e:
        error_msg = str(e)
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

        table.add_row(
            str(todo.id),
            todo.title[:60] + "..." if len(todo.title) > 60 else todo.title,
            category[:10],  # Truncate category to fit column width
            status_text,
            priority,
            ai_status,
        )

    console.print(table)


@app.command("done")
@app.command("complete")
def complete_todo(todo_id: int) -> None:
    """Mark a todo as completed."""
    try:
        todo = todo_repo.complete_todo(todo_id)

        if todo:
            console.print(f"[green]✓ Completed:[/green] {todo.title}")

            # Display gamification results
            if hasattr(todo, "scoring_result") and todo.scoring_result:
                scoring = todo.scoring_result

                # Points breakdown
                if scoring["bonus_points"] > 0:
                    console.print(
                        f"[yellow]🎉 Earned {scoring['total_points']} points! "
                        f"({scoring['base_points']} base + {scoring['bonus_points']} bonus)[/yellow]"
                    )
                else:
                    console.print(
                        f"[yellow]🎉 Earned {scoring['total_points']} points![/yellow]"
                    )

                # Streak information
                if scoring["new_streak"] > 1:
                    console.print(
                        f"[blue]🔥 {scoring['new_streak']}-day streak![/blue]"
                    )

                # Level up notification
                if scoring["level_up"]:
                    console.print(
                        f"[magenta]⭐ Level up! You're now level {scoring['new_level']}![/magenta]"
                    )

                # Daily goal achievement
                if scoring["daily_goal_met"]:
                    console.print("[green]🎯 Daily goal achieved![/green]")

                # Achievement unlocks
                if scoring.get("achievements_unlocked"):
                    for achievement in scoring["achievements_unlocked"]:
                        console.print(
                            f"[bold magenta]🏆 Achievement Unlocked: {achievement.icon} {achievement.name}![/bold magenta]"
                        )
                        console.print(
                            f"[dim]{achievement.description} (+{achievement.bonus_points} bonus points)[/dim]"
                        )

            elif todo.total_points_earned:
                # Fallback for basic points display
                console.print(
                    f"[yellow]🎉 Earned {todo.total_points_earned} points![/yellow]"
                )
        else:
            console.print(f"[red]✗ Todo {todo_id} not found or already completed[/red]")
    except Exception as e:
        error_msg = str(e)
        if "foreign key constraint" in error_msg.lower():
            console.print(
                f"[red]✗ Cannot complete todo {todo_id}: This todo has related data that must be cleaned up first[/red]"
            )
        elif "not found" in error_msg.lower():
            console.print(f"[red]✗ Todo {todo_id} not found[/red]")
        else:
            console.print(f"[red]✗ Error completing todo {todo_id}: {error_msg}[/red]")


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
def show_stats() -> None:
    """Show user progress and statistics."""
    from ..core.scoring import ScoringService

    try:
        scoring_service = ScoringService(db)
        progress = scoring_service.get_user_progress()

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
        console.print(f"[red]✗ Error retrieving stats: {e}[/red]")


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
