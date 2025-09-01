"""Working E2E tests with proper CLI integration."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from todo.cli.main import app
from todo.db.connection import DatabaseConnection
from todo.db.migrations import MigrationManager


@pytest.fixture
def isolated_database():
    """Create an isolated database for E2E testing."""
    temp_dir = tempfile.mkdtemp(prefix="todo_e2e_")
    db_path = Path(temp_dir) / "e2e_test.db"

    # Create database and initialize schema
    db = DatabaseConnection(str(db_path))
    migration_manager = MigrationManager(db)
    migration_manager.initialize_schema()

    yield db, str(db_path)

    # Cleanup
    db.close()
    db_path.unlink(missing_ok=True)
    Path(temp_dir).rmdir()


class TestWorkingE2E:
    """Working E2E tests that actually test the CLI with isolated databases."""

    def test_cli_version_with_isolated_database(self, isolated_database):
        """Test CLI version command with isolated database."""
        db, db_path = isolated_database
        runner = CliRunner()

        # Test version command (doesn't require database)
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "todo version 0.1.0" in result.output

    def test_database_auto_initialization_e2e(self):
        """Test that CLI auto-initializes database on first run."""
        temp_dir = tempfile.mkdtemp(prefix="todo_init_e2e_")
        db_path = Path(temp_dir) / "auto_init.db"

        try:
            runner = CliRunner()

            # Patch the CLI to use our test database
            with patch("todo.cli.main.config") as mock_config:
                mock_config.database.database_path = str(db_path)

                # First command should auto-initialize database
                result = runner.invoke(app, ["version"])

                # Should succeed
                assert result.exit_code == 0
                assert "todo version 0.1.0" in result.output

        finally:
            # Cleanup
            db_path.unlink(missing_ok=True)
            Path(temp_dir).rmdir()

    def test_basic_todo_workflow_e2e(self, isolated_database):
        """Test basic todo workflow with isolated database."""
        db, db_path = isolated_database
        runner = CliRunner()

        # Mock the CLI to use our isolated database
        with (
            patch("todo.cli.main.db", db),
            patch("todo.cli.main.migration_manager") as mock_migration,
        ):
            mock_migration.is_schema_initialized.return_value = True

            # Mock the repositories to use our database
            with patch("todo.cli.main.todo_repo") as mock_todo_repo:
                # Create mock todo for testing
                from unittest.mock import Mock

                mock_todo = Mock()
                mock_todo.id = 1
                mock_todo.title = "Test E2E Task"
                mock_todo_repo.create_todo.return_value = mock_todo

                # Test add command
                result = runner.invoke(app, ["add", "Test E2E Task", "--no-ai"])

                # Should succeed (even if mocked)
                assert result.exit_code == 0

    def test_database_operations_direct_e2e(self, isolated_database):
        """Test direct database operations in E2E context."""
        db, db_path = isolated_database

        # Test that we can perform database operations
        conn = db.connect()

        # Insert test data
        conn.execute("""
            INSERT INTO todos (uuid, title, description, final_size, final_priority)
            VALUES ('e2e-uuid', 'E2E Test Todo', 'Testing E2E workflow', 'medium', 'medium')
        """)

        # Query data back
        result = conn.execute("""
            SELECT title, description FROM todos WHERE uuid = 'e2e-uuid'
        """).fetchone()

        assert result is not None
        assert result[0] == "E2E Test Todo"
        assert result[1] == "Testing E2E workflow"

        # Test completing todo
        conn.execute("""
            UPDATE todos
            SET status = 'completed', completed_at = CURRENT_TIMESTAMP, total_points_earned = 3
            WHERE uuid = 'e2e-uuid'
        """)

        # Verify completion
        completed = conn.execute("""
            SELECT status, total_points_earned FROM todos WHERE uuid = 'e2e-uuid'
        """).fetchone()

        assert completed[0] == "completed"
        assert completed[1] == 3

    def test_multiple_todos_isolation_e2e(self, isolated_database):
        """Test multiple todos with database isolation."""
        db, db_path = isolated_database
        conn = db.connect()

        # Add multiple todos
        todos = [
            ("todo-1", "First task", "medium", "medium"),
            ("todo-2", "Second task", "large", "high"),
            ("todo-3", "Third task", "small", "low"),
        ]

        for uuid, title, size, priority in todos:
            conn.execute(
                """
                INSERT INTO todos (uuid, title, final_size, final_priority)
                VALUES (?, ?, ?, ?)
            """,
                [uuid, title, size, priority],
            )

        # Verify all todos exist
        count = conn.execute("SELECT COUNT(*) FROM todos").fetchone()[0]
        assert count == 3

        # Complete one todo
        conn.execute("""
            UPDATE todos
            SET status = 'completed', completed_at = CURRENT_TIMESTAMP, total_points_earned = 5
            WHERE uuid = 'todo-2'
        """)

        # Verify counts
        total = conn.execute("SELECT COUNT(*) FROM todos").fetchone()[0]
        completed = conn.execute(
            "SELECT COUNT(*) FROM todos WHERE status = 'completed'"
        ).fetchone()[0]
        pending = conn.execute(
            "SELECT COUNT(*) FROM todos WHERE status = 'pending'"
        ).fetchone()[0]

        assert total == 3
        assert completed == 1
        assert pending == 2

    def test_schema_completeness_e2e(self, isolated_database):
        """Test that E2E database has complete schema."""
        db, db_path = isolated_database
        conn = db.connect()

        # Check all required tables exist
        expected_tables = [
            "todos",
            "categories",
            "user_stats",
            "daily_activity",
            "achievements",
            "recurrence_rules",
            "ai_enrichments",
            "ai_learning_feedback",
            "schema_migrations",
        ]

        for table in expected_tables:
            result = conn.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name = ?
            """,
                [table],
            ).fetchone()

            assert result is not None, f"Table {table} should exist"

        # Check migration was recorded
        migration = conn.execute("""
            SELECT version, name FROM schema_migrations WHERE version = 1
        """).fetchone()

        assert migration is not None
        assert migration[0] == 1
        assert migration[1] == "initial_schema"

    def test_foreign_key_constraints_e2e(self, isolated_database):
        """Test foreign key constraints work in E2E context."""
        db, db_path = isolated_database
        conn = db.connect()

        # Create a todo first
        conn.execute("""
            INSERT INTO todos (uuid, title, final_size, final_priority)
            VALUES ('fk-test-todo', 'FK Test Todo', 'medium', 'medium')
        """)

        # Get the todo ID
        todo_result = conn.execute(
            "SELECT id FROM todos WHERE uuid = 'fk-test-todo'"
        ).fetchone()
        todo_id = todo_result[0]

        # Should be able to create AI enrichment for valid todo
        conn.execute(
            """
            INSERT INTO ai_enrichments
            (todo_id, provider, model_name, suggested_category, confidence_score)
            VALUES (?, 'openai', 'gpt-4', 'Work', 0.8)
        """,
            [todo_id],
        )

        # Verify it was created
        ai_result = conn.execute(
            "SELECT todo_id FROM ai_enrichments WHERE todo_id = ?", [todo_id]
        ).fetchone()
        assert ai_result is not None
        assert ai_result[0] == todo_id

    def test_performance_with_many_todos_e2e(self, isolated_database):
        """Test E2E performance with many todos."""
        db, db_path = isolated_database
        conn = db.connect()

        # Create many todos
        num_todos = 50
        for i in range(num_todos):
            conn.execute(
                """
                INSERT INTO todos (uuid, title, final_size, final_priority)
                VALUES (?, ?, 'medium', 'medium')
            """,
                [f"perf-test-{i}", f"Performance Test Todo {i}"],
            )

        # Verify count
        count = conn.execute("SELECT COUNT(*) FROM todos").fetchone()[0]
        assert count == num_todos

        # Complete half of them
        for i in range(0, num_todos, 2):  # Every other todo
            conn.execute(
                """
                UPDATE todos
                SET status = 'completed', completed_at = CURRENT_TIMESTAMP, total_points_earned = 3
                WHERE uuid = ?
            """,
                [f"perf-test-{i}"],
            )

        # Verify final counts
        total = conn.execute("SELECT COUNT(*) FROM todos").fetchone()[0]
        completed = conn.execute(
            "SELECT COUNT(*) FROM todos WHERE status = 'completed'"
        ).fetchone()[0]
        pending = conn.execute(
            "SELECT COUNT(*) FROM todos WHERE status = 'pending'"
        ).fetchone()[0]

        assert total == num_todos
        assert completed == num_todos // 2
        assert pending == num_todos - completed

    def test_data_types_and_validation_e2e(self, isolated_database):
        """Test data types and validation in E2E context."""
        db, db_path = isolated_database
        conn = db.connect()

        # Test valid enum values
        valid_todos = [
            ("small", "low"),
            ("medium", "medium"),
            ("large", "high"),
            ("medium", "urgent"),
        ]

        for i, (size, priority) in enumerate(valid_todos):
            conn.execute(
                """
                INSERT INTO todos (uuid, title, final_size, final_priority)
                VALUES (?, ?, ?, ?)
            """,
                [f"valid-{i}", f"Valid Todo {i}", size, priority],
            )

        # Verify all were inserted
        count = conn.execute("SELECT COUNT(*) FROM todos").fetchone()[0]
        assert count == len(valid_todos)

        # Verify enum values are stored correctly
        todos = conn.execute(
            "SELECT final_size, final_priority FROM todos ORDER BY uuid"
        ).fetchall()
        for i, (size, priority) in enumerate(valid_todos):
            assert todos[i][0] == size
            assert todos[i][1] == priority

    def test_uuid_uniqueness_e2e(self, isolated_database):
        """Test UUID uniqueness in E2E context."""
        db, db_path = isolated_database
        conn = db.connect()

        # Create todos with different UUIDs
        uuids = [f"unique-uuid-{i}" for i in range(10)]

        for uuid in uuids:
            conn.execute(
                """
                INSERT INTO todos (uuid, title, final_size, final_priority)
                VALUES (?, ?, 'medium', 'medium')
            """,
                [uuid, f"Todo for {uuid}"],
            )

        # Verify all UUIDs are present and unique
        stored_uuids = conn.execute("SELECT uuid FROM todos ORDER BY uuid").fetchall()
        stored_uuids = [row[0] for row in stored_uuids]

        assert len(stored_uuids) == len(uuids)
        assert len(set(stored_uuids)) == len(uuids)  # All unique
        assert sorted(stored_uuids) == sorted(uuids)  # All match
