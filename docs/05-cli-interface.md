# CLI Interface - Implementation Plan

> **⚠️ IMPORTANT**: Review this document before implementation. As we develop the application, requirements may change and this documentation should be updated to reflect any modifications to the CLI interface and commands.

## Overview
This document outlines the Typer-based CLI interface with Rich formatting for the terminal todo application. The focus is on simplicity, beauty, and developer-friendly commands that make task management efficient and engaging.

## Core Design Principles

### Simplicity First
- Primary workflow: `todo add "task"` → `todo done <id>`
- All complex features accessible but not required
- Sensible defaults for everything
- Progressive disclosure of advanced features

### Beautiful Output
- Rich colors and formatting throughout
- Tables for list views with clear headers
- Progress bars for goals and streaks
- Icons and emojis for visual appeal
- Consistent color coding (status, priority, categories)

### Developer-Friendly
- Short command aliases (`ls` for `list`, `rm` for `remove`)
- Flexible input formats
- JSON output option for scripting
- Auto-completion support
- Helpful error messages

## Main CLI Application Structure

### App Configuration
```python
# src/todo/cli/main.py
import typer
from typing import Optional, List, Annotated
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, BarColumn, TextColumn
from rich.text import Text
from rich.prompt import Confirm, Prompt
from datetime import date, datetime

from todo.cli.display import DisplayManager
from todo.cli.utils import handle_error, validate_date, parse_size_priority
from todo.core.config import get_app_config
from todo.db.repositories.todo import TodoRepository
from todo.ai.background import BackgroundEnrichmentService

# Initialize CLI application
console = Console()
app = typer.Typer(
    name="todo",
    help="🎯 AI-powered terminal todo app for developers",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]}
)

# Initialize services
config = get_app_config()
todo_repo = TodoRepository()
display = DisplayManager(console)
background_enrichment = BackgroundEnrichmentService()

# Global options
def version_callback(value: bool):
    if value:
        console.print("todo version 0.1.0")
        raise typer.Exit()

@app.callback()
def main(
    version: Annotated[Optional[bool], typer.Option("--version", "-v", callback=version_callback)] = None,
):
    """🎯 AI-powered terminal todo app for developers"""
    pass
```

### Core Commands

#### Add Command
```python
@app.command("add")
def add_todo(
    title: Annotated[str, typer.Argument(help="Todo title/description")],
    description: Annotated[Optional[str], typer.Option("--desc", "-d", help="Additional description")] = None,
    priority: Annotated[Optional[str], typer.Option("--priority", "-p", help="Priority: low, medium, high, urgent")] = None,
    size: Annotated[Optional[str], typer.Option("--size", "-s", help="Size: small, medium, large")] = None,
    category: Annotated[Optional[str], typer.Option("--category", "-c", help="Category name")] = None,
    due: Annotated[Optional[str], typer.Option("--due", help="Due date (YYYY-MM-DD or 'tomorrow', 'monday', etc.)")] = None,
    no_ai: Annotated[bool, typer.Option("--no-ai", help="Skip AI enrichment")] = False,
):
    """
    ➕ Add a new todo item

    Examples:
      todo add "Cut the grass"
      todo add "Meeting with client" --priority high --due tomorrow
      todo add "Learn Python" --size large --category Learning --no-ai
    """
    try:
        # Parse and validate inputs
        parsed_priority = parse_size_priority(priority, "priority") if priority else None
        parsed_size = parse_size_priority(size, "size") if size else None
        parsed_due_date = validate_date(due) if due else None

        # Create todo
        todo = todo_repo.create_todo(title, description)

        # Apply user overrides
        updates = {}
        if parsed_size:
            updates['user_override_size'] = parsed_size
            updates['final_size'] = parsed_size
        if parsed_priority:
            updates['user_override_priority'] = parsed_priority
            updates['final_priority'] = parsed_priority
        if parsed_due_date:
            updates['due_date'] = parsed_due_date
        if category:
            category_id = _get_or_create_category(category)
            if category_id:
                updates['category_id'] = category_id

        if updates:
            todo = todo_repo.update(todo.id, updates)

        # Start background AI enrichment
        if not no_ai and config.ai.enable_auto_enrichment:
            background_enrichment.enrich_todo_background(todo.id)

        # Display result
        display.show_todo_created(todo, ai_processing=not no_ai)

    except Exception as e:
        handle_error(e, "Failed to create todo")
```

