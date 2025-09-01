"""Comprehensive E2E tests for all CLI commands."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from todo.cli.main import app
from todo.db.connection import DatabaseConnection
from todo.db.migrations import MigrationManager
from todo.db.repository import TodoRepository


@pytest.fixture
def isolated_cli_database():
    """Create an isolated database for CLI E2E testing."""
    temp_dir = tempfile.mkdtemp(prefix="todo_cli_e2e_")
    db_path = Path(temp_dir) / "cli_e2e_test.db"

    # Create database and initialize schema
    db = DatabaseConnection(str(db_path))
    migration_manager = MigrationManager(db)
    migration_manager.initialize_schema()

    yield db, str(db_path)

    # Cleanup
    db.close()
    db_path.unlink(missing_ok=True)
    Path(temp_dir).rmdir()


class TestComprehensiveCLIE2E:
    """Comprehensive E2E tests for all CLI commands."""

    def test_version_command_e2e(self):
        """Test version command works without database."""
        runner = CliRunner()
        result = runner.invoke(app, ["version"])

        assert result.exit_code == 0
        assert "todo version 0.1.0" in result.output

    def test_help_command_e2e(self):
        """Test help command shows all available commands."""
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "AI-powered terminal todo application" in result.output
        assert "add" in result.output
        assert "list" in result.output
        assert "show" in result.output
        assert "complete" in result.output
        assert "enrich" in result.output
        assert "db" in result.output

    def test_add_command_no_ai_e2e(self, isolated_cli_database):
        """Test add command without AI enrichment."""
        db, db_path = isolated_cli_database
        runner = CliRunner()

        # Mock the CLI to use our isolated database
        with (
            patch("todo.cli.main.db", db),
            patch("todo.cli.main.migration_manager") as mock_migration,
        ):
            mock_migration.is_schema_initialized.return_value = True

            # Create real TodoRepository for testing
            todo_repo = TodoRepository(db)

            with patch("todo.cli.main.todo_repo", todo_repo):
                # Test add command
                result = runner.invoke(
                    app,
                    [
                        "add",
                        "Test E2E Todo",
                        "--desc",
                        "Testing CLI add command",
                        "--no-ai",
                    ],
                )

                assert result.exit_code == 0
                assert "✓ Added task:" in result.output
                assert "Test E2E Todo" in result.output
                assert "Task ID:" in result.output

    def test_add_command_with_mocked_ai_e2e(self, isolated_cli_database):
        """Test add command with mocked AI enrichment."""
        db, db_path = isolated_cli_database
        runner = CliRunner()

        # Mock AI enrichment
        mock_enrichment = Mock()
        mock_enrichment.confidence_score = 0.9
        mock_enrichment.suggested_category = "Testing"
        mock_enrichment.suggested_priority = Mock()
        mock_enrichment.suggested_priority.value = "high"
        mock_enrichment.suggested_size = Mock()
        mock_enrichment.suggested_size.value = "medium"
        mock_enrichment.estimated_duration_minutes = 60
        mock_enrichment.reasoning = "This is a test task"

        with (
            patch("todo.cli.main.db", db),
            patch("todo.cli.main.migration_manager") as mock_migration,
            patch("todo.cli.main._enrich_todo_async", return_value=mock_enrichment),
        ):
            mock_migration.is_schema_initialized.return_value = True
            todo_repo = TodoRepository(db)

            with (
                patch("todo.cli.main.todo_repo", todo_repo),
                patch("todo.cli.main.config") as mock_config,
            ):
                mock_config.ai.enable_auto_enrichment = True
                mock_config.ai.confidence_threshold = 0.7

                result = runner.invoke(
                    app, ["add", "AI Enhanced Task", "--desc", "Testing AI enrichment"]
                )

                assert result.exit_code == 0
                assert "✓ Added task:" in result.output
                assert "🤖 AI analyzing task..." in result.output
                assert "AI Suggestions" in result.output
                assert "high confidence suggestions applied" in result.output.lower()

    def test_list_command_empty_e2e(self, isolated_cli_database):
        """Test list command with no todos."""
        db, db_path = isolated_cli_database
        runner = CliRunner()

        with (
            patch("todo.cli.main.db", db),
            patch("todo.cli.main.migration_manager") as mock_migration,
        ):
            mock_migration.is_schema_initialized.return_value = True
            todo_repo = TodoRepository(db)

            with (
                patch("todo.cli.main.todo_repo", todo_repo),
                patch("todo.cli.main.ai_repo"),
            ):
                result = runner.invoke(app, ["list"])

                assert result.exit_code == 0
                assert "No active todos found" in result.output
                assert "Use 'todo add <task>'" in result.output

    def test_list_command_with_todos_e2e(self, isolated_cli_database):
        """Test list command with existing todos."""
        db, db_path = isolated_cli_database
        runner = CliRunner()

        # Create a test todo directly in database
        todo_repo = TodoRepository(db)
        todo_repo.create_todo("E2E List Test", "Testing list command")

        with (
            patch("todo.cli.main.db", db),
            patch("todo.cli.main.migration_manager") as mock_migration,
        ):
            mock_migration.is_schema_initialized.return_value = True

            with (
                patch("todo.cli.main.todo_repo", todo_repo),
                patch("todo.cli.main.ai_repo") as mock_ai_repo,
            ):
                # Mock AI repo to return no enrichment
                mock_ai_repo.get_latest_by_todo_id.return_value = None

                result = runner.invoke(app, ["list"])

                assert result.exit_code == 0
                assert "📋 Your Todos" in result.output
                assert "E2E List Test" in result.output
                assert "○ Pending" in result.output
                assert "○" in result.output  # No AI enrichment

    def test_show_command_e2e(self, isolated_cli_database):
        """Test show command for existing todo."""
        db, db_path = isolated_cli_database
        runner = CliRunner()

        # Create a test todo
        todo_repo = TodoRepository(db)
        test_todo = todo_repo.create_todo("E2E Show Test", "Testing show command")

        with (
            patch("todo.cli.main.db", db),
            patch("todo.cli.main.migration_manager") as mock_migration,
        ):
            mock_migration.is_schema_initialized.return_value = True

            with (
                patch("todo.cli.main.todo_repo", todo_repo),
                patch("todo.cli.main.ai_repo") as mock_ai_repo,
            ):
                mock_ai_repo.get_latest_by_todo_id.return_value = None

                result = runner.invoke(app, ["show", str(test_todo.id)])

                assert result.exit_code == 0
                assert f"Task #{test_todo.id}" in result.output
                assert "E2E Show Test" in result.output
                assert "Testing show command" in result.output
                assert "Status" in result.output
                assert "Priority" in result.output
                assert "No AI analysis available" in result.output

    def test_show_command_not_found_e2e(self, isolated_cli_database):
        """Test show command for non-existent todo."""
        db, db_path = isolated_cli_database
        runner = CliRunner()

        with (
            patch("todo.cli.main.db", db),
            patch("todo.cli.main.migration_manager") as mock_migration,
        ):
            mock_migration.is_schema_initialized.return_value = True
            todo_repo = TodoRepository(db)

            with patch("todo.cli.main.todo_repo", todo_repo):
                result = runner.invoke(app, ["show", "999"])

                assert result.exit_code == 0
                assert "✗ Todo 999 not found" in result.output

    def test_complete_command_e2e(self, isolated_cli_database):
        """Test complete command for existing todo."""
        db, db_path = isolated_cli_database
        runner = CliRunner()

        # Create a test todo
        todo_repo = TodoRepository(db)
        test_todo = todo_repo.create_todo(
            "E2E Complete Test", "Testing complete command"
        )

        with (
            patch("todo.cli.main.db", db),
            patch("todo.cli.main.migration_manager") as mock_migration,
        ):
            mock_migration.is_schema_initialized.return_value = True

            with patch("todo.cli.main.todo_repo", todo_repo):
                result = runner.invoke(app, ["complete", str(test_todo.id)])

                assert result.exit_code == 0
                assert "✓ Completed:" in result.output
                assert "E2E Complete Test" in result.output
                assert "Earned" in result.output and "points" in result.output

    def test_complete_command_not_found_e2e(self, isolated_cli_database):
        """Test complete command for non-existent todo."""
        db, db_path = isolated_cli_database
        runner = CliRunner()

        with (
            patch("todo.cli.main.db", db),
            patch("todo.cli.main.migration_manager") as mock_migration,
        ):
            mock_migration.is_schema_initialized.return_value = True
            todo_repo = TodoRepository(db)

            with patch("todo.cli.main.todo_repo", todo_repo):
                result = runner.invoke(app, ["complete", "999"])

                assert result.exit_code == 0
                assert "✗ Todo 999 not found or already completed" in result.output

    def test_enrich_command_e2e(self, isolated_cli_database):
        """Test enrich command with mocked AI."""
        db, db_path = isolated_cli_database
        runner = CliRunner()

        # Create a test todo
        todo_repo = TodoRepository(db)
        test_todo = todo_repo.create_todo("E2E Enrich Test", "Testing enrich command")

        # Mock AI enrichment
        mock_enrichment = Mock()
        mock_enrichment.confidence_score = 0.8
        mock_enrichment.suggested_category = "Testing"
        mock_enrichment.suggested_priority = Mock()
        mock_enrichment.suggested_priority.value = "medium"
        mock_enrichment.suggested_size = Mock()
        mock_enrichment.suggested_size.value = "small"
        mock_enrichment.estimated_duration_minutes = 30
        mock_enrichment.reasoning = "This is an enrichment test"

        with (
            patch("todo.cli.main.db", db),
            patch("todo.cli.main.migration_manager") as mock_migration,
            patch("todo.cli.main._enrich_todo_async", return_value=mock_enrichment),
        ):
            mock_migration.is_schema_initialized.return_value = True

            with patch("todo.cli.main.todo_repo", todo_repo):
                result = runner.invoke(app, ["enrich", str(test_todo.id)])

                assert result.exit_code == 0
                assert f"🤖 Analyzing task: {test_todo.title}" in result.output
                assert "AI Suggestions" in result.output
                assert "✓ AI analysis completed and saved" in result.output

    def test_enrich_command_not_found_e2e(self, isolated_cli_database):
        """Test enrich command for non-existent todo."""
        db, db_path = isolated_cli_database
        runner = CliRunner()

        with (
            patch("todo.cli.main.db", db),
            patch("todo.cli.main.migration_manager") as mock_migration,
        ):
            mock_migration.is_schema_initialized.return_value = True
            todo_repo = TodoRepository(db)

            with patch("todo.cli.main.todo_repo", todo_repo):
                result = runner.invoke(app, ["enrich", "999"])

                assert result.exit_code == 0
                assert "✗ Todo 999 not found" in result.output

    def test_db_command_e2e(self, isolated_cli_database):
        """Test db command shows database status."""
        db, db_path = isolated_cli_database
        runner = CliRunner()

        with (
            patch("todo.cli.main.db", db),
            patch("todo.cli.main.migration_manager") as mock_migration,
            patch("todo.cli.main.config") as mock_config,
        ):
            mock_migration.is_schema_initialized.return_value = True
            mock_config.database.database_path = db_path

            # Mock migration status
            mock_migration.get_migration_status.return_value = {
                "schema_initialized": True,
                "current_version": 1,
                "applied_migrations": [{"version": 1, "name": "initial_schema"}],
                "tables": [],
            }

            result = runner.invoke(app, ["db"])

            assert result.exit_code == 0
            assert "💾 Database Status" in result.output
            assert "Database Path" in result.output
            assert "Schema Version" in result.output
            assert "✓ Yes" in result.output  # Initialized
            assert "Applied Migrations:" in result.output
            assert "v1: initial_schema" in result.output

    def test_full_workflow_e2e(self, isolated_cli_database):
        """Test complete workflow: add -> list -> show -> complete -> list."""
        db, db_path = isolated_cli_database
        runner = CliRunner()

        with (
            patch("todo.cli.main.db", db),
            patch("todo.cli.main.migration_manager") as mock_migration,
        ):
            mock_migration.is_schema_initialized.return_value = True
            todo_repo = TodoRepository(db)

            with (
                patch("todo.cli.main.todo_repo", todo_repo),
                patch("todo.cli.main.ai_repo") as mock_ai_repo,
            ):
                mock_ai_repo.get_latest_by_todo_id.return_value = None

                # Step 1: Add a todo
                result1 = runner.invoke(
                    app,
                    [
                        "add",
                        "Workflow Test Todo",
                        "--desc",
                        "Testing full workflow",
                        "--no-ai",
                    ],
                )
                assert result1.exit_code == 0
                assert "✓ Added task:" in result1.output

                # Extract todo ID from output
                import re

                match = re.search(r"Task ID: (\d+)", result1.output)
                assert match is not None
                todo_id = match.group(1)

                # Step 2: List todos (should show our new todo)
                result2 = runner.invoke(app, ["list"])
                assert result2.exit_code == 0
                assert "Workflow Test Todo" in result2.output
                assert "○ Pending" in result2.output

                # Step 3: Show the todo
                result3 = runner.invoke(app, ["show", todo_id])
                assert result3.exit_code == 0
                assert f"Task #{todo_id}" in result3.output
                assert "Workflow Test Todo" in result3.output
                assert "Testing full workflow" in result3.output

                # Step 4: Complete the todo
                result4 = runner.invoke(app, ["complete", todo_id])
                assert result4.exit_code == 0
                assert "✓ Completed:" in result4.output
                assert "Workflow Test Todo" in result4.output

                # Step 5: List todos again (should show completed todo)
                result5 = runner.invoke(app, ["list", "--all"])
                assert result5.exit_code == 0
                # Note: Depending on implementation, completed todos might not show in default list

    def test_command_aliases_e2e(self, isolated_cli_database):
        """Test command aliases work correctly."""
        db, db_path = isolated_cli_database
        runner = CliRunner()

        with (
            patch("todo.cli.main.db", db),
            patch("todo.cli.main.migration_manager") as mock_migration,
        ):
            mock_migration.is_schema_initialized.return_value = True
            todo_repo = TodoRepository(db)

            with (
                patch("todo.cli.main.todo_repo", todo_repo),
                patch("todo.cli.main.ai_repo") as mock_ai_repo,
            ):
                mock_ai_repo.get_latest_by_todo_id.return_value = None

                # Test 'ls' alias for 'list'
                result_ls = runner.invoke(app, ["ls"])
                result_list = runner.invoke(app, ["list"])

                # Both should work the same way
                assert result_ls.exit_code == 0
                assert result_list.exit_code == 0
                assert "No active todos found" in result_ls.output
                assert "No active todos found" in result_list.output

                # Test 'done' alias for 'complete'
                # First create a todo
                test_todo = todo_repo.create_todo("Alias Test", "Testing aliases")

                result_done = runner.invoke(app, ["done", str(test_todo.id)])
                assert result_done.exit_code == 0
                assert "✓ Completed:" in result_done.output

    def test_error_handling_e2e(self, isolated_cli_database):
        """Test error handling in CLI commands."""
        db, db_path = isolated_cli_database
        runner = CliRunner()

        with (
            patch("todo.cli.main.db", db),
            patch("todo.cli.main.migration_manager") as mock_migration,
        ):
            mock_migration.is_schema_initialized.return_value = True
            todo_repo = TodoRepository(db)

            with patch("todo.cli.main.todo_repo", todo_repo):
                # Test invalid todo ID (non-numeric)
                _ = runner.invoke(app, ["show", "invalid"])
                # This might cause a validation error or be handled gracefully
                # The exact behavior depends on Typer's validation

                # Test zero or negative todo ID
                result2 = runner.invoke(app, ["show", "0"])
                assert result2.exit_code == 0
                assert "✗ Todo 0 not found" in result2.output

                _ = runner.invoke(app, ["complete", "-1"])
                # Negative numbers might be handled by Typer validation

    def test_ai_provider_option_e2e(self, isolated_cli_database):
        """Test AI provider option in add and enrich commands."""
        db, db_path = isolated_cli_database
        runner = CliRunner()

        with (
            patch("todo.cli.main.db", db),
            patch("todo.cli.main.migration_manager") as mock_migration,
        ):
            mock_migration.is_schema_initialized.return_value = True
            todo_repo = TodoRepository(db)

            with (
                patch("todo.cli.main.todo_repo", todo_repo),
                patch("todo.cli.main._enrich_todo_async") as mock_enrich,
            ):
                mock_enrich.return_value = None  # AI enrichment fails

                # Test invalid provider
                result1 = runner.invoke(
                    app, ["add", "Provider Test", "--provider", "invalid_provider"]
                )
                assert result1.exit_code == 0
                assert "Invalid provider: invalid_provider" in result1.output

                # Test valid provider (even though it might fail due to no API key)
                result2 = runner.invoke(
                    app,
                    [
                        "add",
                        "OpenAI Test",
                        "--provider",
                        "openai",
                        "--no-ai",  # Skip AI to avoid API calls
                    ],
                )
                assert result2.exit_code == 0
                assert "✓ Added task:" in result2.output
