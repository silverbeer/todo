"""Tests for database layer functionality."""

import tempfile
from pathlib import Path

import pytest

from todo.db import (
    AchievementRepository,
    CategoryRepository,
    DailyActivityRepository,
    DatabaseConnection,
    MigrationManager,
    TodoRepository,
    UserStatsRepository,
)
from todo.models import Category, Priority, TaskSize, TodoStatus


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    # Create a temporary directory instead of file
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test.db"

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
def todo_repo(temp_db):
    """Create TodoRepository with temp database."""
    return TodoRepository(temp_db)


@pytest.fixture
def category_repo(temp_db):
    """Create CategoryRepository with temp database."""
    return CategoryRepository(temp_db)


@pytest.fixture
def user_stats_repo(temp_db):
    """Create UserStatsRepository with temp database."""
    return UserStatsRepository(temp_db)


@pytest.fixture
def daily_activity_repo(temp_db):
    """Create DailyActivityRepository with temp database."""
    return DailyActivityRepository(temp_db)


@pytest.fixture
def achievement_repo(temp_db):
    """Create AchievementRepository with temp database."""
    return AchievementRepository(temp_db)


class TestDatabaseConnection:
    """Test DatabaseConnection functionality."""

    def test_connection_creation(self):
        """Test database connection creation."""
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "test.db"

        db = DatabaseConnection(str(db_path))
        conn = db.connect()
        assert conn is not None

        # Test reusing connection
        conn2 = db.connect()
        assert conn is conn2

        db.close()

        # Cleanup
        if db_path.exists():
            db_path.unlink()
        Path(temp_dir).rmdir()

    def test_schema_initialization(self):
        """Test database schema initialization."""
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "test.db"

        db = DatabaseConnection(str(db_path))
        db.initialize_schema()

        # Check that tables were created
        conn = db.connect()
        tables_result = conn.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'main'
            ORDER BY table_name
        """).fetchall()

        table_names = [row[0] for row in tables_result]
        expected_tables = {
            "achievements",
            "ai_enrichments",
            "ai_learning_feedback",
            "categories",
            "daily_activity",
            "recurrence_rules",
            "schema_migrations",
            "todos",
            "user_stats",
        }

        assert expected_tables.issubset(set(table_names))
        db.close()

        # Cleanup
        if db_path.exists():
            db_path.unlink()
        Path(temp_dir).rmdir()

    def test_database_info(self, temp_db):
        """Test database info retrieval."""
        info = temp_db.get_database_info()

        assert "database_path" in info
        assert "database_exists" in info
        assert "tables" in info
        assert "table_counts" in info
        assert info["database_exists"] is True
        assert len(info["tables"]) > 0


class TestMigrationManager:
    """Test MigrationManager functionality."""

    def test_migration_initialization(self, temp_db):
        """Test migration system initialization."""
        migration_manager = MigrationManager(temp_db)

        assert migration_manager.is_schema_initialized()
        assert migration_manager.get_current_version() >= 1

    def test_migration_status(self, temp_db):
        """Test migration status retrieval."""
        migration_manager = MigrationManager(temp_db)
        status = migration_manager.get_migration_status()

        assert status["schema_initialized"] is True
        assert status["current_version"] >= 1
        assert status["total_migrations_applied"] >= 1

    def test_reset_database(self, temp_db):
        """Test database reset functionality."""
        migration_manager = MigrationManager(temp_db)

        # Add some data first
        conn = temp_db.connect()
        conn.execute("INSERT INTO categories (name) VALUES ('Test')")

        # Reset database
        migration_manager.reset_database()

        # Check that data is gone but schema exists
        result = conn.execute(
            "SELECT COUNT(*) FROM categories WHERE name = 'Test'"
        ).fetchone()
        assert result[0] == 0

        # Check that default categories were reinserted
        result = conn.execute("SELECT COUNT(*) FROM categories").fetchone()
        assert result[0] >= 7  # Default categories


class TestCategoryRepository:
    """Test CategoryRepository functionality."""

    def test_get_all_categories(self, category_repo):
        """Test retrieving all categories."""
        categories = category_repo.get_all()
        assert len(categories) >= 7  # Default categories
        assert all(isinstance(cat, Category) for cat in categories)

    def test_get_category_by_name(self, category_repo):
        """Test retrieving category by name."""
        work_category = category_repo.get_by_name("Work")
        assert work_category is not None
        assert work_category.name == "Work"
        assert work_category.icon == "💼"

    def test_get_category_by_id(self, category_repo):
        """Test retrieving category by ID."""
        work_category = category_repo.get_by_name("Work")
        assert work_category is not None

        category_by_id = category_repo.get_by_id(work_category.id)
        assert category_by_id is not None
        assert category_by_id.name == work_category.name

    def test_create_category(self, category_repo):
        """Test creating a new category."""
        new_category = Category(
            name="Testing",
            color="#FF0000",
            icon="🧪",
            description="Testing and QA tasks",
        )

        created = category_repo.create(new_category)
        assert created.id is not None
        assert created.name == "Testing"
        assert created.color == "#FF0000"
        assert created.icon == "🧪"

    def test_get_nonexistent_category(self, category_repo):
        """Test retrieving non-existent category."""
        category = category_repo.get_by_name("NonExistent")
        assert category is None

        category = category_repo.get_by_id(999999)
        assert category is None


class TestTodoRepository:
    """Test TodoRepository functionality."""

    def test_create_todo(self, todo_repo):
        """Test creating a new todo."""
        todo = todo_repo.create_todo("Test task", "Test description")

        assert todo.id is not None
        assert todo.title == "Test task"
        assert todo.description == "Test description"
        assert todo.status == TodoStatus.PENDING
        assert todo.final_size == TaskSize.MEDIUM
        assert todo.final_priority == Priority.MEDIUM
        assert todo.uuid is not None

    def test_get_todo_by_id(self, todo_repo):
        """Test retrieving todo by ID."""
        todo = todo_repo.create_todo("Test task")
        retrieved = todo_repo.get_by_id(todo.id)

        assert retrieved is not None
        assert retrieved.id == todo.id
        assert retrieved.title == todo.title

    def test_get_todo_by_uuid(self, todo_repo):
        """Test retrieving todo by UUID."""
        todo = todo_repo.create_todo("Test task")
        retrieved = todo_repo.get_by_uuid(todo.uuid)

        assert retrieved is not None
        assert retrieved.uuid == todo.uuid
        assert retrieved.title == todo.title

    def test_get_active_todos(self, todo_repo):
        """Test retrieving active todos."""
        # Create some todos
        todo1 = todo_repo.create_todo("Active task 1")
        todo2 = todo_repo.create_todo("Active task 2")
        todo3 = todo_repo.create_todo("Completed task")

        # Complete one todo
        todo_repo.complete_todo(todo3.id)

        active_todos = todo_repo.get_active_todos()
        active_ids = [todo.id for todo in active_todos]

        assert todo1.id in active_ids
        assert todo2.id in active_ids
        assert todo3.id not in active_ids

    def test_get_active_todos_with_limit(self, todo_repo):
        """Test retrieving active todos with limit."""
        # Create multiple todos
        for i in range(5):
            todo_repo.create_todo(f"Task {i + 1}")

        active_todos = todo_repo.get_active_todos(limit=3)
        assert len(active_todos) == 3

    def test_complete_todo(self, todo_repo):
        """Test completing a todo."""
        todo = todo_repo.create_todo("Task to complete")
        assert todo.status == TodoStatus.PENDING
        assert todo.completed_at is None

        completed_todo = todo_repo.complete_todo(todo.id)
        assert completed_todo is not None
        assert completed_todo.status == TodoStatus.COMPLETED
        assert completed_todo.completed_at is not None
        assert completed_todo.total_points_earned > 0

    def test_complete_nonexistent_todo(self, todo_repo):
        """Test completing a non-existent todo."""
        result = todo_repo.complete_todo(999999)
        assert result is None

    def test_complete_already_completed_todo(self, todo_repo):
        """Test completing an already completed todo."""
        todo = todo_repo.create_todo("Task to complete")
        todo_repo.complete_todo(todo.id)

        # Try to complete again
        result = todo_repo.complete_todo(todo.id)
        assert result is None

    def test_update_todo(self, todo_repo):
        """Test updating a todo."""
        todo = todo_repo.create_todo("Original title")

        updates = {
            "title": "Updated title",
            "description": "Updated description",
            "final_priority": Priority.HIGH,
        }

        updated_todo = todo_repo.update_todo(todo.id, updates)
        assert updated_todo is not None
        assert updated_todo.title == "Updated title"
        assert updated_todo.description == "Updated description"
        assert updated_todo.final_priority == Priority.HIGH

    def test_get_overdue_todos(self, todo_repo, temp_db):
        """Test retrieving overdue todos."""
        # Create a todo with past due date
        todo = todo_repo.create_todo("Overdue task")

        # Manually set due date in the past
        conn = temp_db.connect()
        conn.execute(
            """
            UPDATE todos
            SET due_date = CURRENT_DATE - INTERVAL '1 day'
            WHERE id = ?
        """,
            [todo.id],
        )

        overdue_todos = todo_repo.get_overdue_todos()
        overdue_ids = [t.id for t in overdue_todos]
        assert todo.id in overdue_ids

    def test_delete_todo(self, todo_repo):
        """Test deleting a todo."""
        todo = todo_repo.create_todo("Task to delete")

        # Delete the todo
        deleted = todo_repo.delete(todo.id)
        assert deleted is True

        # Verify it's gone
        retrieved = todo_repo.get_by_id(todo.id)
        assert retrieved is None

    def test_base_points_calculation(self, todo_repo):
        """Test base points calculation for different task sizes."""
        small_todo = todo_repo.create_todo("Small task")
        todo_repo.update_todo(small_todo.id, {"final_size": TaskSize.SMALL})

        medium_todo = todo_repo.create_todo("Medium task")
        todo_repo.update_todo(medium_todo.id, {"final_size": TaskSize.MEDIUM})

        large_todo = todo_repo.create_todo("Large task")
        todo_repo.update_todo(large_todo.id, {"final_size": TaskSize.LARGE})

        # Complete and check points
        completed_small = todo_repo.complete_todo(small_todo.id)
        completed_medium = todo_repo.complete_todo(medium_todo.id)
        completed_large = todo_repo.complete_todo(large_todo.id)

        assert completed_small.base_points == 1
        assert completed_medium.base_points == 3
        assert completed_large.base_points == 5


class TestUserStatsRepository:
    """Test UserStatsRepository functionality."""

    def test_get_current_stats(self, user_stats_repo):
        """Test retrieving current user stats."""
        stats = user_stats_repo.get_current_stats()
        assert stats is not None
        assert stats.level == 1
        assert stats.total_points >= 0
        assert stats.daily_goal >= 1

    def test_update_stats(self, user_stats_repo):
        """Test updating user stats."""
        updates = {"total_points": 100, "level": 2, "daily_goal": 5}

        user_stats_repo.update_stats(updates)
        stats = user_stats_repo.get_current_stats()

        assert stats.total_points == 100
        assert stats.level == 2
        assert stats.daily_goal == 5


class TestDailyActivityRepository:
    """Test DailyActivityRepository functionality."""

    def test_get_today_activity(self, daily_activity_repo):
        """Test retrieving today's activity."""
        # Initially should be None (no activity recorded)
        activity = daily_activity_repo.get_today_activity()
        assert activity is None or activity.tasks_completed == 0

    def test_get_recent_activity(self, daily_activity_repo, temp_db):
        """Test retrieving recent activity."""
        # Insert some test activity data
        conn = temp_db.connect()
        conn.execute("""
            INSERT INTO daily_activity (activity_date, tasks_completed, total_points_earned)
            VALUES (CURRENT_DATE, 3, 9)
        """)

        recent = daily_activity_repo.get_recent_activity(days=7)
        assert len(recent) >= 1

        today_activity = recent[0]  # Should be sorted by date DESC
        assert today_activity.tasks_completed == 3
        assert today_activity.total_points_earned == 9


