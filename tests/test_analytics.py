"""Tests for the analytics service."""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from todo.core.analytics import AnalyticsService
from todo.core.scoring import ScoringService
from todo.db.connection import DatabaseConnection
from todo.db.migrations import MigrationManager
from todo.db.repository import TodoRepository


@pytest.fixture
def analytics_database():
    """Create a temporary database for analytics tests."""
    temp_dir = tempfile.mkdtemp(prefix="todo_analytics_test_")
    db_path = Path(temp_dir) / "analytics_test.db"

    # Create database and initialize schema
    db = DatabaseConnection(str(db_path))
    migration_manager = MigrationManager(db)
    migration_manager.initialize_schema()

    yield db, str(db_path)

    # Cleanup
    db.close()
    db_path.unlink(missing_ok=True)
    Path(temp_dir).rmdir()


class TestAnalyticsService:
    """Test the AnalyticsService class."""

    def test_analytics_service_initialization(self, analytics_database):
        """Test AnalyticsService initializes correctly."""
        db, db_path = analytics_database
        analytics_service = AnalyticsService(db)

        assert analytics_service.db == db
        assert analytics_service.user_stats_repo is not None

    def test_productivity_report_generation(self, analytics_database):
        """Test productivity report generation."""
        db, db_path = analytics_database
        analytics_service = AnalyticsService(db)
        todo_repo = TodoRepository(db)
        _scoring_service = ScoringService(db)

        # Initialize user stats
        _scoring_service._initialize_user_stats()

        # Create some test todos
        todo1 = todo_repo.create_todo("Test task 1")
        todo2 = todo_repo.create_todo("Test task 2")
        _todo3 = todo_repo.create_todo("Test task 3")

        # Complete some todos
        todo_repo.complete_todo(todo1.id)
        todo_repo.complete_todo(todo2.id)

        # Generate report
        report = analytics_service.generate_productivity_report(days=30)

        # Verify report structure
        assert isinstance(report, dict)
        assert "total_completed" in report
        assert "total_created" in report
        assert "completion_rate" in report
        assert "current_streak" in report
        assert "total_points" in report
        assert "category_breakdown" in report
        assert "trend" in report
        assert "insights" in report

        # Verify basic calculations
        assert report["total_completed"] >= 2
        assert report["total_created"] >= 3
        assert isinstance(report["completion_rate"], float)
        assert 0 <= report["completion_rate"] <= 100

    def test_weekly_summary(self, analytics_database):
        """Test weekly summary generation."""
        db, db_path = analytics_database
        analytics_service = AnalyticsService(db)
        todo_repo = TodoRepository(db)

        # Create and complete some todos
        todo1 = todo_repo.create_todo("Weekly test task")
        todo_repo.complete_todo(todo1.id)

        weekly_summary = analytics_service.get_weekly_summary()

        assert isinstance(weekly_summary, dict)
        assert "current_week" in weekly_summary
        assert "previous_week" in weekly_summary

        current_week = weekly_summary["current_week"]
        assert "week_start" in current_week
        assert "week_end" in current_week
        assert "completed_tasks" in current_week
        assert "points_earned" in current_week
        assert "active_days" in current_week

        # Verify current week has at least one completion
        assert current_week["completed_tasks"] >= 1

    def test_monthly_summary(self, analytics_database):
        """Test monthly summary generation."""
        db, db_path = analytics_database
        analytics_service = AnalyticsService(db)
        todo_repo = TodoRepository(db)

        # Create and complete some todos
        todo1 = todo_repo.create_todo("Monthly test task")
        todo_repo.complete_todo(todo1.id)

        monthly_summary = analytics_service.get_monthly_summary()

        assert isinstance(monthly_summary, dict)
        assert "current_month" in monthly_summary
        assert "previous_month" in monthly_summary

        current_month = monthly_summary["current_month"]
        assert "month_start" in current_month
        assert "month_end" in current_month
        assert "completed_tasks" in current_month
        assert "points_earned" in current_month
        assert "active_days" in current_month

    def test_category_breakdown(self, analytics_database):
        """Test category breakdown analysis."""
        db, db_path = analytics_database
        analytics_service = AnalyticsService(db)
        todo_repo = TodoRepository(db)

        # Create todos with different categories (simulated by setting category in todo)
        todo1 = todo_repo.create_todo("Work task")
        todo2 = todo_repo.create_todo("Personal task")

        # Manually set categories (in real app, these would be set by AI enrichment)
        db.execute("UPDATE todos SET category = ? WHERE id = ?", ("work", todo1.id))
        db.execute("UPDATE todos SET category = ? WHERE id = ?", ("personal", todo2.id))

        todo_repo.complete_todo(todo1.id)
        todo_repo.complete_todo(todo2.id)

        breakdown = analytics_service._get_category_breakdown(days=30)

        assert isinstance(breakdown, list)
        assert len(breakdown) >= 2

        for category_data in breakdown:
            assert "category" in category_data
            assert "count" in category_data
            assert "percentage" in category_data
            assert isinstance(category_data["count"], int)
            assert isinstance(category_data["percentage"], float)
            assert 0 <= category_data["percentage"] <= 100

    def test_streak_analysis(self, analytics_database):
        """Test streak analysis."""
        db, db_path = analytics_database
        analytics_service = AnalyticsService(db)
        _scoring_service = ScoringService(db)

        # Initialize user stats with a streak
        _scoring_service._initialize_user_stats()
        _scoring_service.user_stats_repo.update_stats({"current_streak_days": 5})

        streak_analysis = analytics_service.get_streak_analysis()

        assert isinstance(streak_analysis, dict)
        assert "current_streak" in streak_analysis
        assert "longest_streak" in streak_analysis
        assert "streak_history" in streak_analysis

        assert streak_analysis["current_streak"] >= 0
        assert isinstance(streak_analysis["streak_history"], list)

    def test_completion_patterns(self, analytics_database):
        """Test completion pattern analysis."""
        db, db_path = analytics_database
        analytics_service = AnalyticsService(db)
        todo_repo = TodoRepository(db)

        # Create and complete todos at different times
        todo1 = todo_repo.create_todo("Pattern test 1")
        todo2 = todo_repo.create_todo("Pattern test 2")

        todo_repo.complete_todo(todo1.id)
        todo_repo.complete_todo(todo2.id)

        patterns = analytics_service._analyze_completion_patterns(days=30)

        assert isinstance(patterns, dict)
        assert "by_day_of_week" in patterns
        assert "by_hour" in patterns
        assert "peak_productivity_day" in patterns
        assert "peak_productivity_hour" in patterns

        # Verify day of week data
        day_data = patterns["by_day_of_week"]
        assert isinstance(day_data, list)
        assert len(day_data) == 7  # 7 days of the week

        for day_info in day_data:
            assert "day" in day_info
            assert "count" in day_info
            assert isinstance(day_info["count"], int)

    def test_trend_analysis(self, analytics_database):
        """Test trend analysis calculations."""
        db, db_path = analytics_database
        analytics_service = AnalyticsService(db)
        todo_repo = TodoRepository(db)

        # Create todos over time to establish a trend
        for i in range(10):
            todo = todo_repo.create_todo(f"Trend test {i}")
            todo_repo.complete_todo(todo.id)

        trend = analytics_service._calculate_trend(days=30)

        assert isinstance(trend, dict)
        assert "direction" in trend
        assert "slope" in trend
        assert "confidence" in trend

        assert trend["direction"] in ["improving", "declining", "stable"]
        assert isinstance(trend["slope"], float)
        assert isinstance(trend["confidence"], float)
        assert 0 <= trend["confidence"] <= 1

    def test_insights_generation(self, analytics_database):
        """Test insights generation."""
        db, db_path = analytics_database
        analytics_service = AnalyticsService(db)
        todo_repo = TodoRepository(db)
        _scoring_service = ScoringService(db)

        # Initialize stats and complete some tasks
        _user_stats = _scoring_service._initialize_user_stats()

        todo1 = todo_repo.create_todo("Insight test")
        todo_repo.complete_todo(todo1.id)

        # Update stats to trigger insights
        _scoring_service.user_stats_repo.update_stats(
            {"total_tasks_completed": 10, "current_streak_days": 3}
        )
        updated_stats = _scoring_service.user_stats_repo.get_current_stats()

        insights = analytics_service._generate_insights(updated_stats, days=30)

        assert isinstance(insights, list)
        # Should have some insights based on the data
        for insight in insights:
            assert isinstance(insight, str)
            assert len(insight) > 0

    def test_productivity_score_calculation(self, analytics_database):
        """Test productivity score calculation."""
        db, db_path = analytics_database
        analytics_service = AnalyticsService(db)
        _scoring_service = ScoringService(db)

        # Create mock user stats
        user_stats = Mock()
        user_stats.total_tasks_completed = 50
        user_stats.current_streak_days = 7
        user_stats.level = 5

        score = analytics_service._calculate_productivity_score(user_stats)

        assert isinstance(score, int)
        assert 0 <= score <= 100

    def test_empty_database_handling(self, analytics_database):
        """Test analytics with empty database."""
        db, db_path = analytics_database
        analytics_service = AnalyticsService(db)
        _scoring_service = ScoringService(db)

        # Initialize empty user stats
        _user_stats = _scoring_service._initialize_user_stats()

        # Should handle empty database gracefully
        report = analytics_service.generate_productivity_report(days=30)

        assert isinstance(report, dict)
        assert report["total_completed"] == 0
        assert report["total_created"] == 0
        assert report["completion_rate"] == 0
        assert report["category_breakdown"] == []

        weekly = analytics_service.get_weekly_summary()
        assert weekly["current_week"]["completed_tasks"] == 0
        assert weekly["previous_week"]["completed_tasks"] == 0

    def test_date_range_filtering(self, analytics_database):
        """Test that analytics correctly filter by date range."""
        db, db_path = analytics_database
        analytics_service = AnalyticsService(db)
        todo_repo = TodoRepository(db)

        # Create an old todo (outside range)
        old_todo = todo_repo.create_todo("Old task")

        # Simulate old completion by updating the completed_at timestamp
        old_date = datetime.now() - timedelta(days=60)
        db.execute(
            "UPDATE todos SET status = 'completed', completed_at = ? WHERE id = ?",
            (old_date, old_todo.id),
        )

        # Create a recent todo (inside range)
        recent_todo = todo_repo.create_todo("Recent task")
        todo_repo.complete_todo(recent_todo.id)

        # Test 30-day report (should only include recent todo)
        report = analytics_service.generate_productivity_report(days=30)

        # Should only count the recent completion
        assert report["total_completed"] == 1

        # Test 90-day report (should include both)
        report_90 = analytics_service.generate_productivity_report(days=90)
        assert report_90["total_completed"] == 2

    def test_analytics_with_database_errors(self, analytics_database):
        """Test analytics handling of database errors."""
        db, db_path = analytics_database
        analytics_service = AnalyticsService(db)

        # Test with database connection issues
        with patch.object(
            analytics_service.db,
            "fetch_all",
            side_effect=Exception("DB Connection Error"),
        ):
            # Should handle database errors gracefully
            report = analytics_service.generate_productivity_report(days=30)

            # Should return default values when DB fails
            assert isinstance(report, dict)
            # Most values should be defaults when DB fails
            assert report["total_completed"] == 0
            assert report["total_created"] == 0

    def test_performance_with_large_dataset(self, analytics_database):
        """Test analytics performance with larger dataset."""
        db, db_path = analytics_database
        analytics_service = AnalyticsService(db)
        todo_repo = TodoRepository(db)

        # Create a larger number of todos
        for i in range(100):
            todo = todo_repo.create_todo(f"Performance test task {i}")
            if i % 2 == 0:  # Complete half of them
                todo_repo.complete_todo(todo.id)

        # Should handle larger dataset efficiently
        report = analytics_service.generate_productivity_report(days=30)

        assert report["total_completed"] == 50
        assert report["total_created"] == 100
        assert report["completion_rate"] == 50.0

        # All operations should complete without timeout
        weekly = analytics_service.get_weekly_summary()
        monthly = analytics_service.get_monthly_summary()
        streak = analytics_service.get_streak_analysis()

        # Verify all operations completed
        assert isinstance(weekly, dict)
        assert isinstance(monthly, dict)
        assert isinstance(streak, dict)


