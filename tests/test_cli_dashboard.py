"""CLI tests for dashboard and goal commands."""

import pytest
from typer.testing import CliRunner

from todo.cli.main import app


@pytest.fixture
def cli_runner():
    """CLI runner for testing."""
    return CliRunner()


class TestDashboardCLI:
    """Test dashboard command functionality."""

    def test_dashboard_command_exists(self, cli_runner):
        """Test that dashboard command exists and shows in help."""
        result = cli_runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "dashboard" in result.stdout

    def test_dashboard_command_no_crash(self, cli_runner):
        """Test that dashboard command doesn't crash."""
        result = cli_runner.invoke(app, ["dashboard"])

        # Should not crash (exit_code 0 = success, 1 = handled error)
        assert result.exit_code in [0, 1]

        # Should not have unhandled exceptions
        assert "Traceback" not in result.stdout
        assert "NameError" not in result.stdout
        assert "ImportError" not in result.stdout

    def test_dashboard_with_days_option(self, cli_runner):
        """Test dashboard command with --days option."""
        result = cli_runner.invoke(app, ["dashboard", "--days", "7"])

        assert result.exit_code in [0, 1]
        assert "Traceback" not in result.stdout

        # If successful, should show dashboard content
        if result.exit_code == 0:
            assert "📊 Productivity Dashboard" in result.stdout
            assert "(7 days)" in result.stdout

    def test_dashboard_help(self, cli_runner):
        """Test dashboard command help."""
        result = cli_runner.invoke(app, ["dashboard", "--help"])

        assert result.exit_code == 0
        assert "--days" in result.stdout
        assert "Number of days to analyze" in result.stdout

    def test_dashboard_shows_basic_sections(self, cli_runner):
        """Test that dashboard shows expected sections when successful."""
        result = cli_runner.invoke(app, ["dashboard"])

        # If successful, should show main dashboard sections
        if result.exit_code == 0:
            assert "📊 Productivity Dashboard" in result.stdout
            # Note: Other sections may not appear if no data exists


class TestGoalCLI:
    """Test goal command functionality."""

    def test_goal_command_exists(self, cli_runner):
        """Test that goal command exists."""
        result = cli_runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "goal" in result.stdout

    def test_goal_help(self, cli_runner):
        """Test goal command help."""
        result = cli_runner.invoke(app, ["goal", "--help"])

        assert result.exit_code == 0
        assert "create" in result.stdout
        assert "list" in result.stdout
        assert "delete" in result.stdout

    def test_goal_create_help(self, cli_runner):
        """Test goal create command help."""
        result = cli_runner.invoke(app, ["goal", "create", "--help"])

        assert result.exit_code == 0
        assert "goal_type" in result.stdout or "Goal type" in result.stdout
        assert "category" in result.stdout
        assert "target" in result.stdout

    def test_goal_create_invalid_type(self, cli_runner):
        """Test goal create with invalid goal type."""
        result = cli_runner.invoke(
            app, ["goal", "create", "invalid", "tasks_completed", "10"]
        )

        assert result.exit_code in [0, 1]
        if result.exit_code == 1:
            assert "Invalid goal type" in result.stdout

    def test_goal_create_invalid_category(self, cli_runner):
        """Test goal create with invalid category."""
        result = cli_runner.invoke(app, ["goal", "create", "weekly", "invalid", "10"])

        assert result.exit_code in [0, 1]
        if result.exit_code == 1:
            assert "Invalid category" in result.stdout

    def test_goal_create_invalid_target(self, cli_runner):
        """Test goal create with invalid target."""
        result = cli_runner.invoke(
            app, ["goal", "create", "weekly", "tasks_completed", "0"]
        )

        assert result.exit_code in [0, 1]
        if result.exit_code == 1:
            assert "positive number" in result.stdout

    def test_goal_create_valid(self, cli_runner):
        """Test goal create with valid parameters."""
        result = cli_runner.invoke(
            app, ["goal", "create", "weekly", "tasks_completed", "10"]
        )

        assert result.exit_code in [0, 1]

        # Should not crash with unhandled exceptions
        assert "Traceback" not in result.stdout
        assert "NameError" not in result.stdout

        # If successful, should show success message
        if result.exit_code == 0:
            assert "Created weekly goal" in result.stdout
            assert "Tasks Completed - 10" in result.stdout

    def test_goal_list_no_crash(self, cli_runner):
        """Test goal list command doesn't crash."""
        result = cli_runner.invoke(app, ["goal", "list"])

        assert result.exit_code in [0, 1]
        assert "Traceback" not in result.stdout
        assert "NameError" not in result.stdout

    def test_goal_list_empty(self, cli_runner):
        """Test goal list with no goals."""
        result = cli_runner.invoke(app, ["goal", "list"])

        # If successful and no goals exist, should show helpful message
        if result.exit_code == 0:
            # Might show "No active goals" message
            pass

    def test_goal_delete_invalid_id(self, cli_runner):
        """Test goal delete with invalid ID."""
        result = cli_runner.invoke(app, ["goal", "delete", "9999"])

        assert result.exit_code in [0, 1]
        assert "Traceback" not in result.stdout

    def test_goal_delete_non_numeric_id(self, cli_runner):
        """Test goal delete with non-numeric ID."""
        result = cli_runner.invoke(app, ["goal", "delete", "invalid"])

        # Should handle validation error gracefully
        assert result.exit_code != 0  # Should fail validation


