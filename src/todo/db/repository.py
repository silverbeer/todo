"""Repository implementations for database operations."""

from abc import ABC, abstractmethod
from datetime import date
from typing import Any, TypeVar
from uuid import uuid4

from ..models import (
    Achievement,
    Category,
    DailyActivity,
    Priority,
    TaskSize,
    Todo,
    TodoStatus,
    UserStats,
)
from .connection import DatabaseConnection

T = TypeVar("T")


def _row_to_dict(result: Any, cursor: Any = None) -> dict[str, Any]:
    """Convert DuckDB result row to dictionary.

    Args:
        result: DuckDB result row.
        cursor: DuckDB cursor with description.

    Returns:
        Dictionary representation of the row.
    """
    if not result:
        return {}
    if cursor and hasattr(cursor, "description"):
        column_names = [col[0] for col in cursor.description]
        return dict(zip(column_names, result))
    # Fallback for when no cursor is provided - return empty dict
    return {}


class BaseRepository[T](ABC):
    """Base repository with common CRUD operations."""

    def __init__(self, db_connection: DatabaseConnection):
        """Initialize repository with database connection.

        Args:
            db_connection: Database connection instance.
        """
        self.db = db_connection
        self.table_name = self._get_table_name()

    @abstractmethod
    def _get_table_name(self) -> str:
        """Return the table name for this repository."""
        pass

    def get_by_id(self, record_id: int) -> T | None:
        """Get record by ID.

        Args:
            record_id: ID of the record to retrieve.

        Returns:
            Record if found, None otherwise.
        """
        conn = self.db.connect()
        cursor = conn.execute(
            f"SELECT * FROM {self.table_name} WHERE id = ?", [record_id]
        )
        result = cursor.fetchone()

        if result:
            return self._row_to_model(_row_to_dict(result, cursor))
        return None

    def delete(self, record_id: int) -> bool:
        """Delete record by ID.

        Args:
            record_id: ID of the record to delete.

        Returns:
            True if deleted, False if not found.
        """
        conn = self.db.connect()

        # First check if record exists
        exists = self.get_by_id(record_id) is not None
        if not exists:
            return False

        # Now delete it
        conn.execute(f"DELETE FROM {self.table_name} WHERE id = ?", [record_id])

        # DuckDB should report rowcount, but let's check by trying to retrieve again
        return self.get_by_id(record_id) is None

    @abstractmethod
    def _row_to_model(self, row: dict[str, Any]) -> T:
        """Convert database row to Pydantic model.

        Args:
            row: Database row as dictionary.

        Returns:
            Pydantic model instance.
        """
        pass


class CategoryRepository(BaseRepository[Category]):
    """Repository for Category operations."""

    def _get_table_name(self) -> str:
        return "categories"

    def _row_to_model(self, row: dict[str, Any]) -> Category:
        """Convert database row to Category model."""
        return Category(**row)

    def get_all(self) -> list[Category]:
        """Get all categories.

        Returns:
            List of all categories.
        """
        conn = self.db.connect()
        cursor = conn.execute(f"SELECT * FROM {self.table_name} ORDER BY name")
        results = cursor.fetchall()

        if not results:
            return []

        # Get column names from cursor description
        column_names = [desc[0] for desc in cursor.description]
        return [self._row_to_model(dict(zip(column_names, row))) for row in results]

    def get_by_name(self, name: str) -> Category | None:
        """Get category by name.

        Args:
            name: Category name.

        Returns:
            Category if found, None otherwise.
        """
        conn = self.db.connect()
        cursor = conn.execute(f"SELECT * FROM {self.table_name} WHERE name = ?", [name])
        result = cursor.fetchone()

        if result:
            return self._row_to_model(_row_to_dict(result, cursor))
        return None

    def create(self, category: Category) -> Category:
        """Create a new category.

        Args:
            category: Category to create.

        Returns:
            Created category with assigned ID.
        """
        conn = self.db.connect()
        cursor = conn.execute(
            """
            INSERT INTO categories (name, color, icon, description)
            VALUES (?, ?, ?, ?)
            RETURNING *
        """,
            [category.name, category.color, category.icon, category.description],
        )
        result = cursor.fetchone()

        return self._row_to_model(_row_to_dict(result, cursor))


