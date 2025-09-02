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
            # Run any pending migrations
            if current_version < 2:
                self._run_migration_v2_fix_foreign_keys()
            print(f"✅ Database schema is up to date (v{self.get_current_version()})")

    def _run_migration_v2_fix_foreign_keys(self) -> None:
        """Migration v2: Fix DuckDB foreign key constraints for ai_enrichments table."""
        conn = self.db.connect()

        try:
            print("🔧 Running migration v2: Fixing foreign key constraints...")

            # Check if we need to run this migration
            current_version = self.get_current_version()
            if current_version >= 2:
                return

            # Save existing ai_enrichments data if table exists
            backup_data = []
            try:
                backup_data = conn.execute("SELECT * FROM ai_enrichments").fetchall()
                print(
                    f"📦 Backing up {len(backup_data)} existing AI enrichment records"
                )
            except Exception:
                print("📋 No existing ai_enrichments table found - creating new one")

            # Drop the problematic table
            conn.execute("DROP TABLE IF EXISTS ai_enrichments")

            # Recreate the table with proper foreign key constraint
            conn.execute("""
                CREATE SEQUENCE IF NOT EXISTS ai_enrichments_id_seq;
                CREATE TABLE IF NOT EXISTS ai_enrichments (
                    id INTEGER PRIMARY KEY DEFAULT nextval('ai_enrichments_id_seq'),
                    todo_id INTEGER NOT NULL,
                    provider VARCHAR(20) NOT NULL CHECK (provider IN ('openai', 'anthropic')),
                    model_name VARCHAR(50) NOT NULL,

                    -- AI suggestions
                    suggested_category VARCHAR(50),
                    suggested_priority VARCHAR(10) CHECK (suggested_priority IN ('low', 'medium', 'high', 'urgent')),
                    suggested_size VARCHAR(10) CHECK (suggested_size IN ('small', 'medium', 'large')),
                    estimated_duration_minutes INTEGER CHECK (estimated_duration_minutes > 0),

                    -- Recurrence detection
                    is_recurring_candidate BOOLEAN DEFAULT FALSE,
                    suggested_recurrence_pattern VARCHAR(100),

                    -- AI reasoning and confidence
                    reasoning TEXT,
                    confidence_score REAL DEFAULT 0.5 CHECK (confidence_score BETWEEN 0.0 AND 1.0),

                    -- Context
                    context_keywords TEXT,  -- JSON array of keywords
                    similar_tasks_found INTEGER DEFAULT 0 CHECK (similar_tasks_found >= 0),

                    -- Performance tracking
                    enriched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processing_time_ms INTEGER CHECK (processing_time_ms >= 0)
                );
            """)

            # Restore data
            for row in backup_data:
                placeholders = ", ".join(["?" for _ in row[1:]])  # Skip id column
                conn.execute(
                    f"INSERT INTO ai_enrichments (todo_id, provider, model_name, suggested_category, suggested_priority, suggested_size, estimated_duration_minutes, is_recurring_candidate, suggested_recurrence_pattern, reasoning, confidence_score, context_keywords, similar_tasks_found, enriched_at, processing_time_ms) VALUES ({placeholders})",
                    row[1:],
                )

            # Recreate indexes
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ai_enrichments_todo ON ai_enrichments(todo_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ai_enrichments_provider ON ai_enrichments(provider)"
            )

            # Record the migration
            conn.execute("""
                INSERT INTO schema_migrations (version, name)
                VALUES (2, 'fix_foreign_key_constraints')
            """)

            print("✅ Migration v2 completed: Foreign key constraints fixed")

        except Exception as e:
            print(f"❌ Migration v2 failed: {e}")
            raise

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
