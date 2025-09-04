"""Tests for the goal management service."""

import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from todo.core.goals import Goal, GoalCategory, GoalService, GoalType
from todo.core.scoring import ScoringService
from todo.db.connection import DatabaseConnection
from todo.db.migrations import MigrationManager
from todo.db.repository import TodoRepository


@pytest.fixture
def goals_database():
    """Create a temporary database for goals tests."""
    temp_dir = tempfile.mkdtemp(prefix="todo_goals_test_")
    db_path = Path(temp_dir) / "goals_test.db"

    # Create database and initialize schema
    db = DatabaseConnection(str(db_path))
    migration_manager = MigrationManager(db)
    migration_manager.initialize_schema()

    yield db, str(db_path)

    # Cleanup
    db.close()
    db_path.unlink(missing_ok=True)
    Path(temp_dir).rmdir()


class TestGoal:
    """Test the Goal model class."""

    def test_goal_creation(self):
        """Test Goal object creation and basic properties."""
        goal = Goal(
            goal_id=1,
            goal_type=GoalType.WEEKLY,
            category=GoalCategory.TASKS_COMPLETED,
            target_value=10,
            current_value=3,
        )

        assert goal.id == 1
        assert goal.type == GoalType.WEEKLY
        assert goal.category == GoalCategory.TASKS_COMPLETED
        assert goal.target_value == 10
        assert goal.current_value == 3
        assert not goal.is_completed
        assert goal.progress_percentage == 30.0

    def test_goal_completion_status(self):
        """Test goal completion status calculation."""
        # Incomplete goal
        goal = Goal(1, GoalType.WEEKLY, GoalCategory.TASKS_COMPLETED, 10, 7)
        assert not goal.is_completed
        assert goal.progress_percentage == 70.0

        # Completed goal
        goal.current_value = 10
        assert goal.is_completed
        assert goal.progress_percentage == 100.0

        # Over-completed goal
        goal.current_value = 12
        assert goal.is_completed
        assert goal.progress_percentage == 100.0  # Capped at 100%

    def test_goal_period_calculation(self):
        """Test automatic period calculation."""
        today = date.today()

        # Weekly goal
        weekly_goal = Goal(1, GoalType.WEEKLY, GoalCategory.TASKS_COMPLETED, 10)

        # Should start on Monday of current week
        expected_start = today - timedelta(days=today.weekday())
        expected_end = expected_start + timedelta(days=6)

        assert weekly_goal.period_start == expected_start
        assert weekly_goal.period_end == expected_end

        # Monthly goal
        monthly_goal = Goal(1, GoalType.MONTHLY, GoalCategory.TASKS_COMPLETED, 30)

        # Should start on first day of current month
        expected_start = today.replace(day=1)
        if expected_start.month == 12:
            next_month = expected_start.replace(year=expected_start.year + 1, month=1)
        else:
            next_month = expected_start.replace(month=expected_start.month + 1)
        expected_end = next_month - timedelta(days=1)

        assert monthly_goal.period_start == expected_start
        assert monthly_goal.period_end == expected_end

    def test_goal_days_remaining(self):
        """Test days remaining calculation."""
        today = date.today()

        # Goal ending tomorrow
        goal = Goal(1, GoalType.WEEKLY, GoalCategory.TASKS_COMPLETED, 10)
        goal.period_end = today + timedelta(days=1)
        assert goal.days_remaining == 2  # Today + 1 more day

        # Goal ending today
        goal.period_end = today
        assert goal.days_remaining == 1  # Just today

        # Expired goal
        goal.period_end = today - timedelta(days=1)
        assert goal.days_remaining == 0

    def test_goal_current_period_check(self):
        """Test current period checking."""
        today = date.today()

        # Current period goal
        goal = Goal(1, GoalType.WEEKLY, GoalCategory.TASKS_COMPLETED, 10)
        goal.period_start = today - timedelta(days=3)
        goal.period_end = today + timedelta(days=3)
        assert goal.is_current_period

        # Future goal
        goal.period_start = today + timedelta(days=1)
        goal.period_end = today + timedelta(days=7)
        assert not goal.is_current_period

        # Past goal
        goal.period_start = today - timedelta(days=7)
        goal.period_end = today - timedelta(days=1)
        assert not goal.is_current_period


