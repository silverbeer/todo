"""Tests for repository functionality."""

import tempfile
from pathlib import Path

import pytest

from todo.db.connection import DatabaseConnection
from todo.db.migrations import MigrationManager
from todo.db.repository import CategoryRepository, TodoRepository, UserStatsRepository
from todo.models import Category, Priority, TaskSize, TodoStatus, UserStats


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test_repo.db"

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


class TestTodoRepository:
    """Test TodoRepository functionality."""

    def test_create_todo_basic(self, todo_repo):
        """Test creating a basic todo."""
        todo = todo_repo.create_todo("Test task", "Test description")

        assert todo.id is not None
        assert todo.title == "Test task"
        assert todo.description == "Test description"
        assert todo.status == TodoStatus.PENDING
        assert todo.final_size == TaskSize.MEDIUM
        assert todo.final_priority == Priority.MEDIUM

    def test_create_todo_minimal(self, todo_repo):
        """Test creating a todo with minimal input."""
        todo = todo_repo.create_todo("Minimal task")

        assert todo.id is not None
        assert todo.title == "Minimal task"
        assert todo.description is None
        assert todo.status == TodoStatus.PENDING

    def test_get_by_id_found(self, todo_repo):
        """Test getting todo by ID when it exists."""
        created_todo = todo_repo.create_todo("Test task")
        retrieved_todo = todo_repo.get_by_id(created_todo.id)

        assert retrieved_todo is not None
        assert retrieved_todo.id == created_todo.id
        assert retrieved_todo.title == "Test task"

    def test_get_by_id_not_found(self, todo_repo):
        """Test getting todo by ID when it doesn't exist."""
        retrieved_todo = todo_repo.get_by_id(999)

        assert retrieved_todo is None

    def test_delete_todo_found(self, todo_repo):
        """Test deleting a todo that exists."""
        todo = todo_repo.create_todo("To be deleted")
        result = todo_repo.delete(todo.id)

        assert result is True
        assert todo_repo.get_by_id(todo.id) is None

    def test_delete_todo_not_found(self, todo_repo):
        """Test deleting a todo that doesn't exist."""
        result = todo_repo.delete(999)

        assert result is False

    def test_get_active_todos_empty(self, todo_repo):
        """Test getting active todos when none exist."""
        todos = todo_repo.get_active_todos()

        assert len(todos) == 0

    def test_get_active_todos_with_data(self, todo_repo):
        """Test getting active todos when they exist."""
        # Create some todos
        todo1 = todo_repo.create_todo("Task 1")
        todo2 = todo_repo.create_todo("Task 2")
        todo3 = todo_repo.create_todo("Task 3")

        # Complete one todo
        todo_repo.complete_todo(todo3.id)

        active_todos = todo_repo.get_active_todos()

        # Should only get 2 active todos (todo3 is completed)
        assert len(active_todos) == 2
        active_ids = {todo.id for todo in active_todos}
        assert todo1.id in active_ids
        assert todo2.id in active_ids
        assert todo3.id not in active_ids

    def test_get_active_todos_with_limit(self, todo_repo):
        """Test getting active todos with a limit."""
        # Create multiple todos
        for i in range(5):
            todo_repo.create_todo(f"Task {i+1}")

        todos = todo_repo.get_active_todos(limit=3)

        assert len(todos) == 3

    def test_complete_todo_success(self, todo_repo):
        """Test completing a todo successfully."""
        todo = todo_repo.create_todo("To be completed")
        completed_todo = todo_repo.complete_todo(todo.id)

        assert completed_todo is not None
        assert completed_todo.status == TodoStatus.COMPLETED
        assert completed_todo.completed_at is not None
        assert completed_todo.total_points_earned > 0

    def test_complete_todo_not_found(self, todo_repo):
        """Test completing a non-existent todo."""
        result = todo_repo.complete_todo(999)

        assert result is None

    def test_complete_todo_already_completed(self, todo_repo):
        """Test completing an already completed todo."""
        todo = todo_repo.create_todo("To be completed twice")

        # Complete it once
        first_completion = todo_repo.complete_todo(todo.id)
        assert first_completion is not None

        # Try to complete it again
        second_completion = todo_repo.complete_todo(todo.id)
        assert second_completion is None

    def test_get_overdue_todos_empty(self, todo_repo):
        """Test getting overdue todos when none exist."""
        overdue = todo_repo.get_overdue_todos()

        assert len(overdue) == 0

    def test_row_to_model_conversion(self, todo_repo):
        """Test database row to model conversion."""
        todo = todo_repo.create_todo("Test conversion")
        retrieved = todo_repo.get_by_id(todo.id)

        # Verify status values work (may be string or enum depending on implementation)
        assert retrieved.status in [TodoStatus.PENDING, "pending"]
        assert retrieved.final_size in [TaskSize.MEDIUM, "medium"]
        assert retrieved.final_priority in [Priority.MEDIUM, "medium"]


