"""Tests for todo application data models."""

from datetime import date, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from todo.models import (
    Achievement,
    AIConfig,
    AIEnrichment,
    AILearningFeedback,
    AIProvider,
    AppConfig,
    Category,
    DailyActivity,
    Priority,
    RecurrenceRule,
    StatsResponse,
    TaskSize,
    Todo,
    TodoListResponse,
    TodoStatus,
    UserStats,
)


class TestEnums:
    """Test enum definitions."""

    def test_todo_status_values(self):
        """Test TodoStatus enum values."""
        assert TodoStatus.PENDING == "pending"
        assert TodoStatus.IN_PROGRESS == "in_progress"
        assert TodoStatus.COMPLETED == "completed"
        assert TodoStatus.ARCHIVED == "archived"
        assert TodoStatus.OVERDUE == "overdue"

    def test_task_size_values(self):
        """Test TaskSize enum values."""
        assert TaskSize.SMALL == "small"
        assert TaskSize.MEDIUM == "medium"
        assert TaskSize.LARGE == "large"

    def test_priority_values(self):
        """Test Priority enum values."""
        assert Priority.LOW == "low"
        assert Priority.MEDIUM == "medium"
        assert Priority.HIGH == "high"
        assert Priority.URGENT == "urgent"

    def test_ai_provider_values(self):
        """Test AIProvider enum values."""
        assert AIProvider.OPENAI == "openai"
        assert AIProvider.ANTHROPIC == "anthropic"


class TestCategory:
    """Test Category model."""

    def test_category_creation(self):
        """Test basic category creation."""
        category = Category(name="Work")
        assert category.name == "Work"
        assert category.id is None
        assert category.color is None
        assert category.icon is None
        assert category.description is None
        assert isinstance(category.created_at, datetime)

    def test_category_with_all_fields(self):
        """Test category with all optional fields."""
        category = Category(
            name="Personal",
            color="#FF5733",
            icon="🏠",
            description="Personal tasks and errands",
        )
        assert category.name == "Personal"
        assert category.color == "#FF5733"
        assert category.icon == "🏠"
        assert category.description == "Personal tasks and errands"

    def test_category_validation_errors(self):
        """Test category validation."""
        # Empty name
        with pytest.raises(ValidationError):
            Category(name="")

        # Name too long
        with pytest.raises(ValidationError):
            Category(name="x" * 51)

        # Invalid color format
        with pytest.raises(ValidationError):
            Category(name="Test", color="invalid")

        # Icon too long
        with pytest.raises(ValidationError):
            Category(name="Test", icon="🏠🏠🏠")

        # Description too long
        with pytest.raises(ValidationError):
            Category(name="Test", description="x" * 201)


class TestRecurrenceRule:
    """Test RecurrenceRule model."""

    def test_recurrence_rule_creation(self):
        """Test basic recurrence rule creation."""
        rule = RecurrenceRule()
        assert rule.pattern == "weekly"
        assert rule.interval_value == 1
        assert rule.weekdays is None
        assert rule.created_from_ai is False

    def test_recurrence_rule_with_weekdays(self):
        """Test recurrence rule with weekdays."""
        rule = RecurrenceRule(weekdays=[0, 2, 4])  # Mon, Wed, Fri
        assert rule.weekdays == [0, 2, 4]

    def test_weekdays_validation(self):
        """Test weekdays validation."""
        # Valid weekdays
        RecurrenceRule(weekdays=[0, 6])  # Should not raise

        # Invalid weekdays
        with pytest.raises(ValidationError):
            RecurrenceRule(weekdays=[7])

        with pytest.raises(ValidationError):
            RecurrenceRule(weekdays=[-1])

    def test_interval_validation(self):
        """Test interval validation."""
        # Valid interval
        RecurrenceRule(interval_value=5)  # Should not raise

        # Invalid interval (zero)
        with pytest.raises(ValidationError):
            RecurrenceRule(interval_value=0)

        # Invalid interval (negative)
        with pytest.raises(ValidationError):
            RecurrenceRule(interval_value=-1)