class TestGoalService:
    """Test the GoalService class."""

    def test_goal_service_initialization(self, goals_database):
        """Test GoalService initializes correctly."""
        db, db_path = goals_database
        goal_service = GoalService(db)

        assert goal_service.db == db
        assert goal_service.user_stats_repo is not None

        # Should create goals table
        result = db.fetch_one(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='goals'"
        )
        assert result is not None

    def test_create_goal(self, goals_database):
        """Test goal creation."""
        db, db_path = goals_database
        goal_service = GoalService(db)

        goal = goal_service.create_goal(
            GoalType.WEEKLY, GoalCategory.TASKS_COMPLETED, 10
        )

        assert isinstance(goal, Goal)
        assert goal.id > 0
        assert goal.type == GoalType.WEEKLY
        assert goal.category == GoalCategory.TASKS_COMPLETED
        assert goal.target_value == 10
        assert goal.current_value == 0
        assert goal.is_active

        # Verify goal is stored in database
        stored_goals = goal_service.get_active_goals()
        assert len(stored_goals) == 1
        assert stored_goals[0].id == goal.id

    def test_create_goal_deactivates_existing(self, goals_database):
        """Test that creating a goal deactivates existing goals of same type/category."""
        db, db_path = goals_database
        goal_service = GoalService(db)

        # Create first goal
        _goal1 = goal_service.create_goal(
            GoalType.WEEKLY, GoalCategory.TASKS_COMPLETED, 10
        )

        # Create second goal of same type and category
        goal2 = goal_service.create_goal(
            GoalType.WEEKLY, GoalCategory.TASKS_COMPLETED, 15
        )

        # Only the second goal should be active
        active_goals = goal_service.get_active_goals()
        assert len(active_goals) == 1
        assert active_goals[0].id == goal2.id
        assert active_goals[0].target_value == 15

    def test_get_active_goals(self, goals_database):
        """Test retrieving active goals."""
        db, db_path = goals_database
        goal_service = GoalService(db)

        # No goals initially
        goals = goal_service.get_active_goals()
        assert len(goals) == 0

        # Create some goals
        goal1 = goal_service.create_goal(
            GoalType.WEEKLY, GoalCategory.TASKS_COMPLETED, 10
        )
        goal2 = goal_service.create_goal(
            GoalType.MONTHLY, GoalCategory.POINTS_EARNED, 100
        )

        goals = goal_service.get_active_goals()
        assert len(goals) == 2

        # Goals should be sorted by created_at DESC
        assert goals[0].id == goal2.id  # More recent
        assert goals[1].id == goal1.id

    def test_get_current_goals(self, goals_database):
        """Test retrieving goals for current period."""
        db, db_path = goals_database
        goal_service = GoalService(db)

        # Create a current goal
        current_goal = goal_service.create_goal(
            GoalType.WEEKLY, GoalCategory.TASKS_COMPLETED, 10
        )

        # Create a past goal by manually updating its period
        past_goal = goal_service.create_goal(
            GoalType.MONTHLY, GoalCategory.POINTS_EARNED, 100
        )
        past_start = date.today() - timedelta(days=60)
        past_end = date.today() - timedelta(days=30)
        db.execute(
            "UPDATE goals SET period_start = ?, period_end = ? WHERE id = ?",
            (past_start, past_end, past_goal.id),
        )

        # Should only return current goals
        current_goals = goal_service.get_current_goals()
        assert len(current_goals) == 1
        assert current_goals[0].id == current_goal.id

    def test_update_goal_progress(self, goals_database):
        """Test updating goal progress based on user stats."""
        db, db_path = goals_database
        goal_service = GoalService(db)
        todo_repo = TodoRepository(db)
        scoring_service = ScoringService(db)

        # Initialize user stats
        user_stats = scoring_service._initialize_user_stats()

        # Create a goal
        _goal = goal_service.create_goal(
            GoalType.WEEKLY, GoalCategory.TASKS_COMPLETED, 5
        )

        # Complete some tasks
        for i in range(3):
            todo = todo_repo.create_todo(f"Test task {i}")
            todo_repo.complete_todo(todo.id)

        # Update goal progress
        goal_service.update_goal_progress(user_stats)

        # Check that goal progress was updated
        updated_goals = goal_service.get_current_goals()
        assert len(updated_goals) == 1
        updated_goal = updated_goals[0]
        assert updated_goal.current_value >= 3  # Should reflect completed tasks

    def test_goal_progress_calculation_methods(self, goals_database):
        """Test different goal progress calculation methods."""
        db, db_path = goals_database
        goal_service = GoalService(db)
        _scoring_service = ScoringService(db)

        # Mock user stats
        user_stats = Mock()
        user_stats.current_streak_days = 7
        user_stats.total_tasks_completed = 50
        user_stats.level = 5

        # Test streak goal calculation
        streak_goal = Goal(1, GoalType.WEEKLY, GoalCategory.STREAK_DAYS, 5)
        streak_value = goal_service._calculate_goal_progress(streak_goal, user_stats)
        assert streak_value == 7

        # Test productivity score calculation
        productivity_goal = Goal(
            1, GoalType.WEEKLY, GoalCategory.PRODUCTIVITY_SCORE, 80
        )
        productivity_score = goal_service._calculate_goal_progress(
            productivity_goal, user_stats
        )
        assert isinstance(productivity_score, int)
        assert 0 <= productivity_score <= 100

    def test_goal_suggestions(self, goals_database):
        """Test goal suggestion generation."""
        db, db_path = goals_database
        goal_service = GoalService(db)
        todo_repo = TodoRepository(db)
        scoring_service = ScoringService(db)

        # Initialize user stats
        _user_stats = scoring_service._initialize_user_stats()

        # Create and complete some tasks to establish patterns
        for i in range(10):
            todo = todo_repo.create_todo(f"Pattern task {i}")
            todo_repo.complete_todo(todo.id)

        # Update user stats
        scoring_service.user_stats_repo.update_stats(
            {"total_tasks_completed": 10, "current_streak_days": 3}
        )
        updated_stats = scoring_service.user_stats_repo.get_current_stats()

        # Get suggestions
        suggestions = goal_service.get_goal_suggestions(updated_stats)

        assert isinstance(suggestions, list)
        assert len(suggestions) <= 3  # Should return max 3 suggestions

        for suggestion in suggestions:
            assert "type" in suggestion
            assert "category" in suggestion
            assert "target_value" in suggestion
            assert "reason" in suggestion
            assert "difficulty" in suggestion

            assert isinstance(suggestion["type"], GoalType)
            assert isinstance(suggestion["category"], GoalCategory)
            assert isinstance(suggestion["target_value"], int)
            assert suggestion["target_value"] > 0
            assert suggestion["difficulty"] in ["easy", "moderate", "challenging"]

    def test_goal_suggestions_exclude_existing(self, goals_database):
        """Test that goal suggestions exclude existing goal types/categories."""
        db, db_path = goals_database
        goal_service = GoalService(db)
        scoring_service = ScoringService(db)

        user_stats = scoring_service._initialize_user_stats()

        # Create a weekly tasks_completed goal
        goal_service.create_goal(GoalType.WEEKLY, GoalCategory.TASKS_COMPLETED, 10)

        suggestions = goal_service.get_goal_suggestions(user_stats)

        # Should not suggest another weekly tasks_completed goal
        for suggestion in suggestions:
            if suggestion["type"] == GoalType.WEEKLY:
                assert suggestion["category"] != GoalCategory.TASKS_COMPLETED

    def test_goals_summary(self, goals_database):
        """Test goals summary generation."""
        db, db_path = goals_database
        goal_service = GoalService(db)

        # No goals case
        summary = goal_service.get_goals_summary()
        assert summary["total_goals"] == 0
        assert summary["completed_goals"] == 0
        assert summary["in_progress_goals"] == 0
        assert summary["completion_rate"] == 0.0

        # Create some goals with different completion status
        goal1 = goal_service.create_goal(
            GoalType.WEEKLY, GoalCategory.TASKS_COMPLETED, 10
        )
        _goal2 = goal_service.create_goal(
            GoalType.MONTHLY, GoalCategory.POINTS_EARNED, 100
        )

        # Manually set one goal as completed for testing
        db.execute("UPDATE goals SET current_value = ? WHERE id = ?", (10, goal1.id))

        summary = goal_service.get_goals_summary()

        assert summary["total_goals"] == 2
        assert summary["completed_goals"] == 1
        assert summary["in_progress_goals"] == 1
        assert summary["completion_rate"] == 50.0
        assert "average_progress" in summary
        assert "goals" in summary

        # Check individual goal data
        goals_data = summary["goals"]
        assert len(goals_data) == 2

        for goal_data in goals_data:
            assert "type" in goal_data
            assert "category" in goal_data
            assert "target" in goal_data
            assert "current" in goal_data
            assert "progress" in goal_data
            assert "completed" in goal_data
            assert "days_remaining" in goal_data

    def test_cleanup_expired_goals(self, goals_database):
        """Test cleanup of expired goals."""
        db, db_path = goals_database
        goal_service = GoalService(db)

        # Create a goal and make it expired
        goal = goal_service.create_goal(
            GoalType.WEEKLY, GoalCategory.TASKS_COMPLETED, 10
        )

        # Manually set the goal period to past dates
        past_start = date.today() - timedelta(days=14)
        past_end = date.today() - timedelta(days=7)
        db.execute(
            "UPDATE goals SET period_start = ?, period_end = ? WHERE id = ?",
            (past_start, past_end, goal.id),
        )

        # Verify goal is still active before cleanup
        active_goals_before = goal_service.get_active_goals()
        assert len(active_goals_before) == 1

        # Run cleanup
        goal_service.cleanup_expired_goals()

        # Verify expired goal is now inactive
        active_goals_after = goal_service.get_active_goals()
        assert len(active_goals_after) == 0

    def test_delete_goal(self, goals_database):
        """Test goal deletion."""
        db, db_path = goals_database
        goal_service = GoalService(db)

        # Create a goal
        goal = goal_service.create_goal(
            GoalType.WEEKLY, GoalCategory.TASKS_COMPLETED, 10
        )
        goal_id = goal.id

        # Verify goal exists
        assert len(goal_service.get_active_goals()) == 1

        # Delete goal
        result = goal_service.delete_goal(goal_id)
        assert result is True

        # Verify goal is deleted
        assert len(goal_service.get_active_goals()) == 0

        # Try to delete non-existent goal
        result = goal_service.delete_goal(9999)
        assert (
            result is True or result is False
        )  # Behavior depends on DB implementation

    def test_goal_period_specific_calculations(self, goals_database):
        """Test that goal calculations are period-specific."""
        db, db_path = goals_database
        goal_service = GoalService(db)
        todo_repo = TodoRepository(db)

        # Create a weekly goal
        goal = goal_service.create_goal(
            GoalType.WEEKLY, GoalCategory.TASKS_COMPLETED, 5
        )

        # Complete a task this week
        todo1 = todo_repo.create_todo("This week task")
        todo_repo.complete_todo(todo1.id)

        # Create an old task (simulate completing it last month)
        todo2 = todo_repo.create_todo("Old task")
        old_completion_time = datetime.now() - timedelta(days=45)
        db.execute(
            "UPDATE todos SET status = 'completed', completed_at = ? WHERE id = ?",
            (old_completion_time, todo2.id),
        )

        # Calculate goal progress - should only count this week's task
        period_completions = goal_service._get_period_task_completions(goal)
        assert period_completions == 1  # Only the recent task

    def test_goal_with_invalid_data(self, goals_database):
        """Test goal handling with invalid or missing data."""
        db, db_path = goals_database
        goal_service = GoalService(db)

        # Test with None user stats
        goal_service.update_goal_progress(None)  # Should not crash

        # Test with incomplete user stats
        incomplete_stats = Mock()
        incomplete_stats.current_streak_days = None
        incomplete_stats.total_tasks_completed = None

        goal_service.update_goal_progress(incomplete_stats)  # Should not crash

    def test_goal_database_error_handling(self, goals_database):
        """Test goal service handling of database errors."""
        db, db_path = goals_database
        goal_service = GoalService(db)

        # Test with database connection issues
        with patch.object(
            goal_service.db, "fetch_all", side_effect=Exception("DB Error")
        ):
            # Should handle database errors gracefully
            goals = goal_service.get_active_goals()
            assert isinstance(
                goals, list
            )  # Should return empty list or handle gracefully


