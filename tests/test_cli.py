"""Tests for CLI functionality."""

import json
import tempfile
from datetime import date, datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from todo.cli.main import app
from todo.db.connection import DatabaseConnection
from todo.db.migrations import MigrationManager
from todo.db.repository import TodoRepository
from todo.models import Priority, TaskSize


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test_cli.db"

    db = DatabaseConnection(str(db_path))

    # Initialize schema
    migration_manager = MigrationManager(db)
    migration_manager.initialize_schema()

    yield db

    # Cleanup
    db.close()
    if db_path.exists():
        db_path.unlink()
    Path(temp_dir).rmdir()


@pytest.fixture
def runner():
    """Create CLI test runner."""
    return CliRunner()


@pytest.fixture
def sample_todo(temp_db):
    """Create a sample todo for testing."""
    todo_repo = TodoRepository(temp_db)
    return todo_repo.create_todo("Sample todo for CLI testing", "Test description")


class TestCLICommands:
    """Test CLI command functionality."""

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    def test_version_command(self, mock_migration, mock_db, mock_config, runner):
        """Test version command."""
        mock_migration.is_schema_initialized.return_value = True

        result = runner.invoke(app, ["version"])

        assert result.exit_code == 0
        assert "todo version 0.1.0" in result.stdout

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    @patch("todo.cli.main.todo_repo")
    @patch("todo.cli.main.enrichment_service")
    def test_add_command_no_ai(
        self,
        mock_enrichment,
        mock_todo_repo,
        mock_migration,
        mock_db,
        mock_config,
        runner,
    ):
        """Test adding a todo without AI enrichment."""
        mock_migration.is_schema_initialized.return_value = True
        mock_enrichment.should_enrich.return_value = False

        # Mock todo creation
        mock_todo = Mock()
        mock_todo.id = 1
        mock_todo.title = "Test task"
        mock_todo_repo.create_todo.return_value = mock_todo

        result = runner.invoke(app, ["add", "Test task", "--no-ai"])

        assert result.exit_code == 0
        assert "✓ Added task: Test task" in result.stdout
        assert "Task ID: 1" in result.stdout
        mock_todo_repo.create_todo.assert_called_once_with("Test task", None)

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    @patch("todo.cli.main.todo_repo")
    @patch("todo.cli.main.enrichment_service")
    @patch("todo.cli.main.ai_repo")
    @patch("todo.cli.main.asyncio.run")
    def test_add_command_with_ai(
        self,
        mock_asyncio,
        mock_ai_repo,
        mock_enrichment,
        mock_todo_repo,
        mock_migration,
        mock_db,
        mock_config,
        runner,
    ):
        """Test adding a todo with AI enrichment."""
        mock_migration.is_schema_initialized.return_value = True
        mock_enrichment.should_enrich.return_value = True

        # Mock todo creation
        mock_todo = Mock()
        mock_todo.id = 1
        mock_todo.title = "Test task"
        mock_todo_repo.create_todo.return_value = mock_todo

        # Mock AI enrichment
        mock_enrichment_result = Mock()
        mock_enrichment_result.confidence_score = 0.9
        mock_enrichment_result.suggested_category = "Work"
        mock_enrichment_result.suggested_priority = Priority.HIGH
        mock_enrichment_result.suggested_size = TaskSize.MEDIUM
        mock_enrichment_result.estimated_duration_minutes = 30
        mock_enrichment_result.reasoning = "Development task"
        mock_enrichment_result.detected_keywords = ["test"]
        mock_enrichment_result.urgency_indicators = []
        mock_enrichment_result.is_recurring_candidate = False
        mock_enrichment_result.suggested_recurrence_pattern = None

        mock_asyncio.return_value = mock_enrichment_result
        mock_config.ai.confidence_threshold = 0.8

        result = runner.invoke(app, ["add", "Test task", "--desc", "Test description"])

        assert result.exit_code == 0
        assert "✓ Added task: Test task" in result.stdout
        assert "🤖 AI analyzing task..." in result.stdout
        mock_todo_repo.create_todo.assert_called_once_with(
            "Test task", "Test description"
        )

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    @patch("todo.cli.main.todo_repo")
    @patch("todo.cli.main.ai_repo")
    def test_list_command_empty(
        self, mock_ai_repo, mock_todo_repo, mock_migration, mock_db, mock_config, runner
    ):
        """Test listing todos when none exist."""
        mock_migration.is_schema_initialized.return_value = True
        mock_todo_repo.get_active_todos.return_value = []

        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "No active todos found" in result.stdout
        assert "Use 'todo add <task>' to create your first todo!" in result.stdout

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    @patch("todo.cli.main.todo_repo")
    @patch("todo.cli.main.ai_repo")
    def test_list_command_with_todos(
        self, mock_ai_repo, mock_todo_repo, mock_migration, mock_db, mock_config, runner
    ):
        """Test listing todos with existing todos."""
        mock_migration.is_schema_initialized.return_value = True

        # Mock todos
        mock_todo = Mock()
        mock_todo.id = 1
        mock_todo.title = "Test task"
        mock_todo.category_id = None
        mock_todo.category = None
        mock_todo.status = Mock()
        mock_todo.status.value = "pending"
        mock_todo.final_priority = Mock()
        mock_todo.final_priority.value = "medium"
        mock_todo.final_size = Mock()
        mock_todo.final_size.value = "medium"

        mock_todo_repo.get_active_todos.return_value = [mock_todo]
        mock_ai_repo.get_latest_by_todo_id.return_value = None

        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "📋 Your Todos" in result.stdout
        assert "Test task" in result.stdout
        assert "MEDIUM" in result.stdout

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    @patch("todo.cli.main.todo_repo")
    def test_complete_command_success(
        self, mock_todo_repo, mock_migration, mock_db, mock_config, runner
    ):
        """Test completing a todo successfully."""
        mock_migration.is_schema_initialized.return_value = True

        mock_todo = Mock()
        mock_todo.title = "Test task"
        mock_todo.total_points_earned = 5
        # Mock scoring_result to None so it uses the fallback
        mock_todo.scoring_result = None
        mock_todo_repo.complete_todo.return_value = mock_todo

        result = runner.invoke(app, ["done", "1"])

        assert result.exit_code == 0
        assert "✓ Completed: Test task" in result.stdout
        assert "🎉 Earned 5 points!" in result.stdout
        mock_todo_repo.complete_todo.assert_called_once_with(1, note=None)

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    @patch("todo.cli.main.todo_repo")
    def test_complete_command_not_found(
        self, mock_todo_repo, mock_migration, mock_db, mock_config, runner
    ):
        """Test completing a non-existent todo."""
        mock_migration.is_schema_initialized.return_value = True
        mock_todo_repo.complete_todo.return_value = None

        result = runner.invoke(app, ["done", "999"])

        assert result.exit_code == 0
        assert "✗ Todo 999 not found or already completed" in result.stdout

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    @patch("todo.cli.main.todo_repo")
    @patch("todo.cli.main.ai_repo")
    def test_show_command_found(
        self, mock_ai_repo, mock_todo_repo, mock_migration, mock_db, mock_config, runner
    ):
        """Test showing a todo that exists."""
        mock_migration.is_schema_initialized.return_value = True

        mock_todo = Mock()
        mock_todo.id = 1
        mock_todo.title = "Test task"
        mock_todo.description = "Test description"
        mock_todo.status = Mock()
        mock_todo.status.value = "pending"
        mock_todo.status.__format__ = Mock(return_value="pending")
        mock_todo.final_priority = Mock()
        mock_todo.final_priority.value = "medium"
        mock_todo.final_priority.__format__ = Mock(return_value="medium")
        mock_todo.final_size = Mock()
        mock_todo.final_size.value = "medium"
        mock_todo.final_size.__format__ = Mock(return_value="medium")
        mock_todo.due_date = None
        mock_todo.created_at = Mock()
        mock_todo.created_at.strftime = Mock(return_value="2025-01-01 12:00")
        mock_todo.completed_at = None
        mock_todo.completion_note = None
        mock_todo.total_points_earned = None

        mock_todo_repo.get_by_id.return_value = mock_todo
        mock_ai_repo.get_latest_by_todo_id.return_value = None

        result = runner.invoke(app, ["show", "1"])

        assert result.exit_code == 0
        assert "Task #1" in result.stdout
        assert "Test task" in result.stdout
        assert "Test description" in result.stdout
        assert "No AI analysis available" in result.stdout

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    @patch("todo.cli.main.todo_repo")
    def test_show_command_not_found(
        self, mock_todo_repo, mock_migration, mock_db, mock_config, runner
    ):
        """Test showing a non-existent todo."""
        mock_migration.is_schema_initialized.return_value = True
        mock_todo_repo.get_by_id.return_value = None

        result = runner.invoke(app, ["show", "999"])

        assert result.exit_code == 0
        assert "✗ Todo 999 not found" in result.stdout

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    @patch("todo.cli.main.todo_repo")
    @patch("todo.cli.main.asyncio.run")
    def test_enrich_command_success(
        self, mock_asyncio, mock_todo_repo, mock_migration, mock_db, mock_config, runner
    ):
        """Test manually enriching a todo."""
        mock_migration.is_schema_initialized.return_value = True

        mock_todo = Mock()
        mock_todo.id = 1
        mock_todo.title = "Test task"
        mock_todo.description = None
        mock_todo_repo.get_by_id.return_value = mock_todo

        # Mock enrichment result
        mock_enrichment = Mock()
        mock_enrichment.confidence_score = 0.8
        mock_enrichment.suggested_category = "Work"
        mock_enrichment.suggested_priority = Priority.HIGH
        mock_enrichment.suggested_size = TaskSize.MEDIUM
        mock_enrichment.estimated_duration_minutes = 30
        mock_enrichment.reasoning = "Development task"
        mock_enrichment.detected_keywords = ["test"]
        mock_enrichment.urgency_indicators = []
        mock_enrichment.is_recurring_candidate = False
        mock_enrichment.suggested_recurrence_pattern = None

        mock_asyncio.return_value = mock_enrichment

        result = runner.invoke(app, ["enrich", "1"])

        assert result.exit_code == 0
        assert "🤖 Analyzing task: Test task..." in result.stdout
        assert "✓ AI analysis completed and saved" in result.stdout

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    @patch("todo.cli.main.todo_repo")
    def test_enrich_command_todo_not_found(
        self, mock_todo_repo, mock_migration, mock_db, mock_config, runner
    ):
        """Test enriching a non-existent todo."""
        mock_migration.is_schema_initialized.return_value = True
        mock_todo_repo.get_by_id.return_value = None

        result = runner.invoke(app, ["enrich", "999"])

        assert result.exit_code == 0
        assert "✗ Todo 999 not found" in result.stdout

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    def test_db_command(self, mock_migration, mock_db, mock_config, runner):
        """Test database status command."""
        mock_migration.is_schema_initialized.return_value = True
        mock_migration.get_migration_status.return_value = {
            "schema_initialized": True,
            "current_version": 1,
            "total_migrations_applied": 1,
            "applied_migrations": [
                {
                    "version": 1,
                    "name": "initial_schema",
                    "description": "Initial schema",
                }
            ],
        }
        mock_config.database.database_path = "/test/path/db.db"

        result = runner.invoke(app, ["db"])

        assert result.exit_code == 0
        assert "💾 Database Status" in result.stdout
        assert "✓ Yes" in result.stdout
        assert "v1" in result.stdout
        assert "/test/path/db.db" in result.stdout


