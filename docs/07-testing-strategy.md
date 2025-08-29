# Testing Strategy - Implementation Plan

> **⚠️ IMPORTANT**: Review this document before implementation. As we develop the application, requirements may change and this documentation should be updated to reflect any modifications to the testing approach and coverage requirements.

## Overview
This document outlines a comprehensive testing strategy for the todo application, ensuring high code quality, reliability, and maintainability. We target 95%+ code coverage with a mix of unit, integration, and end-to-end tests.

## Testing Philosophy

### Test-Driven Development (TDD)
- Write tests before implementing features
- Red-Green-Refactor cycle for all new functionality
- Tests serve as living documentation
- Comprehensive edge case coverage

### Test Categories
1. **Unit Tests** (70%): Test individual functions and classes in isolation
2. **Integration Tests** (25%): Test component interactions and database operations
3. **End-to-End Tests** (5%): Test complete CLI workflows and user scenarios

### Quality Targets
- **Code Coverage**: Minimum 95%, target 98%
- **Test Performance**: Unit tests <1s total, integration tests <10s total
- **Reliability**: Zero flaky tests, deterministic outcomes
- **Maintainability**: Tests are clear, focused, and easy to update

## Test Structure and Organization

### Directory Structure
```
tests/
├── __init__.py
├── conftest.py              # Pytest configuration and shared fixtures
├── unit/                    # Unit tests (fast, isolated)
│   ├── __init__.py
│   ├── test_models.py       # Pydantic model validation
│   ├── test_scoring.py      # Gamification logic
│   ├── test_enrichment.py   # AI enrichment service
│   ├── test_cli_utils.py    # CLI utility functions
│   └── test_analytics.py    # Analytics calculations
├── integration/             # Integration tests (database, external services)
│   ├── __init__.py
│   ├── test_database.py     # Database operations
│   ├── test_repositories.py # Repository pattern implementations
│   ├── test_ai_providers.py # AI provider integrations
│   └── test_workflows.py    # Business logic workflows
└── e2e/                     # End-to-end tests (full CLI scenarios)
    ├── __init__.py
    ├── test_todo_lifecycle.py # Complete todo management flows
    ├── test_gamification.py   # Gamification scenarios
    └── test_ai_integration.py # AI enrichment end-to-end
```

## Test Configuration and Fixtures

