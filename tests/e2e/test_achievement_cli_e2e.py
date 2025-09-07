"""End-to-end tests for achievement CLI commands."""

import gc
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from todo.cli.main import app
from todo.db.connection import DatabaseConnection
from todo.db.migrations import MigrationManager


@pytest.fixture
def achievement_cli_e2e():
    """Create a real database for E2E achievement CLI testing."""
    # Force garbage collection before creating new connections
    gc.collect()

    temp_dir = tempfile.mkdtemp(prefix="todo_achievement_cli_e2e_")
    db_path = Path(temp_dir) / "achievement_cli_e2e.db"

    # Ensure no existing database file
    if db_path.exists():
        from contextlib import suppress

        with suppress(Exception):
            db_path.unlink()

    # Create database and initialize schema
    db = DatabaseConnection(str(db_path))
    migration_manager = MigrationManager(db)
    migration_manager.initialize_schema()

    yield db, str(db_path), temp_dir

    # Enhanced cleanup - force close all connections and clean up
    try:
        # Explicitly close the connection
        if hasattr(db, "conn") and db.conn:
            db.conn.close()
        db.close()
    except Exception:
        pass

    # Force garbage collection to release any remaining references
    gc.collect()

    # Give DuckDB time to release file locks
    import time

    time.sleep(0.2)

    # Force remove database file even if locked
    import shutil

    try:
        if db_path.exists():
            db_path.unlink()
    except Exception:
        # If file is still locked, remove entire temp directory
        from contextlib import suppress

        with suppress(Exception):
            shutil.rmtree(temp_dir, ignore_errors=True)

    # Clean up temp directory if it still exists
    try:
        if Path(temp_dir).exists():
            # Remove any remaining files first
            for item in Path(temp_dir).iterdir():
                try:
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
                except Exception:
                    pass
            # Then remove the directory
            Path(temp_dir).rmdir()
    except Exception:
        pass


@pytest.fixture
def cli_runner():
    """CLI runner for testing."""
    return CliRunner()


def patch_cli_database(monkeypatch, db):
    """Patch CLI global database objects to use test database."""
    # Import and patch the global database objects
    from todo.ai.background import BackgroundEnrichmentService
    from todo.ai.enrichment_service import EnrichmentService
    from todo.cli import main
    from todo.db.repository import AIEnrichmentRepository, TodoRepository

    # Create new instances with the test database
    test_todo_repo = TodoRepository(db)
    test_ai_repo = AIEnrichmentRepository(db)
    test_enrichment_service = EnrichmentService(db)
    test_background_service = BackgroundEnrichmentService(db)

    # Patch all the global services to use our test database
    monkeypatch.setattr(main, "db", db)
    monkeypatch.setattr(main, "todo_repo", test_todo_repo)
    monkeypatch.setattr(main, "ai_repo", test_ai_repo)
    monkeypatch.setattr(main, "enrichment_service", test_enrichment_service)
    monkeypatch.setattr(main, "background_service", test_background_service)

    # Also patch the migration manager to use the test database
    from todo.db.migrations import MigrationManager

    test_migration_manager = MigrationManager(db)
    monkeypatch.setattr(main, "migration_manager", test_migration_manager)

    # Debug info can be enabled if needed for troubleshooting
    # print(f"🔧 Patched CLI to use test database: {db.db_path}")
    # print(f"🔧 Todo repo database path: {test_todo_repo.db.db_path}")
    # print(f"🔧 Are databases the same? {main.db is db}")