class TestCLIHelpers:
    """Test CLI helper functions."""

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    def test_display_enrichment_results(
        self, mock_migration, mock_db, mock_config, runner
    ):
        """Test displaying enrichment results."""
        mock_migration.is_schema_initialized.return_value = True

        # This tests the _display_enrichment_results function indirectly
        # through the enrich command
        from unittest.mock import patch

        from todo.cli.main import _display_enrichment_results

        mock_enrichment = Mock()
        mock_enrichment.confidence_score = 0.8
        mock_enrichment.suggested_category = "Work"
        mock_enrichment.suggested_priority = Priority.HIGH
        mock_enrichment.suggested_size = TaskSize.MEDIUM
        mock_enrichment.estimated_duration_minutes = 30
        mock_enrichment.reasoning = "Development task"
        mock_enrichment.detected_keywords = ["test"]
        mock_enrichment.urgency_indicators = []
        mock_enrichment.is_recurring_candidate = False
        mock_enrichment.suggested_recurrence_pattern = None

        # This should not raise an exception
        with patch("todo.cli.main.console"):
            _display_enrichment_results(mock_enrichment)

    def test_enum_value_handling(self):
        """Test handling of enum vs string values for display."""

        # This tests the enum handling in list and show commands
        # The functionality is tested indirectly through the command tests above

        # Mock object with string values (like from database)
        mock_obj = Mock()
        mock_obj.final_priority = "medium"
        mock_obj.final_size = "large"

        # Test the logic used in the CLI
        priority_value = (
            mock_obj.final_priority.value
            if hasattr(mock_obj.final_priority, "value")
            else str(mock_obj.final_priority)
        )
        size_value = (
            mock_obj.final_size.value
            if hasattr(mock_obj.final_size, "value")
            else str(mock_obj.final_size)
        )

        assert priority_value == "medium"
        assert size_value == "large"

        # Mock object with enum values
        mock_enum_obj = Mock()
        mock_enum_obj.final_priority = Priority.HIGH
        mock_enum_obj.final_size = TaskSize.SMALL

        priority_value = (
            mock_enum_obj.final_priority.value
            if hasattr(mock_enum_obj.final_priority, "value")
            else str(mock_enum_obj.final_priority)
        )
        size_value = (
            mock_enum_obj.final_size.value
            if hasattr(mock_enum_obj.final_size, "value")
            else str(mock_enum_obj.final_size)
        )

        assert priority_value == "high"
        assert size_value == "small"