### Pytest Configuration (conftest.py)
```python
# tests/conftest.py
import pytest
import tempfile
import os
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import Generator, Dict, Any
from unittest.mock import Mock, AsyncMock

from todo.db.connection import DatabaseConnection
from todo.db.repositories.todo import TodoRepository
from todo.db.repositories.gamification import GamificationRepository
from todo.models.todo import Todo, TaskSize, Priority, TodoStatus, Category
from todo.models.gamification import UserStats, DailyActivity, Achievement
from todo.core.config import AppConfig

# Test database fixture
@pytest.fixture(scope="function")
def test_db() -> Generator[DatabaseConnection, None, None]:
    """Create a temporary test database for each test."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        db_path = tmp_file.name

    try:
        db = DatabaseConnection(db_path)
        # Initialize schema
        conn = db.connect()
        # Run migration scripts to set up tables
        yield db
    finally:
        db.close()
        os.unlink(db_path)

# Repository fixtures
@pytest.fixture
def todo_repo(test_db: DatabaseConnection) -> TodoRepository:
    """Create TodoRepository with test database."""
    return TodoRepository(test_db)

@pytest.fixture
def gamification_repo(test_db: DatabaseConnection) -> GamificationRepository:
    """Create GamificationRepository with test database."""
    return GamificationRepository(test_db)

# Model fixtures
@pytest.fixture
def sample_todo() -> Todo:
    """Create a sample todo for testing."""
    return Todo(
        id=1,
        title="Test Task",
        description="A test task description",
        status=TodoStatus.PENDING,
        final_size=TaskSize.MEDIUM,
        final_priority=Priority.MEDIUM,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

@pytest.fixture
def completed_todo() -> Todo:
    """Create a completed todo for testing."""
    now = datetime.utcnow()
    return Todo(
        id=2,
        title="Completed Task",
        status=TodoStatus.COMPLETED,
        final_size=TaskSize.SMALL,
        final_priority=Priority.LOW,
        base_points=1,
        bonus_points=0,
        total_points_earned=1,
        created_at=now - timedelta(hours=2),
        updated_at=now,
        completed_at=now
    )

@pytest.fixture
def user_stats() -> UserStats:
    """Create sample user stats for testing."""
    return UserStats(
        id=1,
        total_points=100,
        level=2,
        points_to_next_level=150,
        total_tasks_completed=25,
        current_streak_days=5,
        longest_streak_days=12,
        daily_goal=3,
        weekly_goal=20,
        monthly_goal=80,
        last_completion_date=date.today()
    )

@pytest.fixture
def daily_activity() -> DailyActivity:
    """Create sample daily activity for testing."""
    return DailyActivity(
        id=1,
        activity_date=date.today(),
        tasks_completed=3,
        base_points_earned=7,
        streak_bonus_earned=1,
        total_points_earned=8,
        daily_goal_met=True
    )

# Mock fixtures for external services
@pytest.fixture
def mock_openai():
    """Mock OpenAI API responses."""
    mock = AsyncMock()
    mock.chat.completions.create.return_value.choices[0].message.content = '{"suggested_category": "Work", "suggested_size": "medium", "confidence": 0.9}'
    return mock

@pytest.fixture
def mock_anthropic():
    """Mock Anthropic API responses."""
    mock = AsyncMock()
    mock.messages.create.return_value.content = [Mock(text='{"suggested_category": "Personal", "suggested_size": "small", "confidence": 0.8}')]
    return mock

# Configuration fixture
@pytest.fixture
def test_config() -> AppConfig:
    """Create test configuration."""
    return AppConfig(
        database_path=":memory:",  # In-memory SQLite for tests
        ai=AIConfig(
            default_provider="openai",
            openai_api_key="test_key",
            enable_auto_enrichment=True,
            confidence_threshold=0.7
        ),
        enable_gamification=True,
        daily_goal=3
    )

# Time-based fixtures
@pytest.fixture
def freeze_time():
    """Fixture to freeze time for consistent testing."""
    from unittest.mock import patch
    frozen_time = datetime(2025, 1, 15, 12, 0, 0)  # Fixed test time

    with patch('todo.core.scoring.datetime') as mock_datetime:
        mock_datetime.utcnow.return_value = frozen_time
        mock_datetime.now.return_value = frozen_time
        yield frozen_time
```

## Unit Tests

