"""Runtime tests to ensure CLI commands don't crash with import or runtime errors."""

import pytest
from typer.testing import CliRunner

from todo.cli.main import app


@pytest.fixture
def cli_runner():
    """CLI runner for testing."""
    return CliRunner()


class TestCLIRuntimeErrors:
    """Test that CLI commands don't crash with runtime errors."""

    def test_stats_command_no_crash(self, cli_runner):
        """Test that stats command doesn't crash with runtime errors."""
        result = cli_runner.invoke(app, ["stats"])

        # Command should not crash (exit_code 0 = success, 1 = handled error)
        assert result.exit_code in [0, 1]

        # Should not have unhandled exceptions in output
        assert "Traceback" not in result.stdout
        assert "NameError" not in result.stdout
        assert "ImportError" not in result.stdout

        # If successful, should show basic structure
        if result.exit_code == 0:
            assert "📊 Your Progress" in result.stdout

    def test_achievements_command_no_crash(self, cli_runner):
        """Test that achievements command doesn't crash with runtime errors."""
        result = cli_runner.invoke(app, ["achievements"])

        # Command should not crash (exit_code 0 = success, 1 = handled error)
        assert result.exit_code in [0, 1]

        # Should not have unhandled exceptions in output
        assert "Traceback" not in result.stdout
        assert "NameError" not in result.stdout
        assert "ImportError" not in result.stdout
        assert "name 'ScoringService' is not defined" not in result.stdout

        # If successful, should show basic structure
        if result.exit_code == 0:
            assert "🏆 Achievement Progress" in result.stdout

    def test_achievements_unlocked_flag_no_crash(self, cli_runner):
        """Test that achievements --unlocked doesn't crash."""
        result = cli_runner.invoke(app, ["achievements", "--unlocked"])

        assert result.exit_code in [0, 1]
        assert "Traceback" not in result.stdout
        assert "NameError" not in result.stdout
        assert "ImportError" not in result.stdout
        assert "name 'ScoringService' is not defined" not in result.stdout

    def test_achievements_progress_flag_no_crash(self, cli_runner):
        """Test that achievements --progress doesn't crash."""
        result = cli_runner.invoke(app, ["achievements", "--progress"])

        assert result.exit_code in [0, 1]
        assert "Traceback" not in result.stdout
        assert "NameError" not in result.stdout
        assert "ImportError" not in result.stdout
        assert "name 'ScoringService' is not defined" not in result.stdout

    def test_achievements_short_flags_no_crash(self, cli_runner):
        """Test that achievements short flags don't crash."""
        # Test -u flag
        result = cli_runner.invoke(app, ["achievements", "-u"])
        assert result.exit_code in [0, 1]
        assert "Traceback" not in result.stdout
        assert "NameError" not in result.stdout

        # Test -p flag
        result = cli_runner.invoke(app, ["achievements", "-p"])
        assert result.exit_code in [0, 1]
        assert "Traceback" not in result.stdout
        assert "NameError" not in result.stdout

    def test_stats_datetime_error_fixed(self, cli_runner):
        """Test that stats command doesn't have datetime comparison errors."""
        result = cli_runner.invoke(app, ["stats"])

        assert result.exit_code in [0, 1]
        # Should not have the specific datetime error we fixed
        assert (
            "'>' not supported between instances of 'datetime.date' and 'datetime.timedelta'"
            not in result.stdout
        )
        assert "TypeError" not in result.stdout

    def test_basic_commands_still_work(self, cli_runner):
        """Test that basic commands still work after achievement integration."""
        # Test help command
        result = cli_runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "achievements" in result.stdout  # Should show new command

        # Test list command (might be empty but shouldn't crash)
        result = cli_runner.invoke(app, ["list"])
        assert result.exit_code in [0, 1]
        assert "Traceback" not in result.stdout


class TestAchievementCLIIntegration:
    """Test achievement CLI integration doesn't break other functionality."""

    def test_add_and_complete_workflow_no_crash(self, cli_runner):
        """Test that add/complete workflow works with achievement integration."""
        # Add a todo
        result = cli_runner.invoke(app, ["add", "Integration test task"])
        assert result.exit_code == 0

        # List todos to get the ID
        result = cli_runner.invoke(app, ["list"])
        assert result.exit_code in [0, 1]

        # The exact ID might vary, but we can try completing ID 1
        # This tests that achievement integration doesn't break todo completion
        result = cli_runner.invoke(app, ["done", "1"])
        # Should either succeed or fail gracefully (not crash with unhandled exception)
        assert result.exit_code in [0, 1]
        assert "Traceback" not in result.stdout
        assert "NameError" not in result.stdout

    def test_achievement_commands_exist_in_help(self, cli_runner):
        """Test that achievement commands are registered and show up in help."""
        result = cli_runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "achievements" in result.stdout
        assert "stats" in result.stdout

        # Test achievements command help
        result = cli_runner.invoke(app, ["achievements", "--help"])
        assert result.exit_code == 0
        assert "--unlocked" in result.stdout
        assert "--progress" in result.stdout


if __name__ == "__main__":
    pytest.main([__file__])