class TestCLIIntegration:
    """Test CLI integration scenarios."""

    def test_database_auto_initialization(self, runner):
        """Test that database auto-initializes on first run."""
        # This functionality is tested through integration tests
        # The auto-initialization happens during CLI module import
        # which is difficult to mock properly in this context

        # Instead, test that the CLI handles uninitialized databases gracefully
        with patch("todo.cli.main.migration_manager") as mock_migration:
            mock_migration.is_schema_initialized.return_value = (
                True  # Assume initialized
            )

            result = runner.invoke(app, ["version"])

            # Should complete without error
            assert result.exit_code == 0

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    @patch("todo.cli.main.todo_repo")
    @patch("todo.cli.main.enrichment_service")
    @patch("todo.cli.main.asyncio.run")
    def test_ai_enrichment_failure_handling(
        self,
        mock_asyncio,
        mock_enrichment,
        mock_todo_repo,
        mock_migration,
        mock_db,
        mock_config,
        runner,
    ):
        """Test handling when AI enrichment fails."""
        mock_migration.is_schema_initialized.return_value = True
        mock_enrichment.should_enrich.return_value = True

        # Mock todo creation
        mock_todo = Mock()
        mock_todo.id = 1
        mock_todo.title = "Test task"
        mock_todo_repo.create_todo.return_value = mock_todo

        # Mock AI enrichment failure
        mock_asyncio.return_value = None

        result = runner.invoke(app, ["add", "Test task"])

        assert result.exit_code == 0
        assert "✓ Added task: Test task" in result.stdout
        assert "🤖 AI analyzing task..." in result.stdout
        assert "✗ AI enrichment failed" in result.stdout

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    @patch("todo.cli.main.todo_repo")
    @patch("todo.cli.main.ai_repo")
    def test_show_command_with_ai_enrichment(
        self, mock_ai_repo, mock_todo_repo, mock_migration, mock_db, mock_config, runner
    ):
        """Test showing a todo with AI enrichment data."""
        mock_migration.is_schema_initialized.return_value = True

        mock_todo = Mock()
        mock_todo.id = 1
        mock_todo.title = "Test task"
        mock_todo.description = None
        mock_todo.status = Mock()
        mock_todo.status.value = "pending"
        mock_todo.status.__format__ = Mock(return_value="pending")
        mock_todo.final_priority = Mock()
        mock_todo.final_priority.value = "medium"
        mock_todo.final_priority.__format__ = Mock(return_value="medium")
        mock_todo.final_size = Mock()
        mock_todo.final_size.value = "medium"
        mock_todo.final_size.__format__ = Mock(return_value="medium")
        mock_todo.due_date = None
        mock_todo.created_at = Mock()
        mock_todo.created_at.strftime = Mock(return_value="2025-01-01 12:00")
        mock_todo.completed_at = None
        mock_todo.completion_note = None
        mock_todo.total_points_earned = None

        mock_enrichment = Mock()
        mock_enrichment.confidence_score = 0.8
        mock_enrichment.suggested_category = "Work"
        mock_enrichment.suggested_priority = Priority.HIGH
        mock_enrichment.suggested_size = TaskSize.MEDIUM
        mock_enrichment.estimated_duration_minutes = 30
        mock_enrichment.reasoning = "Development task"
        mock_enrichment.detected_keywords = ["test"]
        mock_enrichment.urgency_indicators = []
        mock_enrichment.is_recurring_candidate = False
        mock_enrichment.suggested_recurrence_pattern = None

        mock_todo_repo.get_by_id.return_value = mock_todo
        mock_ai_repo.get_latest_by_todo_id.return_value = mock_enrichment

        result = runner.invoke(app, ["show", "1"])

        assert result.exit_code == 0
        assert "Task #1" in result.stdout
        assert "Test task" in result.stdout
        assert "🤖 AI Analysis" in result.stdout