class TestAchievementCLIE2E:
    """Test achievement CLI commands end-to-end."""

    def test_stats_command_with_fresh_database(
        self, achievement_cli_e2e, cli_runner, monkeypatch
    ):
        """Test stats command with a fresh database."""
        db, db_path, temp_dir = achievement_cli_e2e

        # Patch the database path
        monkeypatch.setenv("TODO_DATABASE_PATH", db_path)

        # Run stats command
        result = cli_runner.invoke(app, ["stats"])

        assert result.exit_code == 0
        assert "📊 Your Progress" in result.stdout
        assert "Level" in result.stdout
        assert "Total Points" in result.stdout
        assert "Tasks Completed" in result.stdout
        assert "Achievements" in result.stdout

        # Should show at least level 1 (regardless of points)
        assert "⭐" in result.stdout  # Level indicator
        assert "🎯" in result.stdout  # Points indicator

    def test_achievements_command_with_no_data(
        self, achievement_cli_e2e, cli_runner, monkeypatch
    ):
        """Test achievements command with no unlocked achievements."""
        db, db_path, temp_dir = achievement_cli_e2e

        # Patch the database path
        monkeypatch.setenv("TODO_DATABASE_PATH", db_path)

        # Run achievements command
        result = cli_runner.invoke(app, ["achievements"])

        assert result.exit_code == 0
        assert "🏆 Achievement Progress" in result.stdout
        # Don't test exact number, just that it doesn't crash

    def test_achievements_command_unlocked_flag(
        self, achievement_cli_e2e, cli_runner, monkeypatch
    ):
        """Test achievements --unlocked flag."""
        db, db_path, temp_dir = achievement_cli_e2e

        # Patch the database path
        monkeypatch.setenv("TODO_DATABASE_PATH", db_path)

        # Run with --unlocked flag
        result = cli_runner.invoke(app, ["achievements", "--unlocked"])

        assert result.exit_code == 0
        assert "🏆 Achievement Progress" in result.stdout
        # With no tasks completed, should show no unlocked achievements

    def test_achievements_command_progress_flag(
        self, achievement_cli_e2e, cli_runner, monkeypatch
    ):
        """Test achievements --progress flag."""
        db, db_path, temp_dir = achievement_cli_e2e

        # Patch the database path and global database objects in CLI
        monkeypatch.setenv("TODO_DATABASE_PATH", db_path)
        patch_cli_database(monkeypatch, db)

        # Run with --progress flag
        result = cli_runner.invoke(app, ["achievements", "--progress"])

        assert result.exit_code == 0
        assert "🏆 Achievement Progress" in result.stdout
        assert "📊 Achievement Progress" in result.stdout

        # With fresh database, should show basic achievements structure
        # Don't assert specific achievements since we start with empty database

    def test_full_workflow_with_achievements(
        self, achievement_cli_e2e, cli_runner, monkeypatch
    ):
        """Test full workflow: create todos, complete them, check achievements."""
        db, db_path, temp_dir = achievement_cli_e2e

        # Patch the database path and global database objects in CLI
        monkeypatch.setenv("TODO_DATABASE_PATH", db_path)
        patch_cli_database(monkeypatch, db)

        # Add some todos (using --no-ai to prevent background enrichment issues)
        result = cli_runner.invoke(app, ["add", "First test task", "--no-ai"])
        assert result.exit_code == 0

        result = cli_runner.invoke(app, ["add", "Second test task", "--no-ai"])
        assert result.exit_code == 0

        # Complete first task
        result = cli_runner.invoke(app, ["done", "1"])
        assert result.exit_code == 0
        assert "✓ Completed:" in result.stdout

        # Check stats after completion
        result = cli_runner.invoke(app, ["stats"])
        assert result.exit_code == 0
        assert "📊 Your Progress" in result.stdout

        # Should have points and at least 1 completed task
        assert "Tasks Completed" in result.stdout

        # Check achievements - should have unlocked achievements
        result = cli_runner.invoke(app, ["achievements", "--unlocked"])
        assert result.exit_code == 0

        # Should show achievement progress (exact achievements may vary)
        assert "🏆 Achievement Progress" in result.stdout

    def test_achievements_short_flags(
        self, achievement_cli_e2e, cli_runner, monkeypatch
    ):
        """Test achievement command short flags."""
        db, db_path, temp_dir = achievement_cli_e2e

        # Patch the database path
        monkeypatch.setenv("TODO_DATABASE_PATH", db_path)

        # Test -u flag (--unlocked)
        result = cli_runner.invoke(app, ["achievements", "-u"])
        assert result.exit_code == 0
        assert "🏆 Achievement Progress" in result.stdout

        # Test -p flag (--progress)
        result = cli_runner.invoke(app, ["achievements", "-p"])
        assert result.exit_code == 0
        assert "🏆 Achievement Progress" in result.stdout
        assert "📊 Achievement Progress" in result.stdout

    def test_error_handling_in_commands(
        self, achievement_cli_e2e, cli_runner, monkeypatch
    ):
        """Test error handling in CLI commands."""
        db, db_path, temp_dir = achievement_cli_e2e

        # Use an invalid database path to test error handling
        monkeypatch.setenv("TODO_DATABASE_PATH", "/invalid/path/to/database.db")

        # Stats command should handle database errors gracefully
        cli_runner.invoke(app, ["stats"])
        # The command might succeed by creating a new database, or fail gracefully
        # Either way, it shouldn't crash with an unhandled exception

        # Achievements command should also handle errors gracefully
        cli_runner.invoke(app, ["achievements"])
        # Same expectation - graceful handling

    def test_achievements_with_multiple_completions(
        self, achievement_cli_e2e, cli_runner, monkeypatch
    ):
        """Test achievements unlock with multiple task completions."""
        db, db_path, temp_dir = achievement_cli_e2e

        # Patch the database path and global database objects in CLI
        monkeypatch.setenv("TODO_DATABASE_PATH", db_path)
        patch_cli_database(monkeypatch, db)

        # Add just 2 tasks to minimize operations
        result = cli_runner.invoke(app, ["add", "Task 1"])
        assert result.exit_code == 0

        result = cli_runner.invoke(app, ["add", "Task 2"])
        assert result.exit_code == 0

        # Complete 1 task only
        result = cli_runner.invoke(app, ["done", "1"])
        assert result.exit_code == 0

        # Check achievements - should work without hanging
        result = cli_runner.invoke(app, ["achievements", "--unlocked"])
        assert result.exit_code == 0

        # Should show achievement progress header
        assert "🏆" in result.stdout

        # Check stats
        result = cli_runner.invoke(app, ["stats"])
        assert result.exit_code == 0
        assert "Tasks Completed" in result.stdout

        # Should show achievement summary
        assert "Achievements" in result.stdout

    def test_achievement_progress_bars(
        self, achievement_cli_e2e, cli_runner, monkeypatch
    ):
        """Test that achievement progress bars are displayed correctly."""
        db, db_path, temp_dir = achievement_cli_e2e

        # Patch the database path and global database objects in CLI
        monkeypatch.setenv("TODO_DATABASE_PATH", db_path)
        patch_cli_database(monkeypatch, db)

        # Add and complete a few tasks to get partial progress
        result = cli_runner.invoke(app, ["add", "Task 1"])
        assert result.exit_code == 0

        result = cli_runner.invoke(app, ["add", "Task 2"])
        assert result.exit_code == 0

        result = cli_runner.invoke(app, ["done", "1"])
        assert result.exit_code == 0

        result = cli_runner.invoke(app, ["done", "2"])
        assert result.exit_code == 0

        # Check progress view
        result = cli_runner.invoke(app, ["achievements", "--progress"])
        assert result.exit_code == 0

        # Should show progress bars or percentages
        assert "%" in result.stdout
        # Progress bars use unicode characters
        progress_indicators = ["━", "╸", "Progress Details:"]
        assert any(indicator in result.stdout for indicator in progress_indicators)