class TodoRepository(BaseRepository[Todo]):
    """Repository for Todo operations."""

    def _get_table_name(self) -> str:
        return "todos"

    def _row_to_model(self, row: dict[str, Any]) -> Todo:
        """Convert database row to Todo model."""
        # Handle enum conversions
        if row.get("status"):
            row["status"] = TodoStatus(row["status"])
        if row.get("user_override_size"):
            row["user_override_size"] = TaskSize(row["user_override_size"])
        if row.get("ai_suggested_size"):
            row["ai_suggested_size"] = TaskSize(row["ai_suggested_size"])
        if row.get("final_size"):
            row["final_size"] = TaskSize(row["final_size"])
        if row.get("user_override_priority"):
            row["user_override_priority"] = Priority(row["user_override_priority"])
        if row.get("ai_suggested_priority"):
            row["ai_suggested_priority"] = Priority(row["ai_suggested_priority"])
        if row.get("final_priority"):
            row["final_priority"] = Priority(row["final_priority"])

        return Todo(**row)

    def create_todo(self, title: str, description: str | None = None) -> Todo:
        """Create a new todo with minimal input.

        Args:
            title: Todo title.
            description: Optional todo description.

        Returns:
            Created todo.
        """
        conn = self.db.connect()

        todo_uuid = str(uuid4())
        cursor = conn.execute(
            """
            INSERT INTO todos (uuid, title, description, final_size, final_priority)
            VALUES (?, ?, ?, 'medium', 'medium')
            RETURNING *
        """,
            [todo_uuid, title, description],
        )
        result = cursor.fetchone()

        return self._row_to_model(_row_to_dict(result, cursor))

    def get_active_todos(self, limit: int | None = None) -> list[Todo]:
        """Get todos that are not completed or archived.

        Args:
            limit: Maximum number of todos to return.

        Returns:
            List of active todos.
        """
        conn = self.db.connect()

        query = """
        SELECT t.*
        FROM todos t
        WHERE t.status IN ('pending', 'in_progress')
        ORDER BY
            CASE t.final_priority
                WHEN 'urgent' THEN 1
                WHEN 'high' THEN 2
                WHEN 'medium' THEN 3
                ELSE 4
            END,
            t.due_date ASC,
            t.created_at DESC
        """

        params = []
        if limit:
            query += " LIMIT ?"
            params.append(limit)

        cursor = conn.execute(query, params)
        results = cursor.fetchall()

        if not results:
            return []

        # Get column names from cursor description
        column_names = [desc[0] for desc in cursor.description]
        return [self._row_to_model(dict(zip(column_names, row))) for row in results]

    def get_overdue_todos(self) -> list[Todo]:
        """Get todos that are overdue.

        Returns:
            List of overdue todos.
        """
        conn = self.db.connect()

        cursor = conn.execute("""
        SELECT t.*
        FROM todos t
        WHERE t.due_date < CURRENT_DATE
        AND t.status NOT IN ('completed', 'archived')
        ORDER BY t.due_date ASC
        """)
        results = cursor.fetchall()

        if not results:
            return []

        # Get column names from cursor description
        column_names = [desc[0] for desc in cursor.description]
        return [self._row_to_model(dict(zip(column_names, row))) for row in results]

    def complete_todo(self, todo_id: int) -> Todo | None:
        """Mark todo as completed and calculate points.

        Args:
            todo_id: ID of the todo to complete.

        Returns:
            Updated todo if successful, None otherwise.
        """
        conn = self.db.connect()

        try:
            # Get current todo
            todo = self.get_by_id(todo_id)
            if not todo or todo.status == TodoStatus.COMPLETED:
                return None

            # Calculate points
            base_points = self._calculate_base_points(todo.final_size)
            bonus_points = 0  # TODO: Implement bonus calculation
            total_points = base_points + bonus_points

            # Update todo
            result = conn.execute(
                """
                UPDATE todos
                SET status = 'completed',
                    completed_at = CURRENT_TIMESTAMP,
                    base_points = ?,
                    bonus_points = ?,
                    total_points_earned = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """,
                [base_points, bonus_points, total_points, todo_id],
            )

            if result.rowcount == 0:
                return None

            # Update stats
            self._update_completion_stats(conn, total_points)

            # Get updated todo
            return self.get_by_id(todo_id)

        except Exception as e:
            raise e

    def get_by_uuid(self, uuid: str) -> Todo | None:
        """Get todo by UUID.

        Args:
            uuid: Todo UUID.

        Returns:
            Todo if found, None otherwise.
        """
        conn = self.db.connect()
        cursor = conn.execute("SELECT * FROM todos WHERE uuid = ?", [uuid])
        result = cursor.fetchone()

        if result:
            return self._row_to_model(_row_to_dict(result, cursor))
        return None

    def update_todo(self, todo_id: int, updates: dict[str, Any]) -> Todo | None:
        """Update todo with given fields.

        Args:
            todo_id: ID of the todo to update.
            updates: Fields to update.

        Returns:
            Updated todo if successful, None otherwise.
        """
        if not updates:
            return self.get_by_id(todo_id)

        conn = self.db.connect()

        # Convert enum values to strings
        for key, value in updates.items():
            if hasattr(value, "value"):  # Enum handling
                updates[key] = value.value

        # Build update query
        set_clauses = [f"{key} = ?" for key in updates]
        set_clause = ", ".join(set_clauses)
        values = list(updates.values()) + [todo_id]

        cursor = conn.execute(
            f"""
            UPDATE todos
            SET {set_clause}, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            RETURNING *
        """,
            values,
        )
        result = cursor.fetchone()

        if result:
            return self._row_to_model(_row_to_dict(result, cursor))
        return None

    def _calculate_base_points(self, size: TaskSize) -> int:
        """Calculate base points for task size.

        Args:
            size: Task size.

        Returns:
            Base points for the size.
        """
        points_map = {
            TaskSize.SMALL: 1,
            TaskSize.MEDIUM: 3,
            TaskSize.LARGE: 5,
        }
        return points_map.get(size, 3)

    def _update_completion_stats(self, conn: Any, points_earned: int) -> None:
        """Update user stats and daily activity after completion.

        Args:
            conn: Database connection.
            points_earned: Points earned from completion.
        """
        today = date.today()

        # Upsert daily activity
        conn.execute(
            """
            INSERT INTO daily_activity (activity_date, tasks_completed, total_points_earned)
            VALUES (?, 1, ?)
            ON CONFLICT(activity_date)
            DO UPDATE SET
                tasks_completed = daily_activity.tasks_completed + 1,
                total_points_earned = daily_activity.total_points_earned + ?,
                updated_at = now()
        """,
            [today, points_earned, points_earned],
        )

        # Update user stats
        conn.execute(
            """
            UPDATE user_stats
            SET total_tasks_completed = total_tasks_completed + 1,
                total_points = total_points + ?,
                last_completion_date = ?,
                updated_at = now()
        """,
            [points_earned, today],
        )