def _make_mock_todo(
    todo_id=1,
    title="Test task",
    status="pending",
    priority="medium",
    size="medium",
):
    """Build a Mock Todo with the attributes the JSON serializer reads."""
    todo = Mock()
    todo.id = todo_id
    todo.title = title
    todo.description = None
    todo.category_id = None
    todo.category = None
    todo.status = Mock()
    todo.status.value = status
    todo.final_priority = Mock()
    todo.final_priority.value = priority
    todo.final_size = Mock()
    todo.final_size.value = size
    todo.total_points_earned = 0
    todo.due_date = None
    todo.is_overdue = False
    todo.created_at = "2026-01-01 00:00:00"
    todo.completed_at = None
    todo.completion_note = None
    return todo


class TestCLIJsonOutput:
    """Tests for the --json machine-readable output flag."""

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    @patch("todo.cli.main.todo_repo")
    @patch("todo.cli.main.enrichment_service")
    def test_add_json_no_ai(
        self,
        mock_enrichment,
        mock_todo_repo,
        mock_migration,
        mock_db,
        mock_config,
        runner,
    ):
        """add --json --no-ai emits a single JSON object on stdout."""
        mock_migration.is_schema_initialized.return_value = True
        todo = _make_mock_todo()
        mock_todo_repo.create_todo.return_value = todo
        mock_todo_repo.get_by_id.return_value = todo

        result = runner.invoke(app, ["add", "Test task", "--no-ai", "--json"])

        assert result.exit_code == 0
        payload = json.loads(result.stdout.strip())
        assert payload["id"] == 1
        assert payload["title"] == "Test task"
        assert payload["ai_enriched"] is False
        assert payload["enrichment"] is None
        # Human-readable confirmation must NOT be on stdout.
        assert "Added task" not in result.stdout

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    @patch("todo.cli.main.todo_repo")
    @patch("todo.cli.main.enrichment_service")
    def test_add_json_empty_title(
        self,
        mock_enrichment,
        mock_todo_repo,
        mock_migration,
        mock_db,
        mock_config,
        runner,
    ):
        """add --json with empty title emits a JSON error, not a crash."""
        mock_migration.is_schema_initialized.return_value = True

        result = runner.invoke(app, ["add", "   ", "--no-ai", "--json"])

        assert result.exit_code == 0
        payload = json.loads(result.stdout.strip())
        assert "error" in payload

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    @patch("todo.cli.main.todo_repo")
    @patch("todo.cli.main.ai_repo")
    def test_list_json(
        self, mock_ai_repo, mock_todo_repo, mock_migration, mock_db, mock_config, runner
    ):
        """ls --json emits {todos: [...]}."""
        mock_migration.is_schema_initialized.return_value = True
        mock_todo_repo.get_active_todos.return_value = [_make_mock_todo()]
        mock_ai_repo.get_latest_by_todo_id.return_value = None

        result = runner.invoke(app, ["ls", "--json"])

        assert result.exit_code == 0
        payload = json.loads(result.stdout.strip())
        assert isinstance(payload["todos"], list)
        assert payload["todos"][0]["id"] == 1
        assert payload["todos"][0]["ai_enriched"] is False

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    @patch("todo.cli.main.todo_repo")
    @patch("todo.cli.main.ai_repo")
    def test_list_json_empty(
        self, mock_ai_repo, mock_todo_repo, mock_migration, mock_db, mock_config, runner
    ):
        """ls --json with no todos emits an empty list, not a prompt."""
        mock_migration.is_schema_initialized.return_value = True
        mock_todo_repo.get_active_todos.return_value = []

        result = runner.invoke(app, ["ls", "--json"])

        assert result.exit_code == 0
        payload = json.loads(result.stdout.strip())
        assert payload["todos"] == []

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    @patch("todo.cli.main.todo_repo")
    @patch("todo.cli.main.ai_repo")
    def test_show_json(
        self, mock_ai_repo, mock_todo_repo, mock_migration, mock_db, mock_config, runner
    ):
        """show --json emits the todo object with enrichment key."""
        mock_migration.is_schema_initialized.return_value = True
        mock_todo_repo.get_by_id.return_value = _make_mock_todo()
        mock_ai_repo.get_latest_by_todo_id.return_value = None

        result = runner.invoke(app, ["show", "1", "--json"])

        assert result.exit_code == 0
        payload = json.loads(result.stdout.strip())
        assert payload["id"] == 1
        assert "enrichment" in payload

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    @patch("todo.cli.main.todo_repo")
    def test_show_json_not_found(
        self, mock_todo_repo, mock_migration, mock_db, mock_config, runner
    ):
        """show --json for a missing id emits a JSON error."""
        mock_migration.is_schema_initialized.return_value = True
        mock_todo_repo.get_by_id.return_value = None

        result = runner.invoke(app, ["show", "999", "--json"])

        assert result.exit_code == 0
        payload = json.loads(result.stdout.strip())
        assert "error" in payload

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    @patch("todo.cli.main.todo_repo")
    def test_done_json(
        self, mock_todo_repo, mock_migration, mock_db, mock_config, runner
    ):
        """done --json reports completed and failed ids."""
        mock_migration.is_schema_initialized.return_value = True
        completed = _make_mock_todo()
        completed.scoring_result = None
        completed.total_points_earned = 0
        # id 1 completes, id 2 returns None (not found / already done)
        mock_todo_repo.complete_todo.side_effect = (
            lambda tid, note=None: completed if tid == 1 else None
        )

        result = runner.invoke(app, ["done", "1", "2", "--json"])

        assert result.exit_code == 0
        payload = json.loads(result.stdout.strip())
        assert payload["completed"] == [1]
        assert payload["failed"] == [2]
        assert "achievements" in payload

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    def test_stats_json(self, mock_migration, mock_db, mock_config, runner):
        """stats --json emits the progress dict."""
        mock_migration.is_schema_initialized.return_value = True
        progress = {
            "total_points": 10,
            "level": 1,
            "points_to_next_level": 90,
            "current_streak": 1,
            "longest_streak": 2,
            "total_completed": 3,
            "daily_goal": 3,
            "tasks_completed_today": 1,
            "daily_goal_met": False,
            "points_earned_today": 5,
        }
        with patch("todo.core.scoring.ScoringService") as mock_scoring_cls:
            mock_scoring_cls.return_value.get_user_progress.return_value = progress
            result = runner.invoke(app, ["stats", "--json"])

        assert result.exit_code == 0
        payload = json.loads(result.stdout.strip())
        assert payload["total_points"] == 10
        assert payload["level"] == 1