class TestAchievementRepository:
    """Test AchievementRepository functionality."""

    def test_get_all_achievements(self, achievement_repo):
        """Test retrieving all achievements."""
        achievements = achievement_repo.get_all_achievements()
        assert len(achievements) >= 10  # Default achievements

        # Check that default achievements exist
        achievement_names = [a.name for a in achievements]
        assert "First Steps" in achievement_names
        assert "Getting Started" in achievement_names

    def test_get_unlocked_achievements(self, achievement_repo):
        """Test retrieving unlocked achievements."""
        # Initially should be empty
        unlocked = achievement_repo.get_unlocked_achievements()
        assert len(unlocked) == 0

    def test_unlock_achievement(self, achievement_repo):
        """Test unlocking an achievement."""
        achievements = achievement_repo.get_all_achievements()
        first_achievement = achievements[0]

        # Unlock it
        unlocked = achievement_repo.unlock_achievement(first_achievement.id)
        assert unlocked is not None
        assert unlocked.is_unlocked is True
        assert unlocked.unlocked_at is not None

        # Check it appears in unlocked list
        unlocked_list = achievement_repo.get_unlocked_achievements()
        assert len(unlocked_list) == 1
        assert unlocked_list[0].id == first_achievement.id

    def test_unlock_already_unlocked_achievement(self, achievement_repo):
        """Test unlocking an already unlocked achievement."""
        achievements = achievement_repo.get_all_achievements()
        first_achievement = achievements[0]

        # Unlock it first time
        achievement_repo.unlock_achievement(first_achievement.id)

        # Try to unlock again
        result = achievement_repo.unlock_achievement(first_achievement.id)
        assert result is None  # Should not unlock again

    def test_unlock_nonexistent_achievement(self, achievement_repo):
        """Test unlocking a non-existent achievement."""
        result = achievement_repo.unlock_achievement(999999)
        assert result is None