class TestTodo:
    """Test Todo model."""

    def test_todo_creation(self):
        """Test basic todo creation."""
        todo = Todo(title="Test task")
        assert todo.title == "Test task"
        assert todo.status == TodoStatus.PENDING
        assert todo.final_size == TaskSize.MEDIUM
        assert todo.final_priority == Priority.MEDIUM
        assert isinstance(UUID(todo.uuid), UUID)

    def test_todo_with_all_fields(self):
        """Test todo with all fields."""
        todo = Todo(
            title="Complete project",
            description="Finish the todo app implementation",
            status=TodoStatus.IN_PROGRESS,
            user_override_size=TaskSize.LARGE,
            ai_suggested_priority=Priority.HIGH,
            estimated_minutes=120,
            due_date=date.today(),
        )
        assert todo.title == "Complete project"
        assert todo.description == "Finish the todo app implementation"
        assert todo.status == TodoStatus.IN_PROGRESS
        assert todo.user_override_size == TaskSize.LARGE
        assert todo.ai_suggested_priority == Priority.HIGH
        assert todo.estimated_minutes == 120

    def test_todo_computed_properties(self):
        """Test todo computed properties."""
        # Test effective_size with user override
        todo = Todo(
            title="Test",
            user_override_size=TaskSize.SMALL,
            ai_suggested_size=TaskSize.LARGE,
        )
        assert todo.effective_size == TaskSize.SMALL

        # Test effective_size with AI suggestion only
        todo = Todo(title="Test", ai_suggested_size=TaskSize.LARGE)
        assert todo.effective_size == TaskSize.LARGE

        # Test effective_size fallback
        todo = Todo(title="Test")
        assert todo.effective_size == TaskSize.MEDIUM

        # Test effective_priority similar logic
        todo = Todo(
            title="Test",
            user_override_priority=Priority.URGENT,
            ai_suggested_priority=Priority.LOW,
        )
        assert todo.effective_priority == Priority.URGENT

    def test_todo_is_overdue(self):
        """Test overdue detection."""
        from datetime import timedelta

        # Not overdue - no due date
        todo = Todo(title="Test")
        assert not todo.is_overdue

        # Not overdue - future due date
        todo = Todo(title="Test", due_date=date.today() + timedelta(days=1))
        assert not todo.is_overdue

        # Not overdue - completed task
        todo = Todo(
            title="Test",
            due_date=date.today() - timedelta(days=1),
            status=TodoStatus.COMPLETED,
        )
        assert not todo.is_overdue

        # Overdue - past due date and not completed
        todo = Todo(title="Test", due_date=date.today() - timedelta(days=1))
        assert todo.is_overdue

    def test_todo_validation_errors(self):
        """Test todo validation."""
        # Empty title
        with pytest.raises(ValidationError):
            Todo(title="")

        # Title too long
        with pytest.raises(ValidationError):
            Todo(title="x" * 501)

        # Negative estimated_minutes
        with pytest.raises(ValidationError):
            Todo(title="Test", estimated_minutes=0)

        # Negative points
        with pytest.raises(ValidationError):
            Todo(title="Test", base_points=-1)