#### List Command
```python
@app.command("list")
@app.command("ls")  # Alias
def list_todos(
    status: Annotated[Optional[str], typer.Option("--status", "-s", help="Filter by status: pending, in_progress, completed")] = None,
    category: Annotated[Optional[str], typer.Option("--category", "-c", help="Filter by category")] = None,
    priority: Annotated[Optional[str], typer.Option("--priority", "-p", help="Filter by priority")] = None,
    due: Annotated[Optional[str], typer.Option("--due", help="Filter by due date: today, tomorrow, overdue, week")] = None,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Number of todos to show")] = 20,
    all: Annotated[bool, typer.Option("--all", "-a", help="Show all todos including completed")] = False,
    json: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
):
    """
    📋 List todos with optional filters

    Examples:
      todo list
      todo ls --status pending --limit 10
      todo list --category Work --priority high
      todo ls --due today
    """
    try:
        # Build filters
        filters = {}
        if status:
            filters['status'] = status
        if category:
            filters['category'] = category
        if priority:
            filters['priority'] = priority
        if due:
            filters['due_filter'] = due
        if not all:
            filters['exclude_completed'] = True

        # Get todos
        todos = todo_repo.get_filtered_todos(filters, limit=limit)

        # Get dashboard stats
        stats = todo_repo.get_dashboard_stats()

        if json:
            import json as json_lib
            output = {
                "todos": [todo.model_dump() for todo in todos],
                "stats": stats,
                "total_count": len(todos)
            }
            console.print(json_lib.dumps(output, indent=2, default=str))
        else:
            display.show_todo_list(todos, stats)

    except Exception as e:
        handle_error(e, "Failed to list todos")
```

#### Complete Command
```python
@app.command("done")
@app.command("complete")  # Alias
def complete_todo(
    todo_ids: Annotated[List[int], typer.Argument(help="Todo ID(s) to complete")],
    time_taken: Annotated[Optional[int], typer.Option("--took", help="Actual time taken in minutes")] = None,
):
    """
    ✅ Mark todo(s) as completed

    Examples:
      todo done 5
      todo done 3 7 12  # Complete multiple todos
      todo complete 8 --took 45
    """
    try:
        completed_todos = []
        total_points = 0

        for todo_id in todo_ids:
            # Complete the todo
            todo = todo_repo.complete_todo(todo_id, time_taken)
            if todo:
                completed_todos.append(todo)
                total_points += todo.total_points_earned
            else:
                console.print(f"[yellow]Warning: Todo {todo_id} not found or already completed[/yellow]")

        if completed_todos:
            display.show_todos_completed(completed_todos, total_points)

            # Check for achievements
            from todo.core.scoring import ScoringService
            scoring = ScoringService()
            new_achievements = scoring.check_new_achievements()
            if new_achievements:
                display.show_achievements_unlocked(new_achievements)
        else:
            console.print("[red]No todos were completed[/red]")

    except Exception as e:
        handle_error(e, "Failed to complete todos")
```

#### Show/Detail Command
```python
@app.command("show")
@app.command("detail")  # Alias
def show_todo(
    todo_id: Annotated[int, typer.Argument(help="Todo ID to show")],
    ai: Annotated[bool, typer.Option("--ai", help="Show AI enrichment details")] = False,
):
    """
    👁️ Show detailed information about a todo

    Examples:
      todo show 5
      todo show 12 --ai  # Include AI analysis
    """
    try:
        todo = todo_repo.get_by_id_with_relations(todo_id)
        if not todo:
            console.print(f"[red]Todo {todo_id} not found[/red]")
            return

        # Get AI enrichment if requested
        ai_enrichment = None
        if ai:
            from todo.db.repositories.ai import AIEnrichmentRepository
            ai_repo = AIEnrichmentRepository()
            ai_enrichment = ai_repo.get_by_todo_id(todo_id)

        display.show_todo_detail(todo, ai_enrichment)

    except Exception as e:
        handle_error(e, "Failed to show todo")
```