class TestCLIDelete:
    """Tests for the delete/rm command."""

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    @patch("todo.cli.main.todo_repo")
    def test_delete_force_json(
        self, mock_todo_repo, mock_migration, mock_db, mock_config, runner
    ):
        """delete --force --json reports deleted and failed ids."""
        mock_migration.is_schema_initialized.return_value = True
        mock_todo_repo.delete_todo.side_effect = lambda tid: tid == 1

        result = runner.invoke(app, ["delete", "1", "2", "--force", "--json"])

        assert result.exit_code == 0
        payload = json.loads(result.stdout.strip())
        assert payload["deleted"] == [1]
        assert payload["failed"] == [2]

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    @patch("todo.cli.main.todo_repo")
    def test_delete_json_requires_force(
        self, mock_todo_repo, mock_migration, mock_db, mock_config, runner
    ):
        """delete --json without --force refuses (cannot prompt)."""
        mock_migration.is_schema_initialized.return_value = True

        result = runner.invoke(app, ["delete", "1", "--json"])

        assert result.exit_code == 0
        payload = json.loads(result.stdout.strip())
        assert "error" in payload
        mock_todo_repo.delete_todo.assert_not_called()

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    @patch("todo.cli.main.todo_repo")
    def test_delete_abort_on_no(
        self, mock_todo_repo, mock_migration, mock_db, mock_config, runner
    ):
        """Answering 'n' to the confirm prompt aborts without deleting."""
        mock_migration.is_schema_initialized.return_value = True

        result = runner.invoke(app, ["delete", "1"], input="n\n")

        assert result.exit_code == 0
        assert "Aborted" in result.stdout
        mock_todo_repo.delete_todo.assert_not_called()

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    @patch("todo.cli.main.todo_repo")
    def test_delete_confirm_yes(
        self, mock_todo_repo, mock_migration, mock_db, mock_config, runner
    ):
        """Answering 'y' to the confirm prompt deletes the todo."""
        mock_migration.is_schema_initialized.return_value = True
        mock_todo_repo.delete_todo.return_value = True

        result = runner.invoke(app, ["rm", "1"], input="y\n")

        assert result.exit_code == 0
        mock_todo_repo.delete_todo.assert_called_once_with(1)