### Model Testing (test_models.py)
```python
# tests/unit/test_models.py
import pytest
from datetime import date, datetime
from pydantic import ValidationError

from todo.models.todo import Todo, TodoStatus, TaskSize, Priority
from todo.models.gamification import UserStats, Achievement
from todo.models.ai import AIEnrichment, AIProvider

class TestTodoModel:
    """Test Todo model validation and behavior."""

    def test_todo_creation_with_minimal_data(self):
        """Test creating todo with only required fields."""
        todo = Todo(
            title="Test task",
            final_size=TaskSize.MEDIUM,
            final_priority=Priority.MEDIUM
        )

        assert todo.title == "Test task"
        assert todo.status == TodoStatus.PENDING
        assert todo.final_size == TaskSize.MEDIUM
        assert todo.uuid is not None
        assert len(todo.uuid) == 36  # UUID4 length

    def test_todo_validation_empty_title(self):
        """Test validation fails for empty title."""
        with pytest.raises(ValidationError) as exc_info:
            Todo(title="", final_size=TaskSize.MEDIUM, final_priority=Priority.MEDIUM)

        assert "ensure this value has at least 1 characters" in str(exc_info.value)

    def test_todo_validation_title_too_long(self):
        """Test validation fails for excessively long title."""
        long_title = "x" * 501  # Over 500 character limit

        with pytest.raises(ValidationError):
            Todo(title=long_title, final_size=TaskSize.MEDIUM, final_priority=Priority.MEDIUM)

    def test_todo_is_overdue_property(self):
        """Test is_overdue computed property."""
        # Not overdue - future due date
        future_todo = Todo(
            title="Future task",
            due_date=date.today() + timedelta(days=1),
            final_size=TaskSize.MEDIUM,
            final_priority=Priority.MEDIUM
        )
        assert not future_todo.is_overdue

        # Overdue - past due date
        overdue_todo = Todo(
            title="Overdue task",
            due_date=date.today() - timedelta(days=1),
            final_size=TaskSize.MEDIUM,
            final_priority=Priority.MEDIUM
        )
        assert overdue_todo.is_overdue

        # Completed task - never overdue
        completed_todo = Todo(
            title="Completed task",
            status=TodoStatus.COMPLETED,
            due_date=date.today() - timedelta(days=1),
            final_size=TaskSize.MEDIUM,
            final_priority=Priority.MEDIUM
        )
        assert not completed_todo.is_overdue

    def test_effective_size_property(self):
        """Test effective_size computed property logic."""
        # User override takes precedence
        todo = Todo(
            title="Test task",
            user_override_size=TaskSize.LARGE,
            ai_suggested_size=TaskSize.SMALL,
            final_size=TaskSize.MEDIUM,
            final_priority=Priority.MEDIUM
        )
        assert todo.effective_size == TaskSize.LARGE

        # AI suggestion when no user override
        todo.user_override_size = None
        assert todo.effective_size == TaskSize.SMALL

        # Default when neither available
        todo.ai_suggested_size = None
        assert todo.effective_size == TaskSize.MEDIUM

class TestUserStatsModel:
    """Test UserStats model validation and behavior."""

    def test_user_stats_creation(self):
        """Test creating UserStats with default values."""
        stats = UserStats()

        assert stats.total_points == 0
        assert stats.level == 1
        assert stats.current_streak_days == 0
        assert stats.daily_goal == 3
        assert stats.achievements_unlocked == 0

    def test_user_stats_validation_negative_values(self):
        """Test validation prevents negative values."""
        with pytest.raises(ValidationError):
            UserStats(total_points=-10)

        with pytest.raises(ValidationError):
            UserStats(level=0)

        with pytest.raises(ValidationError):
            UserStats(daily_goal=0)

class TestAIEnrichmentModel:
    """Test AIEnrichment model validation."""

    def test_ai_enrichment_creation(self):
        """Test creating AIEnrichment with valid data."""
        enrichment = AIEnrichment(
            todo_id=1,
            provider=AIProvider.OPENAI,
            model_name="gpt-4o-mini",
            suggested_category="Work",
            suggested_priority=Priority.HIGH,
            suggested_size=TaskSize.LARGE,
            confidence_score=0.85,
            reasoning="Task involves complex project management"
        )

        assert enrichment.provider == AIProvider.OPENAI
        assert enrichment.confidence_score == 0.85
        assert enrichment.is_recurring_candidate is False

    def test_confidence_score_validation(self):
        """Test confidence score must be between 0 and 1."""
        with pytest.raises(ValidationError):
            AIEnrichment(
                todo_id=1,
                provider=AIProvider.OPENAI,
                model_name="gpt-4o-mini",
                confidence_score=1.5  # Invalid - over 1.0
            )

        with pytest.raises(ValidationError):
            AIEnrichment(
                todo_id=1,
                provider=AIProvider.OPENAI,
                model_name="gpt-4o-mini",
                confidence_score=-0.1  # Invalid - under 0.0
            )
```

