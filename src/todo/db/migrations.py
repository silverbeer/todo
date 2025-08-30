"""Database migration management."""

import contextlib
from typing import Any, NamedTuple

from .connection import DatabaseConnection


class Migration(NamedTuple):
    """Represents a database migration."""

    version: int
    name: str
    description: str


class MigrationManager:
    """Manages database schema migrations."""

    def __init__(self, db_connection: DatabaseConnection):
        """Initialize migration manager.

        Args:
            db_connection: Database connection instance.
        """
        self.db = db_connection
        self._ensure_migration_table()

    def _ensure_migration_table(self) -> None:
        """Create migration tracking table if it doesn't exist."""
        conn = self.db.connect()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    def get_current_version(self) -> int:
        """Get current schema version.

        Returns:
            Current schema version number.
        """
        conn = self.db.connect()
        result = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        return result[0] if result and result[0] is not None else 0

    def get_applied_migrations(self) -> list[Migration]:
        """Get list of applied migrations.

        Returns:
            List of applied migrations.
        """
        conn = self.db.connect()
        results = conn.execute("""
            SELECT version, name, 'Applied migration' as description
            FROM schema_migrations
            ORDER BY version
        """).fetchall()

        return [Migration(row[0], row[1], row[2]) for row in results]

    def is_schema_initialized(self) -> bool:
        """Check if database schema has been initialized.

        Returns:
            True if schema is initialized, False otherwise.
        """
        try:
            current_version = self.get_current_version()
            return current_version >= 1
        except Exception:
            return False

    def initialize_schema(self) -> None:
        """Initialize database schema from scratch."""
        conn = self.db.connect()

        # First initialize the schema
        self.db.initialize_schema()

        # Then record the migration
        try:
            conn.execute("""
                INSERT INTO schema_migrations (version, name)
                VALUES (1, 'initial_schema')
                ON CONFLICT(version) DO NOTHING
            """)
            print("✅ Database schema initialized (v1: initial_schema)")
        except Exception as e:
            print(f"❌ Error recording initial migration: {e}")
            raise

    def run_migrations(self) -> None:
        """Run all pending migrations."""
        if not self.is_schema_initialized():
            print("🔧 Initializing database schema...")
            self.initialize_schema()
        else:
            current_version = self.get_current_version()
            print(f"✅ Database schema is up to date (v{current_version})")

    def reset_database(self) -> None:
        """Reset database by dropping all tables and reinitializing.

        Warning: This will delete all data!
        """
        conn = self.db.connect()

        # Drop tables in reverse dependency order
        # First drop child tables that reference other tables
        drop_order = [
            "ai_enrichments",
            "ai_learning_feedback",
            "todos",
            "daily_activity",
            "achievements",
            "user_stats",
            "recurrence_rules",
            "categories",
            "schema_migrations",
        ]

        for table_name in drop_order:
            with contextlib.suppress(Exception):
                conn.execute(f"DROP TABLE IF EXISTS {table_name}")

        print("🗑️  Dropped all existing tables")

        # Reinitialize schema
        self.initialize_schema()
        print("✅ Database reset complete")

    def get_migration_status(self) -> dict[str, Any]:
        """Get detailed migration status information.

        Returns:
            Dict with migration status details.
        """
        try:
            current_version = self.get_current_version()
            applied_migrations = self.get_applied_migrations()
            schema_initialized = self.is_schema_initialized()

            return {
                "schema_initialized": schema_initialized,
                "current_version": current_version,
                "applied_migrations": [
                    {"version": m.version, "name": m.name, "description": m.description}
                    for m in applied_migrations
                ],
                "total_migrations_applied": len(applied_migrations),
            }
        except Exception as e:
            return {
                "schema_initialized": False,
                "current_version": 0,
                "error": str(e),
                "applied_migrations": [],
                "total_migrations_applied": 0,
            }
