"""Simple E2E tests with isolated databases."""

import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from todo.cli.main import app
from todo.db.connection import DatabaseConnection
from todo.db.migrations import MigrationManager


@pytest.fixture
def e2e_temp_dir():
    """Create a temporary directory for E2E test."""
    temp_dir = tempfile.mkdtemp(prefix="todo_e2e_")
    yield Path(temp_dir)

    # Cleanup
    import shutil

    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def e2e_database(e2e_temp_dir):
    """Create isolated E2E database."""
    db_path = e2e_temp_dir / "e2e_test.db"

    # Create and initialize database
    db = DatabaseConnection(str(db_path))
    migration_manager = MigrationManager(db)
    migration_manager.initialize_schema()

    yield db

    # Cleanup
    db.close()


class TestSimpleE2E:
    """Simple E2E tests to verify database isolation."""

    def test_basic_todo_operations_isolated_db(self, e2e_database):
        """Test basic todo operations with isolated database."""
        # CliRunner not used in this test method

        # Create a proper temporary database path (not an existing file)
        import tempfile

        temp_dir = tempfile.mkdtemp()
        tmp_db_path = Path(temp_dir) / "test_operations.db"

        try:
            # Initialize test database (file shouldn't exist yet)
            test_db = DatabaseConnection(str(tmp_db_path))
            migration_manager = MigrationManager(test_db)
            migration_manager.initialize_schema()

            # Test database operations
            conn = test_db.connect()

            # Insert a test todo directly
            conn.execute("""
                INSERT INTO todos (uuid, title, final_size, final_priority)
                VALUES ('test-uuid', 'Test E2E Todo', 'medium', 'medium')
            """)

            # Verify it exists
            result = conn.execute(
                "SELECT title FROM todos WHERE uuid = 'test-uuid'"
            ).fetchone()
            assert result is not None
            assert result[0] == "Test E2E Todo"

            test_db.close()

        finally:
            # Cleanup
            tmp_db_path.unlink(missing_ok=True)
            Path(temp_dir).rmdir()

    def test_database_isolation(self, e2e_temp_dir):
        """Test that each E2E test gets its own database."""
        # Create multiple databases to simulate isolation
        db_paths = []
        databases = []

        try:
            for i in range(3):
                db_path = e2e_temp_dir / f"isolated_test_{i}.db"
                db = DatabaseConnection(str(db_path))
                migration_manager = MigrationManager(db)
                migration_manager.initialize_schema()

                # Add different data to each database
                conn = db.connect()
                conn.execute(
                    """
                    INSERT INTO todos (uuid, title, final_size, final_priority)
                    VALUES (?, ?, 'medium', 'medium')
                """,
                    [f"uuid-{i}", f"Test Todo {i}"],
                )

                db_paths.append(db_path)
                databases.append(db)

            # Verify each database has only its own data
            for i, db in enumerate(databases):
                conn = db.connect()
                todos = conn.execute("SELECT title FROM todos").fetchall()

                assert len(todos) == 1
                assert todos[0][0] == f"Test Todo {i}"

        finally:
            # Cleanup all databases
            for db in databases:
                db.close()
            for db_path in db_paths:
                db_path.unlink(missing_ok=True)

    def test_cli_with_isolated_database(self):
        """Test CLI operations work with database isolation."""
        runner = CliRunner()

        # Create proper temp directory and database path
        temp_dir = tempfile.mkdtemp()
        tmp_db_path = Path(temp_dir) / "cli_test.db"

        try:
            # Set environment variable to use our test database
            test_env = {
                "TODO_DATABASE_PATH": str(tmp_db_path),
            }

            # Test version command (should work without database initialization issues)
            result = runner.invoke(app, ["version"], env=test_env)
            assert result.exit_code == 0
            assert "todo version 0.1.0" in result.output

        finally:
            # Cleanup
            tmp_db_path.unlink(missing_ok=True)
            Path(temp_dir).rmdir()

    def test_e2e_database_operations_direct(self, e2e_database):
        """Test database operations directly for E2E scenarios."""
        # This tests the database layer that would be used by E2E tests
        conn = e2e_database.connect()

        # Test creating todos
        todos_to_create = [
            ("E2E Test Todo 1", "First test todo"),
            ("E2E Test Todo 2", "Second test todo"),
            ("E2E Test Todo 3", "Third test todo"),
        ]

        created_ids = []
        for title, description in todos_to_create:
            cursor = conn.execute(
                """
                INSERT INTO todos (uuid, title, description, final_size, final_priority)
                VALUES (?, ?, ?, 'medium', 'medium')
                RETURNING id
            """,
                [f"uuid-{title}", title, description],
            )
            result = cursor.fetchone()
            created_ids.append(result[0])

        # Test reading todos
        todos = conn.execute("SELECT title FROM todos ORDER BY id").fetchall()
        assert len(todos) == 3
        for i, (expected_title, _) in enumerate(todos_to_create):
            assert todos[i][0] == expected_title

        # Test completing todos
        completed_id = created_ids[1]  # Complete the second todo
        conn.execute(
            """
            UPDATE todos
            SET status = 'completed', completed_at = CURRENT_TIMESTAMP, total_points_earned = 3
            WHERE id = ?
        """,
            [completed_id],
        )

        # Verify completion
        completed = conn.execute(
            """
            SELECT status, total_points_earned FROM todos WHERE id = ?
        """,
            [completed_id],
        ).fetchone()

        assert completed[0] == "completed"
        assert completed[1] == 3

        # Test counts
        total_count = conn.execute("SELECT COUNT(*) FROM todos").fetchone()[0]
        completed_count = conn.execute(
            "SELECT COUNT(*) FROM todos WHERE status = 'completed'"
        ).fetchone()[0]
        pending_count = conn.execute(
            "SELECT COUNT(*) FROM todos WHERE status = 'pending'"
        ).fetchone()[0]

        assert total_count == 3
        assert completed_count == 1
        assert pending_count == 2

    def test_e2e_schema_completeness(self, e2e_database):
        """Test that E2E database has complete schema."""
        conn = e2e_database.connect()

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

            assert result is not None, f"Table {table} should exist in E2E database"

        # Check migration was recorded
        migration = conn.execute("""
            SELECT version, name FROM schema_migrations WHERE version = 1
        """).fetchone()

        assert migration is not None
        assert migration[0] == 1
        assert migration[1] == "initial_schema"


