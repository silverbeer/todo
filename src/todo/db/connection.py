"""Database connection management for DuckDB."""

from pathlib import Path
from typing import Any

import duckdb


class DatabaseConnection:
    """Manages DuckDB connection and initialization."""

    def __init__(self, db_path: str | None = None):
        """Initialize database connection manager.

        Args:
            db_path: Path to database file. If None, uses default from config.
        """
        if db_path is None:
            # Default database path following XDG standards
            db_path = "~/.local/share/todo/todos.db"

        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: duckdb.DuckDBPyConnection | None = None

    def connect(self) -> duckdb.DuckDBPyConnection:
        """Get or create database connection.

        Returns:
            Active DuckDB connection.
        """
        if self._connection is None:
            self._connection = duckdb.connect(str(self.db_path))
        return self._connection

    def close(self) -> None:
        """Close database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None

    def execute_script(self, script_path: Path) -> None:
        """Execute SQL script file.

        Args:
            script_path: Path to SQL script file.
        """
        conn = self.connect()
        with script_path.open() as f:
            sql_content = f.read()

        # Split by semicolon and execute each statement
        statements = [stmt.strip() for stmt in sql_content.split(";") if stmt.strip()]

        for statement in statements:
            try:
                conn.execute(statement)
            except Exception as e:
                print(f"Error executing statement: {statement[:100]}...")
                raise e

    def initialize_schema(self) -> None:
        """Initialize database schema if needed."""
        schema_path = Path(__file__).parent / "schema.sql"
        self.execute_script(schema_path)

    def get_database_info(self) -> dict[str, Any]:
        """Get database information for debugging.

        Returns:
            Dict with database stats and info.
        """
        conn = self.connect()

        # Get table list
        tables_result = conn.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'main'
            ORDER BY table_name
        """).fetchall()
        tables = [row[0] for row in tables_result]

        # Get row counts for each table
        table_counts = {}
        for table in tables:
            try:
                count_result = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                table_counts[table] = count_result[0] if count_result else 0
            except Exception:
                table_counts[table] = "Error"

        return {
            "database_path": str(self.db_path),
            "database_exists": self.db_path.exists(),
            "database_size_bytes": self.db_path.stat().st_size
            if self.db_path.exists()
            else 0,
            "tables": tables,
            "table_counts": table_counts,
        }

    def __enter__(self) -> "DatabaseConnection":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()