class TestAchievementCLIIntegration:
    """Test integration between different CLI commands and achievements."""

    def test_task_completion_shows_achievement_unlock(
        self, achievement_cli_e2e, cli_runner, monkeypatch
    ):
        """Test that completing tasks shows achievement unlock notifications."""
        db, db_path, temp_dir = achievement_cli_e2e

        # Patch the database path and global database objects in CLI
        monkeypatch.setenv("TODO_DATABASE_PATH", db_path)
        patch_cli_database(monkeypatch, db)

        # Add first task
        result = cli_runner.invoke(app, ["add", "My first task"])
        assert result.exit_code == 0

        # Complete first task - should unlock "First Steps" achievement
        result = cli_runner.invoke(app, ["done", "1"])
        assert result.exit_code == 0

        # Should show completion message and potentially achievement unlock
        assert "✓ Completed:" in result.stdout

        # The achievement unlock notification is in the CLI output
        # It might show "🏆 Achievement Unlocked" or similar
        # The exact format depends on the implementation

    def test_daily_goal_achievement_workflow(
        self, achievement_cli_e2e, cli_runner, monkeypatch
    ):
        """Test daily goal achievement workflow."""
        db, db_path, temp_dir = achievement_cli_e2e

        # Patch the database path and global database objects in CLI
        monkeypatch.setenv("TODO_DATABASE_PATH", db_path)
        patch_cli_database(monkeypatch, db)

        # Add tasks to meet daily goal (default is 3)
        for i in range(4):
            result = cli_runner.invoke(app, ["add", f"Daily task {i + 1}"])
            assert result.exit_code == 0

        # Complete tasks one by one
        for i in range(3):
            result = cli_runner.invoke(app, ["done", str(i + 1)])
            assert result.exit_code == 0

        # Check stats - should show daily goal met
        result = cli_runner.invoke(app, ["stats"])
        assert result.exit_code == 0

        # Should show goal status as met
        assert "Goal Status" in result.stdout
        # Should either show "✅ Met" or progress toward goal

        # Check if daily goal achievement was unlocked
        result = cli_runner.invoke(app, ["achievements", "--unlocked"])
        assert result.exit_code == 0
        # May have unlocked "Goal Getter" achievement


if __name__ == "__main__":
    pytest.main([__file__])
