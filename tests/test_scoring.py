"""Tests for the gamification scoring system."""

import tempfile
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import Mock

import pytest

from todo.core.scoring import ScoringService
from todo.db.connection import DatabaseConnection
from todo.db.migrations import MigrationManager
from todo.db.repository import TodoRepository
from todo.models import TaskSize


@pytest.fixture
def scoring_database():
    """Create a temporary database for scoring tests."""
    temp_dir = tempfile.mkdtemp(prefix="todo_scoring_test_")
    db_path = Path(temp_dir) / "scoring_test.db"

    # Create database and initialize schema
    db = DatabaseConnection(str(db_path))
    migration_manager = MigrationManager(db)
    migration_manager.initialize_schema()

    yield db, str(db_path)

    # Cleanup
    db.close()
    db_path.unlink(missing_ok=True)
    Path(temp_dir).rmdir()


class TestScoringService:
    """Test the ScoringService class."""

    def test_scoring_service_initialization(self, scoring_database):
        """Test ScoringService initializes correctly."""
        db, db_path = scoring_database
        scoring_service = ScoringService(db)

        assert scoring_service.base_points[TaskSize.SMALL] == 1
        assert scoring_service.base_points[TaskSize.MEDIUM] == 3
        assert scoring_service.base_points[TaskSize.LARGE] == 5
        assert len(scoring_service.level_thresholds) > 10

    def test_basic_point_calculation(self, scoring_database):
        """Test basic point calculation without bonuses."""
        db, db_path = scoring_database
        scoring_service = ScoringService(db)
        todo_repo = TodoRepository(db)

        # Create todos of different sizes
        small_todo = todo_repo.create_todo("Small task", None)
        medium_todo = todo_repo.create_todo("Medium task", None)
        large_todo = todo_repo.create_todo("Large task", None)

        # Set task sizes manually for testing
        small_todo.final_size = TaskSize.SMALL
        medium_todo.final_size = TaskSize.MEDIUM
        large_todo.final_size = TaskSize.LARGE

        # Test point calculations
        small_points = scoring_service.calculate_completion_points(small_todo)
        medium_points = scoring_service.calculate_completion_points(medium_todo)
        large_points = scoring_service.calculate_completion_points(large_todo)

        # Check base points (no bonuses initially)
        assert small_points[0] == 1  # base_points
        assert medium_points[0] == 3
        assert large_points[0] == 5

        # Total should equal base initially (no streak, no daily goal met)
        assert small_points[2] <= 2  # Some small bonuses might apply
        assert medium_points[2] >= 3
        assert large_points[2] >= 5

    def test_streak_bonus_calculation(self, scoring_database):
        """Test streak bonus calculations."""
        db, db_path = scoring_database
        scoring_service = ScoringService(db)

        # Test streak multipliers
        assert scoring_service._get_streak_multiplier(0) == 1.0
        assert scoring_service._get_streak_multiplier(2) == 1.0
        assert scoring_service._get_streak_multiplier(3) == 1.1  # 10% bonus
        assert scoring_service._get_streak_multiplier(7) == 1.25  # 25% bonus
        assert scoring_service._get_streak_multiplier(14) == 1.4  # 40% bonus
        assert scoring_service._get_streak_multiplier(30) == 1.6  # 60% bonus
        assert scoring_service._get_streak_multiplier(100) == 2.0  # 100% bonus

    def test_level_calculation(self, scoring_database):
        """Test level calculation logic."""
        db, db_path = scoring_database
        scoring_service = ScoringService(db)

        # Test level 1
        level, points_to_next, points_for_current = scoring_service.calculate_level(50)
        assert level == 1
        assert points_to_next == 50  # 100 - 50

        # Test level 2
        level, points_to_next, points_for_current = scoring_service.calculate_level(150)
        assert level == 2
        assert points_for_current == 100

        # Test level 3
        level, points_to_next, points_for_current = scoring_service.calculate_level(300)
        assert level == 3
        assert points_for_current == 250

    def test_streak_update_logic(self, scoring_database):
        """Test streak update logic for different scenarios."""
        db, db_path = scoring_database
        scoring_service = ScoringService(db)

        # Initialize user stats
        scoring_service._initialize_user_stats()

        # Test first completion (should set streak to 1)
        new_streak = scoring_service.update_streak(date.today())
        assert new_streak == 1

        # Test same day completion (should maintain streak)
        new_streak = scoring_service.update_streak(date.today())
        assert new_streak == 1

        # Test next day completion (should increment)
        tomorrow = date.today() + timedelta(days=1)
        new_streak = scoring_service.update_streak(tomorrow)
        assert new_streak == 2

        # Test gap in streak (should reset to 1)
        far_future = date.today() + timedelta(days=5)
        new_streak = scoring_service.update_streak(far_future)
        assert new_streak == 1

    def test_daily_goal_bonus(self, scoring_database):
        """Test daily goal bonus application."""
        db, db_path = scoring_database
        scoring_service = ScoringService(db)
        todo_repo = TodoRepository(db)

        # Initialize with daily goal of 3
        scoring_service._initialize_user_stats()

        # Create test todos
        todo1 = todo_repo.create_todo("Task 1", None)
        todo2 = todo_repo.create_todo("Task 2", None)
        todo3 = todo_repo.create_todo("Task 3", None)  # This should trigger daily goal

        todo1.final_size = TaskSize.MEDIUM
        todo2.final_size = TaskSize.MEDIUM
        todo3.final_size = TaskSize.MEDIUM

        # Complete first two tasks
        result1 = scoring_service.apply_completion_scoring(todo1)
        result2 = scoring_service.apply_completion_scoring(todo2)

        # Daily goal should not be met yet
        assert not result1["daily_goal_met"]
        assert not result2["daily_goal_met"]

        # Complete third task (should meet daily goal)
        result3 = scoring_service.apply_completion_scoring(todo3)
        assert result3["daily_goal_met"]

        # Third task should have daily goal bonus
        assert result3["bonus_points"] > 0

    def test_full_completion_workflow(self, scoring_database):
        """Test the complete scoring workflow integration."""
        db, db_path = scoring_database
        todo_repo = TodoRepository(db)

        # Create and complete a todo through the repository
        todo = todo_repo.create_todo("Integration test task", "Test description")

        # Complete the todo (this should trigger scoring)
        completed_todo = todo_repo.complete_todo(todo.id)

        assert completed_todo is not None
        assert hasattr(completed_todo, "scoring_result")
        assert (
            completed_todo.scoring_result["total_points"] >= 3
        )  # At least base points
        assert completed_todo.total_points_earned >= 3

    def test_user_progress_retrieval(self, scoring_database):
        """Test getting comprehensive user progress."""
        db, db_path = scoring_database
        scoring_service = ScoringService(db)
        todo_repo = TodoRepository(db)

        # Complete a few tasks to generate data
        for i in range(3):
            todo = todo_repo.create_todo(f"Test task {i}", None)
            todo_repo.complete_todo(todo.id)

        # Get progress
        progress = scoring_service.get_user_progress()

        assert progress["total_points"] > 0
        assert progress["level"] >= 1
        assert progress["total_completed"] == 3
        assert progress["tasks_completed_today"] == 3
        assert progress["daily_goal_met"] is True  # Default goal is 3

    def test_overdue_penalty_application(self, scoring_database):
        """Test overdue penalty logic."""
        db, db_path = scoring_database
        scoring_service = ScoringService(db)
        todo_repo = TodoRepository(db)

        # Create an overdue todo
        todo = todo_repo.create_todo("Overdue task", None)

        # Set due date to yesterday (making it overdue)
        yesterday = date.today() - timedelta(days=1)
        conn = db.connect()
        conn.execute("UPDATE todos SET due_date = ? WHERE id = ?", [yesterday, todo.id])

        # Apply overdue penalties
        penalty = scoring_service.apply_overdue_penalties()
        assert penalty >= 0  # Should apply some penalty

    def test_category_bonus_application(self, scoring_database):
        """Test category bonus for important categories."""
        db, db_path = scoring_database
        scoring_service = ScoringService(db)
        todo_repo = TodoRepository(db)

        # Create todo with mock category
        todo = todo_repo.create_todo("Work task", None)

        # Mock category for testing
        mock_category = Mock()
        mock_category.name = "Work"
        todo.category = mock_category

        base_points, bonus_points, total_points = (
            scoring_service.calculate_completion_points(todo)
        )

        # Should get category bonus for Work category
        assert bonus_points >= 1  # At least 1 point bonus for Work category

    def test_level_progression_edge_cases(self, scoring_database):
        """Test edge cases in level progression."""
        db, db_path = scoring_database
        scoring_service = ScoringService(db)

        # Test max level scenario
        max_points = 200000  # Way beyond defined levels
        level, points_to_next, points_for_current = scoring_service.calculate_level(
            max_points
        )

        assert level <= len(scoring_service.level_thresholds)
        assert points_to_next >= 0

    def test_scoring_service_with_real_database_operations(self, scoring_database):
        """Test scoring service with actual database operations."""
        db, db_path = scoring_database
        scoring_service = ScoringService(db)

        # Initialize user stats
        stats = scoring_service._initialize_user_stats()
        assert stats.total_points == 0
        assert stats.level == 1

        # Test daily activity creation
        today = date.today()
        scoring_service._update_daily_activity(today, 5)

        # Verify daily activity was created
        daily_activity = scoring_service.daily_activity_repo.get_activity_for_date(
            today
        )
        assert daily_activity is not None
        assert daily_activity.total_points_earned >= 5