#### Update Command
```python
@app.command("update")
@app.command("edit")  # Alias
def update_todo(
    todo_id: Annotated[int, typer.Argument(help="Todo ID to update")],
    title: Annotated[Optional[str], typer.Option("--title", "-t", help="New title")] = None,
    description: Annotated[Optional[str], typer.Option("--desc", "-d", help="New description")] = None,
    priority: Annotated[Optional[str], typer.Option("--priority", "-p", help="New priority")] = None,
    size: Annotated[Optional[str], typer.Option("--size", "-s", help="New size")] = None,
    category: Annotated[Optional[str], typer.Option("--category", "-c", help="New category")] = None,
    due: Annotated[Optional[str], typer.Option("--due", help="New due date")] = None,
    status: Annotated[Optional[str], typer.Option("--status", help="New status")] = None,
):
    """
    ✏️ Update todo properties

    Examples:
      todo update 5 --priority high --due tomorrow
      todo edit 3 --title "New title" --category Work
    """
    try:
        # Get existing todo
        existing_todo = todo_repo.get_by_id(todo_id)
        if not existing_todo:
            console.print(f"[red]Todo {todo_id} not found[/red]")
            return

        # Build updates
        updates = {}
        if title:
            updates['title'] = title
        if description:
            updates['description'] = description
        if priority:
            parsed_priority = parse_size_priority(priority, "priority")
            updates['user_override_priority'] = parsed_priority
            updates['final_priority'] = parsed_priority
        if size:
            parsed_size = parse_size_priority(size, "size")
            updates['user_override_size'] = parsed_size
            updates['final_size'] = parsed_size
        if category:
            category_id = _get_or_create_category(category)
            if category_id:
                updates['category_id'] = category_id
        if due:
            parsed_due = validate_date(due)
            updates['due_date'] = parsed_due
        if status:
            updates['status'] = status

        if not updates:
            console.print("[yellow]No changes specified[/yellow]")
            return

        # Apply updates
        updated_todo = todo_repo.update(todo_id, updates)

        # Record learning if AI suggestions were overridden
        if (priority or size or category) and hasattr(existing_todo, 'ai_enrichment'):
            from todo.ai.learning import LearningService
            learning = LearningService()
            # Record override for learning (implementation details)

        display.show_todo_updated(updated_todo)

    except Exception as e:
        handle_error(e, "Failed to update todo")
```

### Stats and Gamification Commands

#### Stats Command
```python
@app.command("stats")
def show_stats(
    period: Annotated[str, typer.Option("--period", "-p", help="Period: today, week, month, year, all")] = "week",
    detailed: Annotated[bool, typer.Option("--detailed", "-d", help="Show detailed breakdown")] = False,
):
    """
    📊 Show productivity statistics and gamification info

    Examples:
      todo stats
      todo stats --period month --detailed
    """
    try:
        from todo.db.repositories.gamification import GamificationRepository
        gamification_repo = GamificationRepository()

        stats = gamification_repo.get_stats_for_period(period)
        achievements = gamification_repo.get_recent_achievements(limit=5)

        display.show_statistics(stats, achievements, detailed)

    except Exception as e:
        handle_error(e, "Failed to show statistics")

@app.command("achievements")
def show_achievements(
    all: Annotated[bool, typer.Option("--all", "-a", help="Show all achievements including locked")] = False,
):
    """
    🏆 Show achievements and progress
    """
    try:
        from todo.db.repositories.gamification import GamificationRepository
        gamification_repo = GamificationRepository()

        achievements = gamification_repo.get_all_achievements(include_locked=all)
        display.show_achievements(achievements)

    except Exception as e:
        handle_error(e, "Failed to show achievements")
```