### Scoring System Testing (test_scoring.py)
```python
# tests/unit/test_scoring.py
import pytest
from datetime import date, timedelta
from unittest.mock import Mock, patch

from todo.core.scoring import ScoringService
from todo.models.todo import Todo, TaskSize, Priority, TodoStatus
from todo.models.gamification import UserStats, DailyActivity

class TestScoringService:
    """Test scoring system calculations."""

    @pytest.fixture
    def scoring_service(self, test_db):
        """Create ScoringService with mocked dependencies."""
        return ScoringService()

    def test_base_point_calculation(self, scoring_service):
        """Test base point values for different task sizes."""
        small_todo = Todo(
            title="Small task",
            final_size=TaskSize.SMALL,
            final_priority=Priority.MEDIUM
        )
        medium_todo = Todo(
            title="Medium task",
            final_size=TaskSize.MEDIUM,
            final_priority=Priority.MEDIUM
        )
        large_todo = Todo(
            title="Large task",
            final_size=TaskSize.LARGE,
            final_priority=Priority.MEDIUM
        )

        # Mock repository calls
        with patch.object(scoring_service, 'gamification_repo') as mock_repo:
            mock_repo.get_user_stats.return_value = UserStats(current_streak_days=0)
            mock_repo.get_today_activity.return_value = None

            small_base, small_bonus, small_total = scoring_service.calculate_completion_points(small_todo)
            medium_base, medium_bonus, medium_total = scoring_service.calculate_completion_points(medium_todo)
            large_base, large_bonus, large_total = scoring_service.calculate_completion_points(large_todo)

            assert small_base == 1
            assert medium_base == 3
            assert large_base == 5

    def test_streak_bonus_calculation(self, scoring_service):
        """Test streak bonus multipliers."""
        todo = Todo(
            title="Test task",
            final_size=TaskSize.MEDIUM,  # 3 base points
            final_priority=Priority.MEDIUM
        )

        # Test 7-day streak (25% bonus)
        with patch.object(scoring_service, 'gamification_repo') as mock_repo:
            mock_repo.get_user_stats.return_value = UserStats(current_streak_days=7)
            mock_repo.get_today_activity.return_value = None

            base, bonus, total = scoring_service.calculate_completion_points(todo)

            assert base == 3
            assert bonus == 1  # 25% of 3 = 0.75, rounded to 1
            assert total == 4

        # Test 30-day streak (60% bonus)
        with patch.object(scoring_service, 'gamification_repo') as mock_repo:
            mock_repo.get_user_stats.return_value = UserStats(current_streak_days=30)
            mock_repo.get_today_activity.return_value = None

            base, bonus, total = scoring_service.calculate_completion_points(todo)

            assert base == 3
            assert bonus == 2  # 60% of 3 = 1.8, rounded to 2
            assert total == 5

    def test_daily_goal_bonus(self, scoring_service):
        """Test daily goal completion bonus."""
        todo = Todo(
            title="Test task",
            final_size=TaskSize.MEDIUM,  # 3 base points
            final_priority=Priority.MEDIUM
        )

        # First time hitting daily goal of 3
        with patch.object(scoring_service, 'gamification_repo') as mock_repo:
            mock_repo.get_user_stats.return_value = UserStats(daily_goal=3, current_streak_days=0)
            mock_repo.get_today_activity.return_value = DailyActivity(
                tasks_completed=2,  # This completion will be #3
                daily_goal_met=False
            )

            base, bonus, total = scoring_service.calculate_completion_points(todo)

            assert base == 3
            assert bonus >= 1  # Should include daily goal bonus

    def test_level_calculation(self, scoring_service):
        """Test level calculation from total points."""
        # Test various point levels
        level1, points_to_next1, _ = scoring_service.calculate_level(50)
        assert level1 == 1
        assert points_to_next1 == 50  # 100 - 50

        level2, points_to_next2, _ = scoring_service.calculate_level(150)
        assert level2 == 2
        assert points_to_next2 == 100  # 250 - 150

        level3, points_to_next3, _ = scoring_service.calculate_level(600)
        assert level3 == 3
        assert points_to_next3 == 400  # 1000 - 600

    def test_streak_update_logic(self, scoring_service):
        """Test streak update scenarios."""
        with patch.object(scoring_service, 'gamification_repo') as mock_repo:
            # First completion ever
            mock_repo.get_user_stats.return_value = UserStats(
                current_streak_days=0,
                longest_streak_days=0,
                last_completion_date=None
            )

            new_streak = scoring_service.update_streak(date.today())
            assert new_streak == 1

            # Consecutive day completion
            mock_repo.get_user_stats.return_value = UserStats(
                current_streak_days=5,
                longest_streak_days=10,
                last_completion_date=date.today() - timedelta(days=1)
            )

            new_streak = scoring_service.update_streak(date.today())
            assert new_streak == 6

            # Streak broken
            mock_repo.get_user_stats.return_value = UserStats(
                current_streak_days=5,
                longest_streak_days=10,
                last_completion_date=date.today() - timedelta(days=3)
            )

            new_streak = scoring_service.update_streak(date.today())
            assert new_streak == 1

    def test_overdue_penalty_calculation(self, scoring_service):
        """Test overdue penalty application."""
        # Create overdue todos
        overdue_todo = Todo(
            id=1,
            title="Overdue task",
            due_date=date.today() - timedelta(days=2),
            final_size=TaskSize.MEDIUM,
            final_priority=Priority.MEDIUM
        )

        with patch.object(scoring_service, 'todo_repo') as mock_todo_repo, \
             patch.object(scoring_service, 'gamification_repo') as mock_gamification_repo:

            mock_todo_repo.get_overdue_todos.return_value = [overdue_todo]
            mock_gamification_repo.get_user_stats.return_value = UserStats(total_points=100)
            mock_gamification_repo.get_today_activity.return_value = DailyActivity()

            penalty = scoring_service.apply_overdue_penalties()

            assert penalty == 2  # 2 days overdue = 2 point penalty
            mock_gamification_repo.update_user_stats.assert_called_with({'total_points': 98})

class TestAchievementService:
    """Test achievement system."""

    @pytest.fixture
    def achievement_service(self, test_db):
        from todo.core.achievements import AchievementService
        return AchievementService()

    def test_first_task_achievement(self, achievement_service):
        """Test 'First Steps' achievement unlock."""
        user_stats = UserStats(total_tasks_completed=1)

        with patch.object(achievement_service, 'gamification_repo') as mock_repo:
            mock_repo.get_all_achievements.return_value = []
            mock_repo.create_achievement.return_value = Mock()
            mock_repo.update_user_stats.return_value = None

            achievements = achievement_service.check_and_unlock_achievements(user_stats)

            assert len(achievements) > 0
            # Should include 'First Steps' achievement
            achievement_names = [a.name for a in achievements]
            assert 'First Steps' in achievement_names

    def test_streak_achievements(self, achievement_service):
        """Test streak-based achievement unlocking."""
        user_stats = UserStats(current_streak_days=7, total_tasks_completed=10)

        with patch.object(achievement_service, 'gamification_repo') as mock_repo:
            mock_repo.get_all_achievements.return_value = []
            mock_repo.create_achievement.return_value = Mock()
            mock_repo.update_user_stats.return_value = None
            mock_repo.count_daily_goals_met.return_value = 0

            achievements = achievement_service.check_and_unlock_achievements(user_stats)

            # Should unlock multiple streak achievements
            achievement_names = [a.name for a in achievements]
            assert 'Consistency' in achievement_names  # 3-day streak
            assert 'Week Warrior' in achievement_names  # 7-day streak
```