class UserStatsRepository(BaseRepository[UserStats]):
    """Repository for UserStats operations."""

    def _get_table_name(self) -> str:
        return "user_stats"

    def _row_to_model(self, row: dict[str, Any]) -> UserStats:
        """Convert database row to UserStats model."""
        return UserStats(**row)

    def get_current_stats(self) -> UserStats | None:
        """Get current user statistics.

        Returns:
            Current user stats or None if not found.
        """
        conn = self.db.connect()
        cursor = conn.execute("SELECT * FROM user_stats LIMIT 1")
        result = cursor.fetchone()

        if result:
            return self._row_to_model(_row_to_dict(result, cursor))
        return None

    def update_stats(self, updates: dict[str, Any]) -> UserStats | None:
        """Update user statistics.

        Args:
            updates: Fields to update.

        Returns:
            Updated user stats.
        """
        if not updates:
            return self.get_current_stats()

        conn = self.db.connect()

        # Build update query
        set_clauses = [f"{key} = ?" for key in updates]
        set_clause = ", ".join(set_clauses)
        values = list(updates.values())

        result = conn.execute(
            f"""
            UPDATE user_stats
            SET {set_clause}, updated_at = CURRENT_TIMESTAMP
        """,
            values,
        )

        # Check if update was successful (at least one row affected)
        if result.rowcount > 0:
            return self.get_current_stats()
        return None


