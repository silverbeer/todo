"""Main CLI application entry point."""

import typer
from rich.console import Console

console = Console()
app = typer.Typer(
    name="todo",
    help="AI-powered terminal todo application for developers",
    add_completion=False,
    no_args_is_help=True,
)


@app.command("version")
def version() -> None:
    """Show application version."""
    console.print("todo version 0.1.0")


@app.command("add")
def add_todo(task: str) -> None:
    """Add a new todo task."""
    console.print(f"[green]Added task:[/green] {task}")
    console.print("[dim]Note: Full implementation coming soon![/dim]")


if __name__ == "__main__":
    app()
