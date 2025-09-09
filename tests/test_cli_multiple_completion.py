"""Tests for multiple todo completion feature."""

import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from todo.cli.main import app
from todo.db.connection import DatabaseConnection
from todo.db.migrations import MigrationManager


def patch_cli_database_simple(db):
    """Simple database patching for testing."""
    from todo.ai.background import BackgroundEnrichmentService
    from todo.ai.enrichment_service import EnrichmentService
    from todo.cli import main as cli_main
    from todo.db.repository import AIEnrichmentRepository, TodoRepository

    # Patch CLI to use test database
    cli_main.db = db
    cli_main.todo_repo = TodoRepository(db)
    cli_main.ai_repo = AIEnrichmentRepository(db)
    cli_main.enrichment_service = EnrichmentService(db)
    cli_main.background_service = BackgroundEnrichmentService(db)


@pytest.fixture
def test_db():
    """Create isolated test database."""
    temp_dir = tempfile.mkdtemp(prefix="test_multi_completion_")
    db_path = Path(temp_dir) / "test.db"

    try:
        # Initialize database
        db = DatabaseConnection(str(db_path))
        migration_manager = MigrationManager(db)
        migration_manager.initialize_schema()

        # Patch CLI
        patch_cli_database_simple(db)

        yield db
    finally:
        # Cleanup
        try:
            db.close()
            import shutil

            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass


def test_single_todo_completion_backward_compatibility(test_db):
    """Test that single todo completion still works (backward compatibility)."""
    cli_runner = CliRunner()

    # Add a test todo
    result = cli_runner.invoke(app, ["add", "Single completion test", "--no-ai"])
    assert result.exit_code == 0

    # Complete single todo
    result = cli_runner.invoke(app, ["done", "1"])
    assert result.exit_code == 0
    assert "✓ Completed: Single completion test" in result.stdout
    assert "🎉 Earned" in result.stdout


def test_multiple_todo_completion(test_db):
    """Test completing multiple todos at once."""
    cli_runner = CliRunner()

    # Add multiple test todos
    for i in range(1, 5):  # Create 4 todos
        result = cli_runner.invoke(app, ["add", f"Multi task {i}", "--no-ai"])
        assert result.exit_code == 0

    # Complete multiple todos
    result = cli_runner.invoke(app, ["done", "1", "2", "3"])
    assert result.exit_code == 0

    # Check output
    assert "✓ Completed: Multi task 1" in result.stdout
    assert "✓ Completed: Multi task 2" in result.stdout
    assert "✓ Completed: Multi task 3" in result.stdout
    assert "📊 Summary: 3 todos completed" in result.stdout
    assert "🎯 Total points earned:" in result.stdout


def test_mixed_valid_invalid_todo_ids(test_db):
    """Test completing mix of valid and invalid todo IDs."""
    cli_runner = CliRunner()

    # Add test todos
    result = cli_runner.invoke(app, ["add", "Valid task 1", "--no-ai"])
    assert result.exit_code == 0
    result = cli_runner.invoke(app, ["add", "Valid task 2", "--no-ai"])
    assert result.exit_code == 0

    # Try to complete valid and invalid IDs
    result = cli_runner.invoke(app, ["done", "1", "999", "2", "1000"])
    assert result.exit_code == 0

    # Check that valid todos were completed
    assert "✓ Completed: Valid task 1" in result.stdout
    assert "✓ Completed: Valid task 2" in result.stdout

    # Check that invalid IDs were reported
    assert "✗ Todo 999 not found" in result.stdout
    assert "✗ Todo 1000 not found" in result.stdout

    # Check summary
    assert "📊 Summary: 2 todos completed" in result.stdout
    assert "❌ Failed: 2 todos could not be completed" in result.stdout


def test_multiple_completion_summary_display(test_db):
    """Test that summary is only shown for multiple todos."""
    cli_runner = CliRunner()

    # Add test todos
    result = cli_runner.invoke(app, ["add", "Summary test 1", "--no-ai"])
    assert result.exit_code == 0
    result = cli_runner.invoke(app, ["add", "Summary test 2", "--no-ai"])
    assert result.exit_code == 0

    # Complete single todo - should NOT show summary
    result = cli_runner.invoke(app, ["done", "1"])
    assert result.exit_code == 0
    assert "📊 Summary:" not in result.stdout

    # Complete multiple todos - should show summary
    result = cli_runner.invoke(app, ["done", "2"])
    # Actually, this is still single completion, let me add another todo
    result = cli_runner.invoke(app, ["add", "Summary test 3", "--no-ai"])
    assert result.exit_code == 0

    result = cli_runner.invoke(app, ["done", "2", "3"])
    assert result.exit_code == 0
    assert "📊 Summary:" in result.stdout


def test_no_duplicate_achievement_display(test_db):
    """Test that duplicate achievements are not shown multiple times."""
    cli_runner = CliRunner()

    # Add several todos to potentially trigger same achievement
    for i in range(1, 4):
        result = cli_runner.invoke(app, ["add", f"Achievement test {i}", "--no-ai"])
        assert result.exit_code == 0

    # Complete multiple todos at once (may trigger "First Steps" achievement)
    result = cli_runner.invoke(app, ["done", "1", "2", "3"])
    assert result.exit_code == 0

    # If achievements are unlocked, check they're not duplicated in summary
    if "🏆 Achievements unlocked:" in result.stdout:
        # Count occurrences of achievement names - they should appear only once in summary
        lines = result.stdout.split("\n")
        summary_started = False
        achievement_names = []

        for line in lines:
            if "🏆 Achievements unlocked:" in line:
                summary_started = True
            elif summary_started and "  •" in line:
                achievement_names.append(line)

        # Check that there are no duplicate achievement entries in summary
        unique_achievements = set(achievement_names)
        assert len(achievement_names) == len(
            unique_achievements
        ), "Duplicate achievements in summary"