class DailyActivityRepository(BaseRepository[DailyActivity]):
    """Repository for DailyActivity operations."""

    def _get_table_name(self) -> str:
        return "daily_activity"

    def _row_to_model(self, row: dict[str, Any]) -> DailyActivity:
        """Convert database row to DailyActivity model."""
        return DailyActivity(**row)

    def get_today_activity(self) -> DailyActivity | None:
        """Get today's activity record.

        Returns:
            Today's activity or None if not found.
        """
        conn = self.db.connect()
        today = date.today()
        cursor = conn.execute(
            "SELECT * FROM daily_activity WHERE activity_date = ?", [today]
        )
        result = cursor.fetchone()

        if result:
            return self._row_to_model(_row_to_dict(result, cursor))
        return None

    def get_recent_activity(self, days: int = 30) -> list[DailyActivity]:
        """Get recent activity records.

        Args:
            days: Number of days to retrieve.

        Returns:
            List of recent activity records.
        """
        conn = self.db.connect()
        cursor = conn.execute(
            """
            SELECT *
            FROM daily_activity
            WHERE activity_date >= (CURRENT_DATE - ? * INTERVAL '1 DAY')
            ORDER BY activity_date DESC
        """,
            [days],
        )
        results = cursor.fetchall()

        if not results:
            return []

        # Get column names from cursor description
        column_names = [desc[0] for desc in cursor.description]
        return [self._row_to_model(dict(zip(column_names, row))) for row in results]


class AchievementRepository(BaseRepository[Achievement]):
    """Repository for Achievement operations."""

    def _get_table_name(self) -> str:
        return "achievements"

    def _row_to_model(self, row: dict[str, Any]) -> Achievement:
        """Convert database row to Achievement model."""
        return Achievement(**row)

    def get_all_achievements(self) -> list[Achievement]:
        """Get all achievements.

        Returns:
            List of all achievements.
        """
        conn = self.db.connect()
        cursor = conn.execute(
            "SELECT * FROM achievements ORDER BY requirement_value, name"
        )
        results = cursor.fetchall()

        if not results:
            return []

        # Get column names from cursor description
        column_names = [desc[0] for desc in cursor.description]
        return [self._row_to_model(dict(zip(column_names, row))) for row in results]

    def get_unlocked_achievements(self) -> list[Achievement]:
        """Get unlocked achievements.

        Returns:
            List of unlocked achievements.
        """
        conn = self.db.connect()
        cursor = conn.execute("""
            SELECT * FROM achievements
            WHERE is_unlocked = TRUE
            ORDER BY unlocked_at DESC
        """)
        results = cursor.fetchall()

        if not results:
            return []

        # Get column names from cursor description
        column_names = [desc[0] for desc in cursor.description]
        return [self._row_to_model(dict(zip(column_names, row))) for row in results]

    def unlock_achievement(self, achievement_id: int) -> Achievement | None:
        """Unlock an achievement.

        Args:
            achievement_id: ID of achievement to unlock.

        Returns:
            Updated achievement if successful.
        """
        conn = self.db.connect()
        cursor = conn.execute(
            """
            UPDATE achievements
            SET is_unlocked = TRUE, unlocked_at = CURRENT_TIMESTAMP
            WHERE id = ? AND is_unlocked = FALSE
            RETURNING *
        """,
            [achievement_id],
        )
        result = cursor.fetchone()

        if result:
            return self._row_to_model(_row_to_dict(result, cursor))
        return None