class TestCategoryRepository:
    """Test CategoryRepository functionality."""

    def test_get_table_name(self, category_repo):
        """Test category repository table name."""
        assert category_repo._get_table_name() == "categories"

    def test_row_to_model(self, category_repo):
        """Test category row to model conversion."""
        # This tests the abstract method implementation
        row = {"id": 1, "name": "Work", "color": "#FF0000", "description": "Work tasks"}

        category = category_repo._row_to_model(row)

        assert isinstance(category, Category)
        assert category.id == 1
        assert category.name == "Work"
        assert category.color == "#FF0000"


class TestUserStatsRepository:
    """Test UserStatsRepository functionality."""

    def test_get_table_name(self, user_stats_repo):
        """Test user stats repository table name."""
        assert user_stats_repo._get_table_name() == "user_stats"

    def test_row_to_model(self, user_stats_repo):
        """Test user stats row to model conversion."""
        row = {
            "id": 1,
            "total_tasks_created": 10,
            "total_tasks_completed": 8,
            "total_points_earned": 100,
            "current_streak": 5,
            "longest_streak": 10,
            "last_activity_date": "2025-08-30",
        }

        stats = user_stats_repo._row_to_model(row)

        assert isinstance(stats, UserStats)
        assert stats.id == 1
        assert stats.total_tasks_created == 10
        assert stats.total_tasks_completed == 8


class TestRepositoryBase:
    """Test base repository functionality."""

    def test_base_repository_methods(self, todo_repo):
        """Test base repository CRUD methods."""
        # Test create through TodoRepository
        todo = todo_repo.create_todo("Base test")
        assert todo.id is not None

        # Test get_by_id (from base)
        retrieved = todo_repo.get_by_id(todo.id)
        assert retrieved is not None
        assert retrieved.id == todo.id

        # Test delete (from base)
        deleted = todo_repo.delete(todo.id)
        assert deleted is True

        # Verify deletion
        not_found = todo_repo.get_by_id(todo.id)
        assert not_found is None

    def test_row_to_dict_helper(self):
        """Test the _row_to_dict helper function."""
        from todo.db.repository import _row_to_dict

        # Test with None result
        result = _row_to_dict(None)
        assert result == {}

        # Test with empty result
        result = _row_to_dict([])
        assert result == {}

        # Test with mock cursor
        from unittest.mock import Mock

        mock_cursor = Mock()
        mock_cursor.description = [["id"], ["name"], ["value"]]

        row_data = [1, "test", "data"]
        result = _row_to_dict(row_data, mock_cursor)

        expected = {"id": 1, "name": "test", "value": "data"}
        assert result == expected

    def test_calculate_base_points(self, todo_repo):
        """Test base points calculation."""
        # This is a private method, test through complete_todo
        small_todo = todo_repo.create_todo("Small task")
        # Update to small size for testing
        db = todo_repo.db.connect()
        db.execute(
            "UPDATE todos SET final_size = 'small' WHERE id = ?", [small_todo.id]
        )

        completed = todo_repo.complete_todo(small_todo.id)
        assert completed.base_points == 1

        # Test medium size
        medium_todo = todo_repo.create_todo("Medium task")
        completed_medium = todo_repo.complete_todo(medium_todo.id)
        assert completed_medium.base_points == 3

        # Test large size
        large_todo = todo_repo.create_todo("Large task")
        db.execute(
            "UPDATE todos SET final_size = 'large' WHERE id = ?", [large_todo.id]
        )
        completed_large = todo_repo.complete_todo(large_todo.id)
        assert completed_large.base_points == 5