#### Goals Command
```python
@app.command("goals")
def manage_goals(
    daily: Annotated[Optional[int], typer.Option("--daily", help="Set daily goal")] = None,
    weekly: Annotated[Optional[int], typer.Option("--weekly", help="Set weekly goal")] = None,
    monthly: Annotated[Optional[int], typer.Option("--monthly", help="Set monthly goal")] = None,
):
    """
    🎯 View or update productivity goals

    Examples:
      todo goals  # Show current goals
      todo goals --daily 5 --weekly 30
    """
    try:
        from todo.db.repositories.gamification import GamificationRepository
        gamification_repo = GamificationRepository()

        if daily or weekly or monthly:
            # Update goals
            updates = {}
            if daily: updates['daily_goal'] = daily
            if weekly: updates['weekly_goal'] = weekly
            if monthly: updates['monthly_goal'] = monthly

            gamification_repo.update_goals(updates)
            console.print("[green]Goals updated successfully![/green]")

        # Show current goals and progress
        goals = gamification_repo.get_current_goals()
        progress = gamification_repo.get_goal_progress()

        display.show_goals_and_progress(goals, progress)

    except Exception as e:
        handle_error(e, "Failed to manage goals")
```

### Utility Commands

#### Search Command
```python
@app.command("search")
@app.command("find")  # Alias
def search_todos(
    query: Annotated[str, typer.Argument(help="Search query")],
    limit: Annotated[int, typer.Option("--limit", "-n", help="Number of results")] = 10,
    case_sensitive: Annotated[bool, typer.Option("--case-sensitive", help="Case sensitive search")] = False,
):
    """
    🔍 Search todos by text

    Examples:
      todo search "meeting"
      todo find "grocery" --limit 5
    """
    try:
        todos = todo_repo.search_todos(query, limit, case_sensitive)
        display.show_search_results(todos, query)

    except Exception as e:
        handle_error(e, "Failed to search todos")

@app.command("categories")
@app.command("cats")  # Alias
def manage_categories(
    add: Annotated[Optional[str], typer.Option("--add", help="Add new category")] = None,
    color: Annotated[Optional[str], typer.Option("--color", help="Category color (hex)")] = None,
    icon: Annotated[Optional[str], typer.Option("--icon", help="Category icon (emoji)")] = None,
):
    """
    🏷️ Manage todo categories

    Examples:
      todo categories  # List all categories
      todo cats --add "Projects" --color "#FF5722" --icon "🚀"
    """
    try:
        from todo.db.repositories.category import CategoryRepository
        category_repo = CategoryRepository()

        if add:
            # Create new category
            category = category_repo.create_category(add, color, icon)
            console.print(f"[green]Created category: {category.name}[/green]")

        # Show all categories
        categories = category_repo.get_all()
        display.show_categories(categories)

    except Exception as e:
        handle_error(e, "Failed to manage categories")
```

#### Config Command
```python
@app.command("config")
def manage_config(
    show: Annotated[bool, typer.Option("--show", help="Show current configuration")] = False,
    set_key: Annotated[Optional[str], typer.Option("--set", help="Configuration key to set")] = None,
    value: Annotated[Optional[str], typer.Option("--value", help="Configuration value")] = None,
):
    """
    ⚙️ Manage application configuration

    Examples:
      todo config --show
      todo config --set daily_goal --value 5
    """
    try:
        if show:
            display.show_config(config)
        elif set_key and value:
            # Update configuration (implement config update logic)
            console.print(f"[green]Updated {set_key} = {value}[/green]")
        else:
            display.show_config(config)

    except Exception as e:
        handle_error(e, "Failed to manage configuration")
```

## Display Manager Implementation