## Integration Tests

### Database Integration Testing (test_database.py)
```python
# tests/integration/test_database.py
import pytest
from datetime import date, datetime, timedelta

from todo.models.todo import Todo, TodoStatus, TaskSize, Priority
from todo.models.gamification import UserStats, DailyActivity

class TestTodoRepository:
    """Test TodoRepository database operations."""

    def test_create_todo(self, todo_repo):
        """Test creating a todo in the database."""
        todo = todo_repo.create_todo("Test task", "Test description")

        assert todo.id is not None
        assert todo.title == "Test task"
        assert todo.description == "Test description"
        assert todo.status == TodoStatus.PENDING
        assert todo.created_at is not None

    def test_get_todo_by_id(self, todo_repo):
        """Test retrieving todo by ID."""
        # Create todo
        created_todo = todo_repo.create_todo("Test task")

        # Retrieve todo
        retrieved_todo = todo_repo.get_by_id(created_todo.id)

        assert retrieved_todo is not None
        assert retrieved_todo.id == created_todo.id
        assert retrieved_todo.title == created_todo.title

    def test_update_todo(self, todo_repo):
        """Test updating todo properties."""
        # Create todo
        todo = todo_repo.create_todo("Original title")

        # Update todo
        updates = {
            'title': 'Updated title',
            'final_priority': Priority.HIGH,
            'due_date': date.today() + timedelta(days=1)
        }
        updated_todo = todo_repo.update(todo.id, updates)

        assert updated_todo.title == "Updated title"
        assert updated_todo.final_priority == Priority.HIGH
        assert updated_todo.due_date == date.today() + timedelta(days=1)

    def test_complete_todo(self, todo_repo):
        """Test completing a todo with point calculation."""
        # Create todo
        todo = todo_repo.create_todo("Task to complete")

        # Complete todo
        completed_todo = todo_repo.complete_todo(todo.id)

        assert completed_todo is not None
        assert completed_todo.status == TodoStatus.COMPLETED
        assert completed_todo.completed_at is not None
        assert completed_todo.total_points_earned > 0

    def test_get_active_todos(self, todo_repo):
        """Test filtering active todos."""
        # Create todos with different statuses
        pending_todo = todo_repo.create_todo("Pending task")
        completed_todo = todo_repo.create_todo("Completed task")
        todo_repo.update(completed_todo.id, {'status': TodoStatus.COMPLETED})

        # Get active todos
        active_todos = todo_repo.get_active_todos()

        active_ids = [t.id for t in active_todos]
        assert pending_todo.id in active_ids
        assert completed_todo.id not in active_ids

    def test_get_overdue_todos(self, todo_repo):
        """Test filtering overdue todos."""
        # Create todos with different due dates
        overdue_todo = todo_repo.create_todo("Overdue task")
        todo_repo.update(overdue_todo.id, {'due_date': date.today() - timedelta(days=1)})

        future_todo = todo_repo.create_todo("Future task")
        todo_repo.update(future_todo.id, {'due_date': date.today() + timedelta(days=1)})

        # Get overdue todos
        overdue_todos = todo_repo.get_overdue_todos()

        overdue_ids = [t.id for t in overdue_todos]
        assert overdue_todo.id in overdue_ids
        assert future_todo.id not in overdue_ids

class TestGamificationRepository:
    """Test GamificationRepository database operations."""

    def test_get_user_stats(self, gamification_repo):
        """Test retrieving user stats."""
        stats = gamification_repo.get_user_stats()

        assert stats is not None
        assert stats.total_points >= 0
        assert stats.level >= 1
        assert stats.daily_goal > 0

    def test_update_user_stats(self, gamification_repo):
        """Test updating user statistics."""
        # Update stats
        updates = {
            'total_points': 150,
            'current_streak_days': 7,
            'daily_goal': 5
        }
        gamification_repo.update_user_stats(updates)

        # Verify updates
        stats = gamification_repo.get_user_stats()
        assert stats.total_points == 150
        assert stats.current_streak_days == 7
        assert stats.daily_goal == 5

    def test_daily_activity_tracking(self, gamification_repo):
        """Test daily activity creation and updates."""
        today = date.today()

        # Create daily activity
        activity_data = {
            'tasks_completed': 3,
            'base_points_earned': 7,
            'total_points_earned': 8,
            'daily_goal_met': True
        }
        gamification_repo.update_daily_activity(today, activity_data)

        # Retrieve activity
        activity = gamification_repo.get_today_activity()

        assert activity is not None
        assert activity.tasks_completed == 3
        assert activity.total_points_earned == 8
        assert activity.daily_goal_met is True

    def test_achievement_management(self, gamification_repo):
        """Test achievement creation and unlocking."""
        from todo.models.gamification import Achievement

        # Create achievement
        achievement = Achievement(
            name="Test Achievement",
            description="A test achievement",
            requirement_type="tasks_completed",
            requirement_value=10,
            bonus_points=50
        )

        created = gamification_repo.create_achievement(achievement)
        assert created.id is not None
        assert not created.is_unlocked

        # Unlock achievement
        gamification_repo.unlock_achievement(created.id)

        # Verify unlock
        unlocked = gamification_repo.get_achievement_by_id(created.id)
        assert unlocked.is_unlocked
        assert unlocked.unlocked_at is not None

class TestDatabaseTransactions:
    """Test database transaction handling."""

    def test_todo_completion_transaction(self, todo_repo, gamification_repo):
        """Test that todo completion updates multiple tables atomically."""
        # Create todo
        todo = todo_repo.create_todo("Transaction test")

        # Get initial stats
        initial_stats = gamification_repo.get_user_stats()
        initial_points = initial_stats.total_points

        # Complete todo (should update todos, user_stats, and daily_activity)
        completed_todo = todo_repo.complete_todo(todo.id)

        # Verify all updates occurred
        assert completed_todo.status == TodoStatus.COMPLETED

        updated_stats = gamification_repo.get_user_stats()
        assert updated_stats.total_points > initial_points

        today_activity = gamification_repo.get_today_activity()
        assert today_activity.tasks_completed >= 1

    def test_transaction_rollback_on_error(self, test_db):
        """Test that transactions roll back on errors."""
        # This would test error scenarios and rollback behavior
        # Implementation depends on specific error handling approach
        pass
```