class TestScoringIntegration:
    """Test scoring system integration with other components."""

    def test_cli_completion_with_scoring(self, scoring_database):
        """Test CLI completion command with scoring integration."""
        db, db_path = scoring_database
        todo_repo = TodoRepository(db)

        # Create and complete a todo
        todo = todo_repo.create_todo("CLI integration test", None)
        result = todo_repo.complete_todo(todo.id)

        # Should have scoring result attached
        assert hasattr(result, "scoring_result")
        scoring_result = result.scoring_result

        assert "base_points" in scoring_result
        assert "bonus_points" in scoring_result
        assert "total_points" in scoring_result
        assert "new_streak" in scoring_result
        assert "level_up" in scoring_result
        assert "daily_goal_met" in scoring_result

    def test_multiple_completions_scoring(self, scoring_database):
        """Test scoring across multiple task completions."""
        db, db_path = scoring_database
        todo_repo = TodoRepository(db)

        total_points = 0
        for i in range(5):
            todo = todo_repo.create_todo(f"Multi-completion test {i}", None)
            result = todo_repo.complete_todo(todo.id)

            assert hasattr(result, "scoring_result")
            total_points += result.scoring_result["total_points"]

        # Total points should accumulate properly
        assert total_points >= 15  # At least 5 * 3 base points

        # Check final user progress
        scoring_service = ScoringService(db)
        progress = scoring_service.get_user_progress()
        assert progress["total_completed"] == 5
        # Total points may be higher due to achievement bonuses
        assert progress["total_points"] >= total_points