### Rich Formatting
```python
# src/todo/cli/display.py
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn, MofNCompleteColumn
from rich.text import Text
from rich.columns import Columns
from rich.tree import Tree
from typing import List, Optional, Dict, Any
from datetime import date, datetime

from todo.models.todo import Todo, TodoStatus, TaskSize, Priority
from todo.models.gamification import UserStats, Achievement
from todo.models.ai import AIEnrichment

class DisplayManager:
    """Handles all Rich-based display formatting."""

    def __init__(self, console: Console):
        self.console = console

        # Color scheme
        self.colors = {
            'pending': 'white',
            'in_progress': 'yellow',
            'completed': 'green',
            'archived': 'dim white',
            'overdue': 'red',
            'priority_low': 'blue',
            'priority_medium': 'yellow',
            'priority_high': 'red',
            'priority_urgent': 'bold red',
            'size_small': 'green',
            'size_medium': 'yellow',
            'size_large': 'red',
        }

        # Icons
        self.icons = {
            'pending': '⏳',
            'in_progress': '🔄',
            'completed': '✅',
            'archived': '📦',
            'overdue': '⚠️',
            'priority_low': '🔵',
            'priority_medium': '🟡',
            'priority_high': '🔴',
            'priority_urgent': '🚨',
            'size_small': '🟢',
            'size_medium': '🟡',
            'size_large': '🔴',
        }

    def show_todo_list(self, todos: List[Todo], stats: Dict[str, Any]) -> None:
        """Display formatted todo list with stats."""

        # Create header with stats
        self._show_dashboard_header(stats)

        if not todos:
            self.console.print("\n[dim]No todos found. Use 'todo add \"task\"' to create one![/dim]")
            return

        # Create todo table
        table = Table(
            title="📋 Your Todos",
            show_header=True,
            header_style="bold cyan",
            border_style="blue",
            expand=True
        )

        table.add_column("ID", style="dim", width=4)
        table.add_column("Status", width=8)
        table.add_column("Title", flex=1)
        table.add_column("Category", width=12)
        table.add_column("Priority", width=8)
        table.add_column("Size", width=6)
        table.add_column("Due", width=10)
        table.add_column("Points", width=6)

        for todo in todos:
            # Format row data
            status_text = Text(todo.status.value)
            status_text.stylize(self.colors[todo.status.value])

            title_text = Text(todo.title)
            if todo.is_overdue:
                title_text.stylize("red")

            category_text = todo.category.name if todo.category else ""

            priority_text = Text(self.icons[f'priority_{todo.final_priority.value}'])
            priority_text.append(f" {todo.final_priority.value}")

            size_text = Text(self.icons[f'size_{todo.final_size.value}'])
            size_text.append(f" {todo.final_size.value}")

            due_text = ""
            if todo.due_date:
                due_text = todo.due_date.strftime("%m/%d")
                if todo.is_overdue:
                    due_text = f"[red]{due_text}[/red]"

            points_text = str(todo.total_points_earned or 0)

            table.add_row(
                str(todo.id),
                status_text,
                title_text,
                category_text,
                priority_text,
                size_text,
                due_text,
                points_text
            )

        self.console.print("\n", table)

        # Show helpful commands
        self._show_quick_help()

    def _show_dashboard_header(self, stats: Dict[str, Any]) -> None:
        """Show dashboard stats header."""

        # Create stats panels
        panels = []

        # Today's progress
        today_panel = Panel(
            f"[bold green]{stats.get('tasks_completed_today', 0)}[/bold green] tasks\n"
            f"[bold yellow]{stats.get('points_earned_today', 0)}[/bold yellow] points",
            title="📅 Today",
            border_style="green",
            width=20
        )
        panels.append(today_panel)

        # Current streak
        streak_panel = Panel(
            f"[bold orange1]{stats.get('current_streak', 0)}[/bold orange1] days\n"
            f"🔥 Keep it up!",
            title="🔥 Streak",
            border_style="orange1",
            width=20
        )
        panels.append(streak_panel)

        # Overdue items
        overdue_count = stats.get('overdue_count', 0)
        overdue_color = "red" if overdue_count > 0 else "green"
        overdue_panel = Panel(
            f"[bold {overdue_color}]{overdue_count}[/bold {overdue_color}] items\n"
            f"{'⚠️ Needs attention!' if overdue_count > 0 else '✅ All caught up!'}",
            title="⚠️ Overdue",
            border_style=overdue_color,
            width=20
        )
        panels.append(overdue_panel)

        # Level and total points
        level_panel = Panel(
            f"Level [bold cyan]{stats.get('current_level', 1)}[/bold cyan]\n"
            f"[dim]{stats.get('total_points', 0)} total points[/dim]",
            title="🏆 Level",
            border_style="cyan",
            width=20
        )
        panels.append(level_panel)

        self.console.print(Columns(panels, expand=True))

    def show_todo_created(self, todo: Todo, ai_processing: bool = False) -> None:
        """Show confirmation of todo creation."""

        panel_content = f"[green]✅ Created todo #{todo.id}[/green]\n"
        panel_content += f"[bold]{todo.title}[/bold]"

        if ai_processing:
            panel_content += "\n[dim]🤖 AI enrichment processing in background...[/dim]"

        panel = Panel(
            panel_content,
            title="Todo Created",
            border_style="green",
            expand=False
        )

        self.console.print("\n", panel)

    def show_todos_completed(self, todos: List[Todo], total_points: int) -> None:
        """Show completion confirmation with points."""

        if len(todos) == 1:
            todo = todos[0]
            content = f"[green]✅ Completed: {todo.title}[/green]\n"
            content += f"[bold yellow]+{todo.total_points_earned} points![/bold yellow]"
        else:
            content = f"[green]✅ Completed {len(todos)} todos![/green]\n"
            content += f"[bold yellow]+{total_points} points total![/bold yellow]"

        panel = Panel(
            content,
            title="🎉 Great Work!",
            border_style="green",
            expand=False
        )

        self.console.print("\n", panel)

    def _show_quick_help(self) -> None:
        """Show helpful command suggestions."""
        help_text = "[dim]Quick commands: [/dim]"
        help_text += "[cyan]todo add \"task\"[/cyan] • "
        help_text += "[cyan]todo done <id>[/cyan] • "
        help_text += "[cyan]todo show <id>[/cyan] • "
        help_text += "[cyan]todo stats[/cyan]"

        self.console.print(f"\n{help_text}")
```