class TestIntegration:
    """Integration tests for database operations."""

    def test_todo_completion_updates_stats(
        self, todo_repo, user_stats_repo, daily_activity_repo
    ):
        """Test that completing a todo updates user stats and daily activity."""
        # Get initial stats
        initial_stats = user_stats_repo.get_current_stats()
        initial_completed = initial_stats.total_tasks_completed
        initial_points = initial_stats.total_points

        # Create and complete a todo
        todo = todo_repo.create_todo("Integration test task")
        completed_todo = todo_repo.complete_todo(todo.id)

        # Check updated stats
        updated_stats = user_stats_repo.get_current_stats()
        assert updated_stats.total_tasks_completed == initial_completed + 1
        assert (
            updated_stats.total_points
            == initial_points + completed_todo.total_points_earned
        )

        # Check daily activity
        today_activity = daily_activity_repo.get_today_activity()
        assert today_activity is not None
        assert today_activity.tasks_completed >= 1
        assert today_activity.total_points_earned >= completed_todo.total_points_earned

    def test_multiple_todo_operations(self, todo_repo):
        """Test multiple todo operations in sequence."""
        # Create multiple todos
        todos = []
        for i in range(3):
            todo = todo_repo.create_todo(f"Task {i + 1}", f"Description {i + 1}")
            todos.append(todo)

        # Update one todo
        updated_todo = todo_repo.update_todo(
            todos[0].id, {"title": "Updated Task 1", "final_priority": Priority.HIGH}
        )
        assert updated_todo.title == "Updated Task 1"
        assert updated_todo.final_priority == Priority.HIGH

        # Complete one todo
        completed_todo = todo_repo.complete_todo(todos[1].id)
        assert completed_todo.status == TodoStatus.COMPLETED

        # Check active todos
        active_todos = todo_repo.get_active_todos()
        active_ids = [t.id for t in active_todos]
        assert todos[0].id in active_ids  # Updated todo still active
        assert todos[1].id not in active_ids  # Completed todo not active
        assert todos[2].id in active_ids  # Unchanged todo still active

        # Delete one todo
        deleted = todo_repo.delete(todos[2].id)
        assert deleted is True

        # Final check
        final_active_todos = todo_repo.get_active_todos()
        final_active_ids = [t.id for t in final_active_todos]
        assert len(final_active_ids) == 1
        assert todos[0].id in final_active_ids