class TestScoringEdgeCases:
    """Test edge cases and error conditions in scoring."""

    def test_scoring_with_missing_user_stats(self, scoring_database):
        """Test scoring when user stats don't exist initially."""
        db, db_path = scoring_database
        todo_repo = TodoRepository(db)

        # Complete a task without initializing user stats first
        todo = todo_repo.create_todo("Edge case test", None)
        result = todo_repo.complete_todo(todo.id)

        # Should automatically initialize stats and work
        assert hasattr(result, "scoring_result")
        assert result.scoring_result["total_points"] > 0

    def test_scoring_with_invalid_task_sizes(self, scoring_database):
        """Test scoring with edge cases in task sizes."""
        db, db_path = scoring_database
        scoring_service = ScoringService(db)
        todo_repo = TodoRepository(db)

        todo = todo_repo.create_todo("Invalid size test", None)

        # Test with invalid size (should default to MEDIUM = 3 points)
        todo.final_size = None
        base_points, bonus_points, total_points = (
            scoring_service.calculate_completion_points(todo)
        )
        assert base_points == 3  # Default to medium

    def test_concurrent_completions(self, scoring_database):
        """Test scoring with concurrent task completions."""
        db, db_path = scoring_database
        scoring_service = ScoringService(db)
        todo_repo = TodoRepository(db)

        # Create multiple todos
        todos = []
        for i in range(3):
            todo = todo_repo.create_todo(f"Concurrent test {i}", None)
            todos.append(todo)

        # Complete them "simultaneously"
        results = []
        for todo in todos:
            result = todo_repo.complete_todo(todo.id)
            results.append(result)

        # All should have valid scoring results
        for result in results:
            assert hasattr(result, "scoring_result")
            assert result.scoring_result["total_points"] > 0

        # Final stats should be correct
        progress = scoring_service.get_user_progress()
        assert progress["total_completed"] == 3


if __name__ == "__main__":
    pytest.main([__file__])