## End-to-End Tests

### CLI Workflow Testing (test_todo_lifecycle.py)
```python
# tests/e2e/test_todo_lifecycle.py
import pytest
from typer.testing import CliRunner
from unittest.mock import patch

from todo.cli.main import app

class TestTodoLifecycle:
    """Test complete todo lifecycle through CLI."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    def test_complete_todo_workflow(self, runner, test_db):
        """Test creating, listing, updating, and completing todos."""
        with patch('todo.cli.main.todo_repo') as mock_repo, \
             patch('todo.cli.main.background_enrichment') as mock_enrichment:

            # Mock repository responses
            mock_repo.create_todo.return_value = Mock(id=1, title="Test task")
            mock_repo.get_filtered_todos.return_value = [Mock(id=1, title="Test task")]
            mock_repo.get_dashboard_stats.return_value = {}
            mock_repo.complete_todo.return_value = Mock(
                id=1,
                title="Test task",
                total_points_earned=3
            )

            # 1. Create todo
            result = runner.invoke(app, ["add", "Test task", "--no-ai"])
            assert result.exit_code == 0
            assert "Created todo #1" in result.stdout

            # 2. List todos
            result = runner.invoke(app, ["list"])
            assert result.exit_code == 0

            # 3. Complete todo
            result = runner.invoke(app, ["done", "1"])
            assert result.exit_code == 0
            assert "Completed" in result.stdout

    def test_todo_with_ai_enrichment(self, runner, mock_openai):
        """Test todo creation with AI enrichment enabled."""
        with patch('todo.cli.main.todo_repo') as mock_repo, \
             patch('todo.cli.main.background_enrichment') as mock_enrichment:

            mock_repo.create_todo.return_value = Mock(id=1, title="Cut the grass")

            # Create todo with AI enrichment
            result = runner.invoke(app, ["add", "Cut the grass"])
            assert result.exit_code == 0
            assert "AI enrichment processing" in result.stdout

            # Verify background enrichment was started
            mock_enrichment.enrich_todo_background.assert_called_once_with(1)

    def test_error_handling(self, runner):
        """Test CLI error handling for invalid inputs."""
        # Test invalid todo ID
        result = runner.invoke(app, ["done", "999"])
        assert result.exit_code == 0  # Should handle gracefully
        assert "not found" in result.stdout.lower()

        # Test invalid date format
        result = runner.invoke(app, ["add", "Test", "--due", "invalid-date"])
        assert result.exit_code != 0 or "invalid" in result.stdout.lower()

    def test_natural_language_date_parsing(self, runner):
        """Test natural language date parsing in CLI."""
        with patch('todo.cli.main.todo_repo') as mock_repo:
            mock_repo.create_todo.return_value = Mock(id=1, title="Test task")

            # Test various date formats
            date_formats = ["tomorrow", "monday", "2025-12-25", "12/25"]

            for date_format in date_formats:
                result = runner.invoke(app, ["add", "Test task", "--due", date_format, "--no-ai"])
                assert result.exit_code == 0, f"Failed for date format: {date_format}"

class TestGamificationCLI:
    """Test gamification features through CLI."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_stats_command(self, runner):
        """Test stats command output."""
        with patch('todo.db.repositories.gamification.GamificationRepository') as mock_repo:
            mock_repo_instance = mock_repo.return_value
            mock_repo_instance.get_stats_for_period.return_value = {
                'total_points': 100,
                'level': 2,
                'current_streak': 5
            }
            mock_repo_instance.get_recent_achievements.return_value = []

            result = runner.invoke(app, ["stats"])
            assert result.exit_code == 0
            assert "points" in result.stdout.lower()

    def test_achievements_command(self, runner):
        """Test achievements command output."""
        with patch('todo.db.repositories.gamification.GamificationRepository') as mock_repo:
            mock_repo_instance = mock_repo.return_value
            mock_repo_instance.get_all_achievements.return_value = [
                Mock(name="First Steps", description="Complete first task", is_unlocked=True)
            ]

            result = runner.invoke(app, ["achievements"])
            assert result.exit_code == 0
            assert "First Steps" in result.stdout

    def test_goals_management(self, runner):
        """Test goals command for viewing and setting."""
        with patch('todo.db.repositories.gamification.GamificationRepository') as mock_repo:
            mock_repo_instance = mock_repo.return_value
            mock_repo_instance.get_current_goals.return_value = Mock(daily_goal=3, weekly_goal=20)
            mock_repo_instance.get_goal_progress.return_value = {}

            # View current goals
            result = runner.invoke(app, ["goals"])
            assert result.exit_code == 0

            # Set new goals
            result = runner.invoke(app, ["goals", "--daily", "5"])
            assert result.exit_code == 0
            assert "updated" in result.stdout.lower()

class TestAIIntegration:
    """Test AI integration end-to-end."""

    def test_ai_enrichment_workflow(self, runner, mock_openai):
        """Test complete AI enrichment workflow."""
        with patch('todo.ai.enrichment_service.EnrichmentService') as mock_service, \
             patch('todo.cli.main.todo_repo') as mock_repo:

            # Mock AI enrichment response
            mock_enrichment = Mock(
                suggested_category="Home",
                suggested_size="medium",
                confidence_score=0.9
            )
            mock_service.return_value.enrich_todo.return_value = mock_enrichment
            mock_repo.create_todo.return_value = Mock(id=1, title="Cut the grass")

            # Create todo (triggers background enrichment)
            result = runner.invoke(app, ["add", "Cut the grass"])
            assert result.exit_code == 0

    def test_user_override_learning(self, runner):
        """Test that user overrides are recorded for AI learning."""
        with patch('todo.cli.main.todo_repo') as mock_repo, \
             patch('todo.ai.learning.LearningService') as mock_learning:

            mock_repo.get_by_id.return_value = Mock(
                id=1,
                title="Test task",
                ai_suggested_size="small"
            )
            mock_repo.update.return_value = Mock()

            # Update todo with size override
            result = runner.invoke(app, ["update", "1", "--size", "large"])
            assert result.exit_code == 0

            # Verify learning service was called
            mock_learning.return_value.record_user_override.assert_called_once()
```