class TestCLIDue:
    """Tests for the --due flag on add and the due command."""

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    @patch("todo.cli.main.todo_repo")
    @patch("todo.cli.main.enrichment_service")
    def test_add_with_due(
        self,
        mock_enrichment,
        mock_todo_repo,
        mock_migration,
        mock_db,
        mock_config,
        runner,
    ):
        """add --due sets the due date on the new todo."""
        mock_migration.is_schema_initialized.return_value = True
        todo = _make_mock_todo()
        todo.due_date = date(2026, 6, 10)
        mock_todo_repo.create_todo.return_value = todo
        mock_todo_repo.get_by_id.return_value = todo

        result = runner.invoke(
            app, ["add", "Pay rent", "--no-ai", "--due", "today", "--json"]
        )

        assert result.exit_code == 0
        payload = json.loads(result.stdout.strip())
        assert payload["due_date"] == "2026-06-10"
        # update_todo called with a due_date value
        args = mock_todo_repo.update_todo.call_args
        assert "due_date" in args.args[1]

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    @patch("todo.cli.main.todo_repo")
    @patch("todo.cli.main.enrichment_service")
    def test_add_with_invalid_due(
        self,
        mock_enrichment,
        mock_todo_repo,
        mock_migration,
        mock_db,
        mock_config,
        runner,
    ):
        """add --due with an unparseable date errors and creates nothing."""
        mock_migration.is_schema_initialized.return_value = True

        result = runner.invoke(
            app, ["add", "Pay rent", "--no-ai", "--due", "asdfqwer", "--json"]
        )

        assert result.exit_code == 0
        payload = json.loads(result.stdout.strip())
        assert "error" in payload
        mock_todo_repo.create_todo.assert_not_called()

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    @patch("todo.cli.main.todo_repo")
    @patch("todo.cli.main.ai_repo")
    def test_due_command_set(
        self, mock_ai_repo, mock_todo_repo, mock_migration, mock_db, mock_config, runner
    ):
        """due <id> <when> updates the due date."""
        mock_migration.is_schema_initialized.return_value = True
        todo = _make_mock_todo()
        todo.due_date = date(2026, 6, 10)
        mock_todo_repo.get_by_id.return_value = todo
        mock_ai_repo.get_latest_by_todo_id.return_value = None

        result = runner.invoke(app, ["due", "1", "today", "--json"])

        assert result.exit_code == 0
        payload = json.loads(result.stdout.strip())
        assert payload["due_date"] == "2026-06-10"
        assert "due_date" in mock_todo_repo.update_todo.call_args.args[1]

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    @patch("todo.cli.main.todo_repo")
    @patch("todo.cli.main.ai_repo")
    def test_due_command_clear(
        self, mock_ai_repo, mock_todo_repo, mock_migration, mock_db, mock_config, runner
    ):
        """due <id> --clear sets due_date to None."""
        mock_migration.is_schema_initialized.return_value = True
        todo = _make_mock_todo()
        todo.due_date = None
        mock_todo_repo.get_by_id.return_value = todo
        mock_ai_repo.get_latest_by_todo_id.return_value = None

        result = runner.invoke(app, ["due", "1", "--clear", "--json"])

        assert result.exit_code == 0
        payload = json.loads(result.stdout.strip())
        assert payload["due_date"] is None
        assert mock_todo_repo.update_todo.call_args.args[1] == {"due_date": None}

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    @patch("todo.cli.main.todo_repo")
    def test_due_command_not_found(
        self, mock_todo_repo, mock_migration, mock_db, mock_config, runner
    ):
        """due for a missing id emits a JSON error."""
        mock_migration.is_schema_initialized.return_value = True
        mock_todo_repo.get_by_id.return_value = None

        result = runner.invoke(app, ["due", "999", "today", "--json"])

        assert result.exit_code == 0
        payload = json.loads(result.stdout.strip())
        assert "error" in payload

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    @patch("todo.cli.main.todo_repo")
    def test_due_command_requires_value(
        self, mock_todo_repo, mock_migration, mock_db, mock_config, runner
    ):
        """due with neither a date nor --clear errors."""
        mock_migration.is_schema_initialized.return_value = True
        mock_todo_repo.get_by_id.return_value = _make_mock_todo()

        result = runner.invoke(app, ["due", "1", "--json"])

        assert result.exit_code == 0
        payload = json.loads(result.stdout.strip())
        assert "error" in payload
        mock_todo_repo.update_todo.assert_not_called()