class TestAIEnrichment:
    """Test AIEnrichment model."""

    def test_ai_enrichment_creation(self):
        """Test basic AI enrichment creation."""
        enrichment = AIEnrichment(
            todo_id=1, provider=AIProvider.OPENAI, model_name="gpt-4o-mini"
        )
        assert enrichment.todo_id == 1
        assert enrichment.provider == AIProvider.OPENAI
        assert enrichment.model_name == "gpt-4o-mini"
        assert enrichment.confidence_score == 0.5
        assert not enrichment.is_recurring_candidate

    def test_ai_enrichment_with_suggestions(self):
        """Test AI enrichment with suggestions."""
        enrichment = AIEnrichment(
            todo_id=1,
            provider=AIProvider.ANTHROPIC,
            model_name="claude-3-haiku",
            suggested_category="Work",
            suggested_priority=Priority.HIGH,
            suggested_size=TaskSize.LARGE,
            confidence_score=0.85,
            reasoning="This appears to be a complex work task",
        )
        assert enrichment.suggested_category == "Work"
        assert enrichment.suggested_priority == Priority.HIGH
        assert enrichment.suggested_size == TaskSize.LARGE
        assert enrichment.confidence_score == 0.85

    def test_confidence_score_validation(self):
        """Test confidence score validation."""
        # Valid confidence scores
        AIEnrichment(
            todo_id=1,
            provider=AIProvider.OPENAI,
            model_name="test",
            confidence_score=0.0,
        )
        AIEnrichment(
            todo_id=1,
            provider=AIProvider.OPENAI,
            model_name="test",
            confidence_score=1.0,
        )

        # Invalid confidence scores
        with pytest.raises(ValidationError):
            AIEnrichment(
                todo_id=1,
                provider=AIProvider.OPENAI,
                model_name="test",
                confidence_score=-0.1,
            )

        with pytest.raises(ValidationError):
            AIEnrichment(
                todo_id=1,
                provider=AIProvider.OPENAI,
                model_name="test",
                confidence_score=1.1,
            )


class TestUserStats:
    """Test UserStats model."""

    def test_user_stats_creation(self):
        """Test basic user stats creation."""
        stats = UserStats()
        assert stats.total_points == 0
        assert stats.level == 1
        assert stats.points_to_next_level == 100
        assert stats.current_streak_days == 0
        assert stats.daily_goal == 3

    def test_user_stats_with_values(self):
        """Test user stats with custom values."""
        stats = UserStats(
            total_points=500,
            level=5,
            total_tasks_completed=100,
            current_streak_days=7,
            daily_goal=5,
        )
        assert stats.total_points == 500
        assert stats.level == 5
        assert stats.total_tasks_completed == 100
        assert stats.current_streak_days == 7
        assert stats.daily_goal == 5

    def test_user_stats_validation(self):
        """Test user stats validation."""
        # Negative values should fail
        with pytest.raises(ValidationError):
            UserStats(total_points=-1)

        with pytest.raises(ValidationError):
            UserStats(level=0)

        with pytest.raises(ValidationError):
            UserStats(daily_goal=0)


class TestDailyActivity:
    """Test DailyActivity model."""

    def test_daily_activity_creation(self):
        """Test basic daily activity creation."""
        activity = DailyActivity()
        assert activity.activity_date == date.today()
        assert activity.tasks_completed == 0
        assert activity.total_points_earned == 0
        assert not activity.daily_goal_met
        assert not activity.streak_active

    def test_daily_activity_with_values(self):
        """Test daily activity with values."""
        activity = DailyActivity(
            tasks_completed=5,
            base_points_earned=15,
            streak_bonus_earned=5,
            total_points_earned=20,
            daily_goal_met=True,
            streak_active=True,
        )
        assert activity.tasks_completed == 5
        assert activity.base_points_earned == 15
        assert activity.total_points_earned == 20
        assert activity.daily_goal_met
        assert activity.streak_active


class TestAchievement:
    """Test Achievement model."""

    def test_achievement_creation(self):
        """Test basic achievement creation."""
        achievement = Achievement(
            name="First Task",
            description="Complete your first task",
            requirement_type="tasks_completed",
            requirement_value=1,
        )
        assert achievement.name == "First Task"
        assert achievement.requirement_type == "tasks_completed"
        assert achievement.requirement_value == 1
        assert not achievement.is_unlocked
        assert achievement.progress_current == 0

    def test_achievement_with_icon_and_points(self):
        """Test achievement with icon and bonus points."""
        achievement = Achievement(
            name="Task Master",
            description="Complete 100 tasks",
            icon="🏆",
            requirement_type="tasks_completed",
            requirement_value=100,
            bonus_points=50,
        )
        assert achievement.icon == "🏆"
        assert achievement.bonus_points == 50

    def test_achievement_validation(self):
        """Test achievement validation."""
        # Invalid requirement value
        with pytest.raises(ValidationError):
            Achievement(
                name="Test",
                description="Test",
                requirement_type="tasks_completed",
                requirement_value=0,
            )