## CLI Utilities

### Input Validation and Parsing
```python
# src/todo/cli/utils.py
from typing import Optional, Union
from datetime import date, datetime, timedelta
import re
from rich.console import Console
from todo.models.todo import TaskSize, Priority, TodoStatus

console = Console()

def handle_error(error: Exception, context: str) -> None:
    """Handle and display errors gracefully."""
    console.print(f"[red]Error: {context}[/red]")
    console.print(f"[dim]{str(error)}[/dim]")

def parse_size_priority(value: str, type_name: str) -> Union[TaskSize, Priority]:
    """Parse size or priority from string input."""
    if type_name == "size":
        size_map = {
            's': TaskSize.SMALL, 'small': TaskSize.SMALL,
            'm': TaskSize.MEDIUM, 'medium': TaskSize.MEDIUM,
            'l': TaskSize.LARGE, 'large': TaskSize.LARGE,
        }
        parsed = size_map.get(value.lower())
        if not parsed:
            raise ValueError(f"Invalid size: {value}. Use: small, medium, large (or s, m, l)")
        return parsed

    elif type_name == "priority":
        priority_map = {
            'l': Priority.LOW, 'low': Priority.LOW,
            'm': Priority.MEDIUM, 'medium': Priority.MEDIUM,
            'h': Priority.HIGH, 'high': Priority.HIGH,
            'u': Priority.URGENT, 'urgent': Priority.URGENT,
        }
        parsed = priority_map.get(value.lower())
        if not parsed:
            raise ValueError(f"Invalid priority: {value}. Use: low, medium, high, urgent (or l, m, h, u)")
        return parsed

def validate_date(date_str: str) -> date:
    """Parse and validate date input with natural language support."""
    date_str = date_str.lower().strip()
    today = date.today()

    # Handle relative dates
    if date_str in ['today']:
        return today
    elif date_str in ['tomorrow', 'tom']:
        return today + timedelta(days=1)
    elif date_str in ['yesterday']:
        return today - timedelta(days=1)

    # Handle day names (next occurrence)
    weekdays = {
        'monday': 0, 'mon': 0,
        'tuesday': 1, 'tue': 1, 'tues': 1,
        'wednesday': 2, 'wed': 2,
        'thursday': 3, 'thu': 3, 'thur': 3, 'thurs': 3,
        'friday': 4, 'fri': 4,
        'saturday': 5, 'sat': 5,
        'sunday': 6, 'sun': 6,
    }

    if date_str in weekdays:
        target_weekday = weekdays[date_str]
        days_ahead = target_weekday - today.weekday()
        if days_ahead <= 0:  # Target day already happened this week
            days_ahead += 7
        return today + timedelta(days=days_ahead)

    # Handle relative terms
    if date_str in ['next week']:
        return today + timedelta(weeks=1)
    elif date_str in ['next month']:
        next_month = today.replace(day=28) + timedelta(days=4)
        return next_month - timedelta(days=next_month.day - 1)

    # Try to parse ISO format (YYYY-MM-DD)
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        pass

    # Try other common formats
    formats = ['%m/%d/%Y', '%m/%d', '%m-%d-%Y', '%m-%d']
    for fmt in formats:
        try:
            parsed = datetime.strptime(date_str, fmt).date()
            # If no year provided, assume current year
            if parsed.year == 1900:
                parsed = parsed.replace(year=today.year)
                # If the date has passed, assume next year
                if parsed < today:
                    parsed = parsed.replace(year=today.year + 1)
            return parsed
        except ValueError:
            continue

    raise ValueError(f"Invalid date format: {date_str}. Use YYYY-MM-DD, MM/DD, or natural language like 'tomorrow', 'monday'")

def _get_or_create_category(category_name: str) -> Optional[int]:
    """Get existing category or create new one."""
    from todo.db.repositories.category import CategoryRepository

    category_repo = CategoryRepository()

    # Try to find existing category (case-insensitive)
    existing = category_repo.get_by_name_case_insensitive(category_name)
    if existing:
        return existing.id

    # Create new category
    new_category = category_repo.create_category(category_name)
    console.print(f"[dim]Created new category: {category_name}[/dim]")
    return new_category.id
```