class TestE2EDataIsolation:
    """Test data isolation between E2E test runs."""

    def test_fresh_database_each_test(self, e2e_database):
        """Each test should get a fresh database."""
        conn = e2e_database.connect()

        # Add some data
        conn.execute("""
            INSERT INTO todos (uuid, title, final_size, final_priority)
            VALUES ('isolation-test-1', 'Isolation Test Todo', 'medium', 'medium')
        """)

        # Verify it exists
        count = conn.execute("SELECT COUNT(*) FROM todos").fetchone()[0]
        assert count == 1

    def test_no_data_carryover(self, e2e_database):
        """This test should not see data from previous test."""
        conn = e2e_database.connect()

        # Should start with empty todos table
        count = conn.execute("SELECT COUNT(*) FROM todos").fetchone()[0]
        assert count == 0

        # Add different data
        conn.execute("""
            INSERT INTO todos (uuid, title, final_size, final_priority)
            VALUES ('isolation-test-2', 'Different Test Todo', 'large', 'high')
        """)

        # Verify only our data exists
        todos = conn.execute("SELECT title FROM todos").fetchall()
        assert len(todos) == 1
        assert todos[0][0] == "Different Test Todo"

    def test_concurrent_test_isolation(self, e2e_temp_dir):
        """Test that multiple test databases can coexist."""
        databases = []
        db_paths = []

        try:
            # Create multiple test databases
            for i in range(5):
                db_path = e2e_temp_dir / f"concurrent_test_{i}.db"
                db = DatabaseConnection(str(db_path))
                migration_manager = MigrationManager(db)
                migration_manager.initialize_schema()

                # Add unique data to each
                conn = db.connect()
                conn.execute(
                    """
                    INSERT INTO todos (uuid, title, final_size, final_priority)
                    VALUES (?, ?, 'medium', 'medium')
                """,
                    [f"concurrent-{i}", f"Concurrent Test {i}"],
                )

                databases.append(db)
                db_paths.append(db_path)

            # Verify each database maintains its isolation
            for i, db in enumerate(databases):
                conn = db.connect()

                # Should have exactly one todo with correct data
                todos = conn.execute("SELECT title FROM todos").fetchall()
                assert len(todos) == 1
                assert todos[0][0] == f"Concurrent Test {i}"

                # Should have proper schema
                tables = conn.execute("""
                    SELECT COUNT(*) FROM sqlite_master WHERE type='table'
                """).fetchone()[0]
                assert tables >= 9  # Should have all our tables

        finally:
            # Cleanup
            for db in databases:
                db.close()
            for db_path in db_paths:
                db_path.unlink(missing_ok=True)