class TestAnalyticsIntegration:
    """Test analytics integration with other services."""

    def test_analytics_with_scoring_integration(self, analytics_database):
        """Test analytics integration with scoring service."""
        db, db_path = analytics_database
        analytics_service = AnalyticsService(db)
        _scoring_service = ScoringService(db)
        todo_repo = TodoRepository(db)

        # Initialize user stats
        _user_stats = _scoring_service._initialize_user_stats()

        # Complete some todos to generate scoring data
        todo1 = todo_repo.create_todo("Integration test 1")
        todo2 = todo_repo.create_todo("Integration test 2")

        completed_todo1 = todo_repo.complete_todo(todo1.id)
        completed_todo2 = todo_repo.complete_todo(todo2.id)

        # Verify scoring results exist
        assert hasattr(completed_todo1, "scoring_result")
        assert hasattr(completed_todo2, "scoring_result")

        # Get updated stats
        _scoring_service.user_stats_repo.get_current_stats()

        # Generate analytics report
        report = analytics_service.generate_productivity_report(days=30)

        # Verify analytics includes scoring data
        assert report["total_completed"] >= 2
        assert report["total_points"] > 0  # Should have points from completions

    def test_analytics_data_consistency(self, analytics_database):
        """Test data consistency between analytics and other services."""
        db, db_path = analytics_database
        analytics_service = AnalyticsService(db)
        todo_repo = TodoRepository(db)
        _scoring_service = ScoringService(db)

        # Create and complete todos
        completed_count = 0
        for i in range(5):
            todo = todo_repo.create_todo(f"Consistency test {i}")
            todo_repo.complete_todo(todo.id)
            completed_count += 1

        # Get data from different sources
        user_stats = _scoring_service.user_stats_repo.get_current_stats()
        analytics_report = analytics_service.generate_productivity_report(days=30)

        # Verify consistency
        assert user_stats.total_tasks_completed == completed_count
        assert analytics_report["total_completed"] == completed_count

        # Verify completion rate calculation
        expected_rate = (
            completed_count / completed_count
        ) * 100  # 100% since we completed all
        assert analytics_report["completion_rate"] == expected_rate


if __name__ == "__main__":
    pytest.main([__file__])
