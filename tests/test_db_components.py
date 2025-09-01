"""Tests for database components."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from todo.db.connection import DatabaseConnection
from todo.db.migrations import MigrationManager


@pytest.fixture
def temp_db_path():
    """Create a temporary database path for testing."""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test_db.db"

    yield str(db_path)

    # Cleanup
    if db_path.exists():
        db_path.unlink()
    Path(temp_dir).rmdir()


@pytest.fixture
def temp_db(temp_db_path):
    """Create a temporary database connection for testing."""
    db = DatabaseConnection(temp_db_path)

    yield db

    db.close()


class TestDatabaseConnection:
    """Test DatabaseConnection functionality."""

    def test_connection_creation(self, temp_db_path):
        """Test creating database connection."""
        db = DatabaseConnection(temp_db_path)

        assert str(db.db_path) == temp_db_path
        assert db._connection is None

        db.close()

    def test_connect(self, temp_db):
        """Test connecting to database."""
        conn = temp_db.connect()

        assert conn is not None
        assert temp_db._connection is not None

    def test_context_manager(self, temp_db_path):
        """Test using database connection as context manager."""
        with DatabaseConnection(temp_db_path) as db:
            conn = db.connect()
            assert conn is not None
            assert db._connection is not None

        # Connection should be closed after context
        assert db._connection is None

    def test_initialize_schema(self, temp_db):
        """Test schema initialization."""
        temp_db.initialize_schema()

        # Verify that tables were created
        conn = temp_db.connect()

        # Check that todos table exists
        result = conn.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='todos'
        """).fetchone()

        assert result is not None


class TestMigrationManager:
    """Test MigrationManager functionality."""

    def test_migration_manager_creation(self, temp_db):
        """Test creating migration manager."""
        manager = MigrationManager(temp_db)

        assert manager.db is temp_db

    def test_get_current_version_empty(self, temp_db):
        """Test getting current version when no migrations applied."""
        manager = MigrationManager(temp_db)

        version = manager.get_current_version()

        assert version == 0

    def test_is_schema_initialized_false(self, temp_db):
        """Test schema initialization check when not initialized."""
        manager = MigrationManager(temp_db)

        assert manager.is_schema_initialized() is False

    def test_initialize_schema(self, temp_db):
        """Test schema initialization."""
        manager = MigrationManager(temp_db)

        manager.initialize_schema()

        # Check that tables were created and migration recorded
        assert manager.is_schema_initialized() is True
        assert manager.get_current_version() == 1

    def test_run_migrations_first_time(self, temp_db):
        """Test running migrations for the first time."""
        manager = MigrationManager(temp_db)

        with patch("builtins.print"):
            manager.run_migrations()

        # Should initialize schema
        assert manager.is_schema_initialized() is True

    def test_get_migration_status_success(self, temp_db):
        """Test getting migration status successfully."""
        manager = MigrationManager(temp_db)
        manager.initialize_schema()

        status = manager.get_migration_status()

        assert status["schema_initialized"] is True
        assert status["current_version"] == 1
        assert status["total_migrations_applied"] == 1