class TestAppConfig:
    """Test AppConfig model."""

    def test_app_config_creation(self):
        """Test basic app config creation."""
        config = AppConfig()
        assert config.database_path == "~/.local/share/todo/todos.db"
        assert config.enable_gamification
        assert config.daily_goal == 3
        assert isinstance(config.ai, AIConfig)

    def test_ai_config_creation(self):
        """Test AI config creation."""
        ai_config = AIConfig()
        assert ai_config.default_provider == AIProvider.OPENAI
        assert ai_config.openai_model == "gpt-4o-mini"
        assert ai_config.anthropic_model == "claude-3-haiku-20240307"
        assert ai_config.enable_auto_enrichment
        assert ai_config.confidence_threshold == 0.7

    def test_ai_config_validation(self):
        """Test AI config validation."""
        # Valid confidence threshold
        AIConfig(confidence_threshold=0.8)  # Should not raise

        # Invalid confidence threshold
        with pytest.raises(ValidationError):
            AIConfig(confidence_threshold=1.5)

        # Invalid timeout
        with pytest.raises(ValidationError):
            AIConfig(timeout_seconds=3)


class TestResponseModels:
    """Test response models."""

    def test_todo_list_response(self):
        """Test TodoListResponse creation."""
        todo = Todo(title="Test task")
        response = TodoListResponse(
            todos=[todo],
            total_count=1,
            filtered_count=1,
            has_overdue=False,
            current_streak=3,
            points_today=10,
        )
        assert len(response.todos) == 1
        assert response.total_count == 1
        assert not response.has_overdue
        assert response.current_streak == 3

    def test_stats_response(self):
        """Test StatsResponse creation."""
        user_stats = UserStats()
        daily_activity = DailyActivity()
        achievements = [
            Achievement(
                name="First Task",
                description="Complete first task",
                requirement_type="tasks_completed",
                requirement_value=1,
            )
        ]

        response = StatsResponse(
            user_stats=user_stats,
            today_activity=daily_activity,
            recent_achievements=achievements,
        )
        assert isinstance(response.user_stats, UserStats)
        assert isinstance(response.today_activity, DailyActivity)
        assert len(response.recent_achievements) == 1


class TestAILearningFeedback:
    """Test AILearningFeedback model."""

    def test_ai_learning_feedback_creation(self):
        """Test basic AI learning feedback creation."""
        feedback = AILearningFeedback(
            original_task_text="Fix the bug in authentication",
            ai_provider=AIProvider.OPENAI,
            ai_suggested_size=TaskSize.MEDIUM,
            user_corrected_size=TaskSize.LARGE,
            correction_type="size_increase",
        )
        assert feedback.original_task_text == "Fix the bug in authentication"
        assert feedback.ai_provider == AIProvider.OPENAI
        assert feedback.ai_suggested_size == TaskSize.MEDIUM
        assert feedback.user_corrected_size == TaskSize.LARGE
        assert feedback.correction_type == "size_increase"

    def test_ai_learning_feedback_with_keywords(self):
        """Test AI learning feedback with keywords."""
        feedback = AILearningFeedback(
            original_task_text="Review pull request",
            ai_provider=AIProvider.ANTHROPIC,
            task_keywords=["review", "code", "pull request"],
            correction_type="category_change",
        )
        assert feedback.task_keywords == ["review", "code", "pull request"]