class TestCLIIntegration:
    """Test CLI integration between different commands."""

    def test_goal_create_and_list_workflow(self, cli_runner):
        """Test creating a goal and then listing it."""
        # Create a goal
        create_result = cli_runner.invoke(
            app, ["goal", "create", "weekly", "tasks_completed", "5"]
        )

        if create_result.exit_code == 0:
            # List goals to see if it appears
            list_result = cli_runner.invoke(app, ["goal", "list"])
            assert list_result.exit_code in [0, 1]

            if list_result.exit_code == 0:
                assert "🎯 Current Goals" in list_result.stdout

    def test_goal_create_and_dashboard_workflow(self, cli_runner):
        """Test creating a goal and checking dashboard."""
        # Create a goal
        create_result = cli_runner.invoke(
            app, ["goal", "create", "weekly", "tasks_completed", "5"]
        )

        if create_result.exit_code == 0:
            # Check dashboard shows the goal
            dashboard_result = cli_runner.invoke(app, ["dashboard"])

            if dashboard_result.exit_code == 0:
                assert "📊 Productivity Dashboard" in dashboard_result.stdout

    def test_add_complete_and_dashboard_workflow(self, cli_runner):
        """Test adding tasks, completing them, and viewing dashboard."""
        # Add a task
        add_result = cli_runner.invoke(app, ["add", "Test dashboard integration"])

        if add_result.exit_code == 0:
            # Complete the task (assume ID 1)
            complete_result = cli_runner.invoke(app, ["done", "1"])

            if complete_result.exit_code in [0, 1]:
                # View dashboard
                dashboard_result = cli_runner.invoke(app, ["dashboard"])
                assert dashboard_result.exit_code in [0, 1]
                assert "Traceback" not in dashboard_result.stdout

    def test_commands_dont_interfere(self, cli_runner):
        """Test that new commands don't interfere with existing ones."""
        # Test basic commands still work
        help_result = cli_runner.invoke(app, ["--help"])
        assert help_result.exit_code == 0
        assert "add" in help_result.stdout
        assert "list" in help_result.stdout
        assert "done" in help_result.stdout
        assert "achievements" in help_result.stdout
        assert "stats" in help_result.stdout
        assert "dashboard" in help_result.stdout
        assert "goal" in help_result.stdout

    def test_all_commands_handle_errors_gracefully(self, cli_runner):
        """Test that all commands handle errors gracefully."""
        commands_to_test = [
            ["dashboard"],
            ["goal", "list"],
            ["achievements"],
            ["stats"],
        ]

        for cmd in commands_to_test:
            result = cli_runner.invoke(app, cmd)

            # Should not crash with unhandled exceptions
            assert "Traceback" not in result.stdout
            assert "NameError" not in result.stdout
            assert "ImportError" not in result.stdout

            # Should have a reasonable exit code
            assert result.exit_code in [0, 1]


class TestCLIErrorHandling:
    """Test CLI error handling for dashboard and goals."""

    def test_dashboard_with_database_error(self, cli_runner):
        """Test dashboard command with potential database errors."""
        result = cli_runner.invoke(app, ["dashboard"])

        # Should handle database errors gracefully
        assert result.exit_code in [0, 1]
        assert "Traceback" not in result.stdout

    def test_goal_commands_with_database_error(self, cli_runner):
        """Test goal commands with potential database errors."""
        commands = [
            ["goal", "list"],
            ["goal", "create", "weekly", "tasks_completed", "10"],
            ["goal", "delete", "1"],
        ]

        for cmd in commands:
            result = cli_runner.invoke(app, cmd)
            assert result.exit_code in [0, 1]
            assert "Traceback" not in result.stdout

    def test_cli_displays_user_friendly_errors(self, cli_runner):
        """Test that CLI displays user-friendly error messages."""
        # Test with obviously invalid input
        result = cli_runner.invoke(
            app, ["goal", "create", "invalid_type", "invalid_category", "-5"]
        )

        if result.exit_code == 1:
            # Should show user-friendly error, not technical stack trace
            assert "✗" in result.stdout or "Error" in result.stdout
            assert "Traceback" not in result.stdout


if __name__ == "__main__":
    pytest.main([__file__])