## Test Execution and Coverage

### Coverage Configuration
```toml
# pyproject.toml coverage configuration
[tool.coverage.run]
source = ["src/todo"]
branch = true
omit = [
    "tests/*",
    "*/migrations/*",
    "*/__main__.py",
    "*/conftest.py"
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "if self.debug:",
    "if settings.DEBUG",
    "raise AssertionError",
    "raise NotImplementedError",
    "if 0:",
    "if __name__ == .__main__.:",
    "class .*\\bProtocol\\):",
    "@(abc\\.)?abstractmethod",
]
show_missing = true
skip_covered = false
precision = 2
fail_under = 95

[tool.coverage.html]
directory = "htmlcov"

[tool.coverage.xml]
output = "coverage.xml"
```

### Test Execution Scripts
```bash
# scripts/test.sh
#!/bin/bash
set -e

echo "Running test suite..."

# Run tests with coverage
uv run pytest --cov=src/todo --cov-report=term-missing --cov-report=html --cov-report=xml

# Check coverage threshold
uv run coverage report --fail-under=95

echo "All tests passed with sufficient coverage!"
```

## Performance Testing

### Load Testing for Database Operations
```python
# tests/performance/test_performance.py
import pytest
import time
from concurrent.futures import ThreadPoolExecutor

class TestPerformance:
    """Test application performance under load."""

    def test_database_performance(self, todo_repo):
        """Test database operation performance."""
        start_time = time.time()

        # Create 1000 todos
        for i in range(1000):
            todo_repo.create_todo(f"Performance test {i}")

        creation_time = time.time() - start_time
        assert creation_time < 10.0, f"Creating 1000 todos took {creation_time}s (should be < 10s)"

        # Query performance test
        start_time = time.time()
        active_todos = todo_repo.get_active_todos(limit=100)
        query_time = time.time() - start_time

        assert query_time < 1.0, f"Querying todos took {query_time}s (should be < 1s)"
        assert len(active_todos) <= 100

    def test_concurrent_operations(self, todo_repo):
        """Test concurrent database operations."""

        def create_and_complete_todo(index):
            todo = todo_repo.create_todo(f"Concurrent task {index}")
            return todo_repo.complete_todo(todo.id)

        start_time = time.time()

        # Run 50 concurrent operations
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_and_complete_todo, i) for i in range(50)]
            results = [f.result() for f in futures]

        concurrent_time = time.time() - start_time

        assert concurrent_time < 5.0, f"50 concurrent operations took {concurrent_time}s"
        assert len(results) == 50
        assert all(r.status == TodoStatus.COMPLETED for r in results)
```

## Implementation Steps

### Step 1: Test Infrastructure Setup
1. Create test directory structure
2. Implement conftest.py with fixtures
3. Configure pytest and coverage settings
4. Test basic test execution

### Step 2: Unit Test Implementation
1. Write model validation tests
2. Implement scoring system tests
3. Add AI enrichment service tests
4. Create CLI utility function tests

### Step 3: Integration Test Development
1. Implement database operation tests
2. Add repository integration tests
3. Create transaction testing
4. Test external service mocking

### Step 4: End-to-End Test Creation
1. Implement CLI workflow tests
2. Add gamification feature tests
3. Create AI integration tests
4. Test error handling scenarios

### Step 5: Performance and Coverage
1. Add performance testing suite
2. Achieve 95%+ code coverage
3. Optimize slow tests
4. Set up CI/CD integration

## Success Criteria
- [ ] Test suite runs in under 30 seconds
- [ ] Code coverage above 95%
- [ ] All edge cases covered
- [ ] Integration tests verify database operations
- [ ] End-to-end tests cover user workflows
- [ ] Performance tests validate scalability
- [ ] Zero flaky tests in CI/CD
- [ ] Tests serve as comprehensive documentation