## Auto-completion Support

### Bash Completion
```python
# src/todo/cli/completion.py
def get_completion_script() -> str:
    """Generate bash completion script."""
    return '''
    _todo_completion() {
        local cur prev commands
        COMPREPLY=()
        cur="${COMP_WORDS[COMP_CWORD]}"
        prev="${COMP_WORDS[COMP_CWORD-1]}"
        commands="add list ls done complete show detail update edit stats achievements goals search find categories cats config"

        case ${prev} in
            --status|-s)
                COMPREPLY=( $(compgen -W "pending in_progress completed archived" -- ${cur}) )
                return 0
                ;;
            --priority|-p)
                COMPREPLY=( $(compgen -W "low medium high urgent l m h u" -- ${cur}) )
                return 0
                ;;
            --size)
                COMPREPLY=( $(compgen -W "small medium large s m l" -- ${cur}) )
                return 0
                ;;
            --due)
                COMPREPLY=( $(compgen -W "today tomorrow monday tuesday wednesday thursday friday saturday sunday next" -- ${cur}) )
                return 0
                ;;
        esac

        if [[ ${cur} == -* ]]; then
            COMPREPLY=( $(compgen -W "--help --version --status --priority --size --category --due --limit --all --json --no-ai" -- ${cur}) )
        else
            COMPREPLY=( $(compgen -W "${commands}" -- ${cur}) )
        fi
    }

    complete -F _todo_completion todo
    '''
```

## Implementation Steps

### Step 1: Core CLI Structure
1. Create `src/todo/cli/__init__.py`
2. Implement main Typer app in `main.py`
3. Add basic add/list/done commands
4. Test basic CLI functionality

### Step 2: Display Manager
1. Implement Rich-based display formatting
2. Create todo list table with colors/icons
3. Add dashboard header with stats
4. Test visual output and formatting

### Step 3: Advanced Commands
1. Implement search, update, show commands
2. Add category and config management
3. Create stats and gamification displays
4. Test all command variations

### Step 4: Input Validation
1. Implement date parsing with natural language
2. Add size/priority parsing with aliases
3. Create error handling and validation
4. Test edge cases and error conditions

### Step 5: Polish and UX
1. Add auto-completion support
2. Implement helpful error messages
3. Add progress indicators where appropriate
4. Test overall user experience flow

## Success Criteria
- [ ] All core commands working (add, list, done, show, update)
- [ ] Beautiful Rich formatting throughout
- [ ] Natural language date parsing working
- [ ] Auto-completion functional
- [ ] Error handling graceful and helpful
- [ ] Performance responsive for typical usage
- [ ] Gamification elements engaging and clear
- [ ] JSON output option working for scripting
- [ ] Comprehensive help text and examples