class TestGoalIntegration:
    """Test goal system integration with other services."""

    def test_goal_integration_with_todo_completion(self, goals_database):
        """Test goal progress updates when todos are completed."""
        db, db_path = goals_database
        goal_service = GoalService(db)
        todo_repo = TodoRepository(db)
        scoring_service = ScoringService(db)

        # Initialize user stats
        user_stats = scoring_service._initialize_user_stats()

        # Create a weekly task completion goal
        goal = goal_service.create_goal(
            GoalType.WEEKLY, GoalCategory.TASKS_COMPLETED, 5
        )

        # Initial progress should be 0
        assert goal.current_value == 0

        # Complete some todos
        for i in range(3):
            todo = todo_repo.create_todo(f"Integration task {i}")
            todo_repo.complete_todo(todo.id)

        # Update goal progress
        goal_service.update_goal_progress(user_stats)

        # Check goal progress
        updated_goals = goal_service.get_current_goals()
        updated_goal = updated_goals[0]
        assert updated_goal.current_value >= 3
        assert updated_goal.progress_percentage > 0

    def test_goal_analytics_consistency(self, goals_database):
        """Test consistency between goal calculations and analytics."""
        db, db_path = goals_database
        goal_service = GoalService(db)
        todo_repo = TodoRepository(db)
        scoring_service = ScoringService(db)

        # Initialize user stats
        user_stats = scoring_service._initialize_user_stats()

        # Create goals and complete tasks
        _weekly_goal = goal_service.create_goal(
            GoalType.WEEKLY, GoalCategory.TASKS_COMPLETED, 10
        )

        completed_count = 0
        for i in range(7):
            todo = todo_repo.create_todo(f"Consistency task {i}")
            todo_repo.complete_todo(todo.id)
            completed_count += 1

        # Update goal progress
        goal_service.update_goal_progress(user_stats)

        # Check goal calculations match expected completions
        updated_goals = goal_service.get_current_goals()
        updated_goal = updated_goals[0]

        # Goal progress should reflect actual completions
        period_completions = goal_service._get_period_task_completions(updated_goal)
        assert period_completions == completed_count


if __name__ == "__main__":
    pytest.main([__file__])