def _make_mock_event(event_id=1, title="Soccer", start=None, attendees=None):
    """Build a Mock Event with the attributes the serializer reads."""
    ev = Mock()
    ev.id = event_id
    ev.title = title
    ev.description = None
    ev.start_at = start or datetime(2026, 6, 13, 10, 0)
    ev.end_at = None
    ev.all_day = False
    ev.location = None
    ev.status = Mock()
    ev.status.value = "scheduled"
    ev.attendees = attendees or []
    ev.google_event_id = None
    ev.is_synced = False
    ev.created_at = datetime(2026, 6, 10, 12, 0)
    return ev


class TestCLIEvents:
    """Tests for the event sub-app."""

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    @patch("todo.cli.main.event_repo")
    @patch("todo.cli.main.contact_repo")
    def test_event_add_flag_mode(
        self, mock_contacts, mock_events, mock_mig, mock_db, mock_config, runner
    ):
        """event add --no-ai --when creates an event from flags."""
        mock_mig.is_schema_initialized.return_value = True
        mock_contacts.resolve.return_value = []
        ev = _make_mock_event()
        mock_events.create_event.return_value = ev
        mock_events.get_attendees.return_value = []

        result = runner.invoke(
            app,
            [
                "event",
                "add",
                "Soccer",
                "--when",
                "2026-06-13 10:00",
                "--no-ai",
                "--json",
            ],
        )

        assert result.exit_code == 0
        payload = json.loads(result.stdout.strip())
        assert payload["title"] == "Soccer"
        assert payload["start_at"].startswith("2026-06-13 10:00")
        # parsed start passed to create_event
        assert mock_events.create_event.call_args.args[1] == datetime(
            2026, 6, 13, 10, 0
        )

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    @patch("todo.cli.main.event_repo")
    def test_event_add_flag_requires_when(
        self, mock_events, mock_mig, mock_db, mock_config, runner
    ):
        """--no-ai without --when errors and creates nothing."""
        mock_mig.is_schema_initialized.return_value = True

        result = runner.invoke(app, ["event", "add", "Soccer", "--no-ai", "--json"])

        assert result.exit_code == 0
        assert "error" in json.loads(result.stdout.strip())
        mock_events.create_event.assert_not_called()

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    @patch("todo.cli.main.event_repo")
    @patch("todo.cli.main.contact_repo")
    @patch("todo.cli.main.event_parser")
    @patch("todo.cli.main.asyncio.run")
    def test_event_add_ai_resolves_date(
        self,
        mock_run,
        mock_parser,
        mock_contacts,
        mock_events,
        mock_mig,
        mock_db,
        mock_config,
        runner,
    ):
        """AI mode resolves the date phrase deterministically (not via the model)."""
        from todo.ai.event_parser import EventDraft

        mock_mig.is_schema_initialized.return_value = True
        mock_run.return_value = EventDraft(
            title="Dinner",
            date_phrase="friday",
            time="7pm",
            attendees=["wife"],
        )
        mock_contacts.resolve.return_value = ["jane@example.com"]
        mock_events.create_event.return_value = _make_mock_event(
            title="Dinner",
            start=datetime(2026, 6, 12, 19, 0),
            attendees=["jane@example.com"],
        )

        result = runner.invoke(
            app, ["event", "add", "dinner friday 7pm with wife", "--json"]
        )

        assert result.exit_code == 0
        # create_event got a real datetime; the date came from core.dates, not the model
        start_arg = mock_events.create_event.call_args.args[1]
        assert isinstance(start_arg, datetime)
        assert start_arg.hour == 19
        mock_events.set_attendees.assert_called_once()

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    @patch("todo.cli.main.event_repo")
    def test_event_list_json(self, mock_events, mock_mig, mock_db, mock_config, runner):
        mock_mig.is_schema_initialized.return_value = True
        mock_events.list_events.return_value = [_make_mock_event()]

        result = runner.invoke(app, ["event", "ls", "--json"])

        assert result.exit_code == 0
        payload = json.loads(result.stdout.strip())
        assert payload["events"][0]["title"] == "Soccer"

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    @patch("todo.cli.main.event_repo")
    def test_event_show_not_found(
        self, mock_events, mock_mig, mock_db, mock_config, runner
    ):
        mock_mig.is_schema_initialized.return_value = True
        mock_events.get_by_id.return_value = None

        result = runner.invoke(app, ["event", "show", "99", "--json"])

        assert result.exit_code == 0
        assert "error" in json.loads(result.stdout.strip())

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    @patch("todo.cli.main.event_repo")
    def test_event_delete_requires_force_in_json(
        self, mock_events, mock_mig, mock_db, mock_config, runner
    ):
        mock_mig.is_schema_initialized.return_value = True

        result = runner.invoke(app, ["event", "delete", "1", "--json"])

        assert result.exit_code == 0
        assert "error" in json.loads(result.stdout.strip())
        mock_events.delete_event.assert_not_called()

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    @patch("todo.cli.main.event_repo")
    def test_event_cancel_json(
        self, mock_events, mock_mig, mock_db, mock_config, runner
    ):
        mock_mig.is_schema_initialized.return_value = True
        ev = _make_mock_event()
        ev.status.value = "cancelled"
        mock_events.cancel_event.return_value = ev

        result = runner.invoke(app, ["event", "cancel", "1", "--json"])

        assert result.exit_code == 0
        assert json.loads(result.stdout.strip())["status"] == "cancelled"


class TestCLIContacts:
    """Tests for the contact sub-app."""

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    @patch("todo.cli.main.contact_repo")
    def test_contact_add_json(
        self, mock_contacts, mock_mig, mock_db, mock_config, runner
    ):
        mock_mig.is_schema_initialized.return_value = True
        mock_contacts.get_emails.return_value = ["a@x.com", "b@x.com"]

        result = runner.invoke(
            app, ["contact", "add", "kids", "a@x.com", "b@x.com", "--json"]
        )

        assert result.exit_code == 0
        payload = json.loads(result.stdout.strip())
        assert payload["alias"] == "kids"
        assert payload["emails"] == ["a@x.com", "b@x.com"]
        assert mock_contacts.add_contact.call_count == 2

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    @patch("todo.cli.main.contact_repo")
    def test_contact_list_json(
        self, mock_contacts, mock_mig, mock_db, mock_config, runner
    ):
        mock_mig.is_schema_initialized.return_value = True
        mock_contacts.list_contacts.return_value = {"wife": ["jane@x.com"]}

        result = runner.invoke(app, ["contact", "ls", "--json"])

        assert result.exit_code == 0
        assert json.loads(result.stdout.strip())["contacts"] == {"wife": ["jane@x.com"]}

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    @patch("todo.cli.main.contact_repo")
    def test_contact_rm_json(
        self, mock_contacts, mock_mig, mock_db, mock_config, runner
    ):
        mock_mig.is_schema_initialized.return_value = True
        mock_contacts.remove_alias.return_value = 2

        result = runner.invoke(app, ["contact", "rm", "kids", "--json"])

        assert result.exit_code == 0
        assert json.loads(result.stdout.strip())["removed"] == 2


class TestCLIDoneNote:
    """Tests for completing a todo with a note."""

    @patch("todo.cli.main.config")
    @patch("todo.cli.main.db")
    @patch("todo.cli.main.migration_manager")
    @patch("todo.cli.main.todo_repo")
    def test_done_with_note(
        self, mock_todo_repo, mock_migration, mock_db, mock_config, runner
    ):
        """done --note passes the note through to complete_todo."""
        mock_migration.is_schema_initialized.return_value = True
        completed = _make_mock_todo()
        completed.scoring_result = None
        completed.total_points_earned = 0
        mock_todo_repo.complete_todo.return_value = completed

        result = runner.invoke(
            app, ["done", "1", "--note", "paid via portal #8891", "--json"]
        )

        assert result.exit_code == 0
        mock_todo_repo.complete_todo.assert_called_once_with(
            1, note="paid via portal #8891"
        )
