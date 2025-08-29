# Database Layer - Implementation Plan

## Overview
This document outlines the DuckDB database schema, operations, and data access layer for the todo application. DuckDB provides excellent performance for analytical queries while being lightweight and embedded.

## Database Schema

### Core Tables

#### categories
```sql
CREATE TABLE categories (
    id INTEGER PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    color VARCHAR(7),  -- Hex color code #RRGGBB
    icon VARCHAR(2),   -- Single emoji or character
    description VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Default categories
INSERT INTO categories (name, color, icon, description) VALUES
('Work', '#3B82F6', '💼', 'Work-related tasks and projects'),
('Personal', '#10B981', '👤', 'Personal tasks and activities'),
('Home', '#F59E0B', '🏠', 'Home maintenance and household tasks'),
('Health', '#EF4444', '❤️', 'Health and fitness activities'),
('Learning', '#8B5CF6', '📚', 'Learning and education'),
('Shopping', '#EC4899', '🛒', 'Shopping and errands'),
('Finance', '#059669', '💰', 'Financial tasks and planning');
```

#### recurrence_rules
```sql
CREATE TABLE recurrence_rules (
    id INTEGER PRIMARY KEY,
    pattern VARCHAR(20) NOT NULL CHECK (pattern IN ('daily', 'weekly', 'monthly', 'yearly', 'custom')),
    interval_value INTEGER NOT NULL DEFAULT 1 CHECK (interval_value > 0),
    weekdays TEXT,  -- JSON array: [0,1,2,3,4] for Mon-Fri
    day_of_month INTEGER CHECK (day_of_month BETWEEN 1 AND 31),
    end_date DATE,
    max_occurrences INTEGER CHECK (max_occurrences > 0),
    next_due_date DATE,
    created_from_ai BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### todos
```sql
CREATE TABLE todos (
    id INTEGER PRIMARY KEY,
    uuid VARCHAR(36) NOT NULL UNIQUE,  -- UUID for external references
    title VARCHAR(500) NOT NULL,
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'in_progress', 'completed', 'archived')),

    -- Size and priority (user override vs AI suggested)
    user_override_size VARCHAR(10) CHECK (user_override_size IN ('small', 'medium', 'large')),
    ai_suggested_size VARCHAR(10) CHECK (ai_suggested_size IN ('small', 'medium', 'large')),
    final_size VARCHAR(10) NOT NULL DEFAULT 'medium'
        CHECK (final_size IN ('small', 'medium', 'large')),

    user_override_priority VARCHAR(10) CHECK (user_override_priority IN ('low', 'medium', 'high', 'urgent')),
    ai_suggested_priority VARCHAR(10) CHECK (ai_suggested_priority IN ('low', 'medium', 'high', 'urgent')),
    final_priority VARCHAR(10) NOT NULL DEFAULT 'medium'
        CHECK (final_priority IN ('low', 'medium', 'high', 'urgent')),

    -- Foreign keys
    category_id INTEGER REFERENCES categories(id),
    recurrence_rule_id INTEGER REFERENCES recurrence_rules(id),
    parent_todo_id INTEGER REFERENCES todos(id),  -- For recurring instances

    -- Time tracking
    estimated_minutes INTEGER CHECK (estimated_minutes > 0),
    actual_minutes INTEGER CHECK (actual_minutes > 0),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    due_date DATE,

    -- Gamification
    base_points INTEGER NOT NULL DEFAULT 0 CHECK (base_points >= 0),
    bonus_points INTEGER NOT NULL DEFAULT 0 CHECK (bonus_points >= 0),
    total_points_earned INTEGER NOT NULL DEFAULT 0 CHECK (total_points_earned >= 0),

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Ensure completed tasks have completion timestamp
    CHECK (status != 'completed' OR completed_at IS NOT NULL)
);

-- Indexes for common queries
CREATE INDEX idx_todos_status ON todos(status);
CREATE INDEX idx_todos_category ON todos(category_id);
CREATE INDEX idx_todos_due_date ON todos(due_date);
CREATE INDEX idx_todos_created_at ON todos(created_at);
CREATE INDEX idx_todos_status_due ON todos(status, due_date);
```

### AI and Learning Tables

#### ai_enrichments
```sql
CREATE TABLE ai_enrichments (
    id INTEGER PRIMARY KEY,
    todo_id INTEGER NOT NULL REFERENCES todos(id) ON DELETE CASCADE,
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

CREATE INDEX idx_ai_enrichments_todo ON ai_enrichments(todo_id);
CREATE INDEX idx_ai_enrichments_provider ON ai_enrichments(provider);
```

#### ai_learning_feedback
```sql
CREATE TABLE ai_learning_feedback (
    id INTEGER PRIMARY KEY,
    original_task_text VARCHAR(500) NOT NULL,
    ai_provider VARCHAR(20) NOT NULL CHECK (ai_provider IN ('openai', 'anthropic')),

    -- Original AI suggestions
    ai_suggested_category VARCHAR(50),
    ai_suggested_size VARCHAR(10) CHECK (ai_suggested_size IN ('small', 'medium', 'large')),
    ai_suggested_priority VARCHAR(10) CHECK (ai_suggested_priority IN ('low', 'medium', 'high', 'urgent')),

    -- User corrections
    user_corrected_category VARCHAR(50),
    user_corrected_size VARCHAR(10) CHECK (user_corrected_size IN ('small', 'medium', 'large')),
    user_corrected_priority VARCHAR(10) CHECK (user_corrected_priority IN ('low', 'medium', 'high', 'urgent')),

    -- Learning context
    task_keywords TEXT,  -- JSON array
    correction_type VARCHAR(50) NOT NULL,  -- 'size_increase', 'size_decrease', 'category_change', etc.

    feedback_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_learning_feedback_provider ON ai_learning_feedback(ai_provider);
CREATE INDEX idx_learning_feedback_correction_type ON ai_learning_feedback(correction_type);
```

### Gamification Tables

#### user_stats
```sql
CREATE TABLE user_stats (
    id INTEGER PRIMARY KEY,

    -- Point tracking
    total_points INTEGER NOT NULL DEFAULT 0 CHECK (total_points >= 0),
    level INTEGER NOT NULL DEFAULT 1 CHECK (level >= 1),
    points_to_next_level INTEGER NOT NULL DEFAULT 100 CHECK (points_to_next_level >= 0),

    -- Task completion
    total_tasks_completed INTEGER NOT NULL DEFAULT 0 CHECK (total_tasks_completed >= 0),
    total_tasks_created INTEGER NOT NULL DEFAULT 0 CHECK (total_tasks_created >= 0),

    -- Streak tracking
    current_streak_days INTEGER NOT NULL DEFAULT 0 CHECK (current_streak_days >= 0),
    longest_streak_days INTEGER NOT NULL DEFAULT 0 CHECK (longest_streak_days >= 0),
    last_completion_date DATE,

    -- Goals
    daily_goal INTEGER NOT NULL DEFAULT 3 CHECK (daily_goal >= 1),
    weekly_goal INTEGER NOT NULL DEFAULT 20 CHECK (weekly_goal >= 1),
    monthly_goal INTEGER NOT NULL DEFAULT 80 CHECK (monthly_goal >= 1),

    -- Achievements
    achievements_unlocked INTEGER NOT NULL DEFAULT 0 CHECK (achievements_unlocked >= 0),

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Single row table - only one user
INSERT INTO user_stats DEFAULT VALUES;
```

#### daily_activity
```sql
CREATE TABLE daily_activity (
    id INTEGER PRIMARY KEY,
    activity_date DATE NOT NULL UNIQUE,

    -- Task completion
    tasks_completed INTEGER NOT NULL DEFAULT 0 CHECK (tasks_completed >= 0),
    tasks_created INTEGER NOT NULL DEFAULT 0 CHECK (tasks_created >= 0),

    -- Points breakdown
    base_points_earned INTEGER NOT NULL DEFAULT 0 CHECK (base_points_earned >= 0),
    streak_bonus_earned INTEGER NOT NULL DEFAULT 0 CHECK (streak_bonus_earned >= 0),
    daily_goal_bonus_earned INTEGER NOT NULL DEFAULT 0 CHECK (daily_goal_bonus_earned >= 0),
    total_points_earned INTEGER NOT NULL DEFAULT 0 CHECK (total_points_earned >= 0),

    -- Goal achievement
    daily_goal_met BOOLEAN DEFAULT FALSE,
    streak_active BOOLEAN DEFAULT FALSE,

    -- Penalties
    overdue_penalty_applied INTEGER NOT NULL DEFAULT 0 CHECK (overdue_penalty_applied >= 0),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_daily_activity_date ON daily_activity(activity_date);
```

#### achievements
```sql
CREATE TABLE achievements (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description VARCHAR(500) NOT NULL,
    icon VARCHAR(2),  -- Emoji

    -- Requirements
    requirement_type VARCHAR(50) NOT NULL,  -- 'tasks_completed', 'streak_days', 'points_earned'
    requirement_value INTEGER NOT NULL CHECK (requirement_value >= 1),
    bonus_points INTEGER NOT NULL DEFAULT 0 CHECK (bonus_points >= 0),

    -- User progress
    is_unlocked BOOLEAN DEFAULT FALSE,
    progress_current INTEGER NOT NULL DEFAULT 0 CHECK (progress_current >= 0),
    unlocked_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Default achievements
INSERT INTO achievements (name, description, icon, requirement_type, requirement_value, bonus_points) VALUES
('First Steps', 'Complete your first task', '🎯', 'tasks_completed', 1, 10),
('Getting Started', 'Complete 10 tasks', '🚀', 'tasks_completed', 10, 25),
('Productive', 'Complete 50 tasks', '⚡', 'tasks_completed', 50, 50),
('Century Club', 'Complete 100 tasks', '💯', 'tasks_completed', 100, 100),
('Task Master', 'Complete 500 tasks', '👑', 'tasks_completed', 500, 250),
('Day One', 'Maintain a 1-day streak', '📅', 'streak_days', 1, 5),
('Week Warrior', 'Maintain a 7-day streak', '🔥', 'streak_days', 7, 35),
('Month Champion', 'Maintain a 30-day streak', '🏆', 'streak_days', 30, 150),
('Point Collector', 'Earn 1000 points', '💎', 'points_earned', 1000, 100),
('Point Master', 'Earn 5000 points', '💍', 'points_earned', 5000, 500);
```

## Database Operations Layer

### Connection Management
```python
# src/todo/db/connection.py
import duckdb
from pathlib import Path
from typing import Optional
from todo.core.config import get_app_config

class DatabaseConnection:
    """Manages DuckDB connection and initialization."""

    def __init__(self, db_path: Optional[str] = None):
        config = get_app_config()
        self.db_path = Path(db_path or config.database_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: Optional[duckdb.DuckDBPyConnection] = None

    def connect(self) -> duckdb.DuckDBPyConnection:
        """Get or create database connection."""
        if self._connection is None:
            self._connection = duckdb.connect(str(self.db_path))
            self._initialize_database()
        return self._connection

    def close(self) -> None:
        """Close database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None

    def _initialize_database(self) -> None:
        """Initialize database schema if needed."""
        conn = self._connection
        # Execute schema creation scripts
        # (Implementation details in next section)
```

### Repository Pattern Implementation

#### Base Repository
```python
# src/todo/db/base.py
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, List, Optional, Any, Dict
from pydantic import BaseModel
from todo.db.connection import DatabaseConnection

T = TypeVar('T', bound=BaseModel)

class BaseRepository(Generic[T], ABC):
    """Base repository with common CRUD operations."""

    def __init__(self, db_connection: DatabaseConnection):
        self.db = db_connection
        self.table_name = self._get_table_name()

    @abstractmethod
    def _get_table_name(self) -> str:
        """Return the table name for this repository."""
        pass

    @abstractmethod
    def _row_to_model(self, row: Dict[str, Any]) -> T:
        """Convert database row to Pydantic model."""
        pass

    def create(self, model: T) -> T:
        """Create a new record."""
        # Implementation with INSERT query
        pass

    def get_by_id(self, id: int) -> Optional[T]:
        """Get record by ID."""
        pass

    def update(self, id: int, updates: Dict[str, Any]) -> Optional[T]:
        """Update record by ID."""
        pass

    def delete(self, id: int) -> bool:
        """Delete record by ID."""
        pass

    def list_all(self, limit: Optional[int] = None, offset: int = 0) -> List[T]:
        """List all records with pagination."""
        pass
```

#### Todo Repository
```python
# src/todo/db/repositories/todo.py
from typing import List, Optional, Dict, Any
from datetime import date, datetime
from todo.models.todo import Todo, TodoStatus, TaskSize, Priority
from todo.db.base import BaseRepository

class TodoRepository(BaseRepository[Todo]):
    """Repository for Todo operations."""

    def _get_table_name(self) -> str:
        return "todos"

    def _row_to_model(self, row: Dict[str, Any]) -> Todo:
        """Convert database row to Todo model."""
        # Handle enum conversions and nested objects
        return Todo(**row)

    def create_todo(self, title: str, description: Optional[str] = None) -> Todo:
        """Create a new todo with minimal input."""
        conn = self.db.connect()

        query = """
        INSERT INTO todos (uuid, title, description, final_size, final_priority)
        VALUES (?, ?, ?, 'medium', 'medium')
        RETURNING *
        """

        result = conn.execute(query, [
            str(uuid4()), title, description
        ]).fetchone()

        return self._row_to_model(dict(result))

    def get_active_todos(self, limit: Optional[int] = None) -> List[Todo]:
        """Get todos that are not completed or archived."""
        conn = self.db.connect()

        query = """
        SELECT t.*, c.name as category_name, c.color as category_color
        FROM todos t
        LEFT JOIN categories c ON t.category_id = c.id
        WHERE t.status IN ('pending', 'in_progress')
        ORDER BY
            CASE t.final_priority
                WHEN 'urgent' THEN 1
                WHEN 'high' THEN 2
                WHEN 'medium' THEN 3
                ELSE 4
            END,
            t.due_date ASC NULLS LAST,
            t.created_at DESC
        """

        if limit:
            query += f" LIMIT {limit}"

        results = conn.execute(query).fetchall()
        return [self._row_to_model(dict(row)) for row in results]

    def get_overdue_todos(self) -> List[Todo]:
        """Get todos that are overdue."""
        conn = self.db.connect()

        query = """
        SELECT t.*, c.name as category_name, c.color as category_color
        FROM todos t
        LEFT JOIN categories c ON t.category_id = c.id
        WHERE t.due_date < CURRENT_DATE
        AND t.status NOT IN ('completed', 'archived')
        ORDER BY t.due_date ASC
        """

        results = conn.execute(query).fetchall()
        return [self._row_to_model(dict(row)) for row in results]

    def complete_todo(self, todo_id: int) -> Optional[Todo]:
        """Mark todo as completed and calculate points."""
        conn = self.db.connect()

        # Start transaction
        conn.begin()
        try:
            # Get current todo
            todo = self.get_by_id(todo_id)
            if not todo or todo.status == TodoStatus.COMPLETED:
                conn.rollback()
                return None

            # Calculate points (implementation depends on gamification logic)
            base_points = self._calculate_base_points(todo.final_size)
            bonus_points = self._calculate_bonus_points(todo)
            total_points = base_points + bonus_points

            # Update todo
            update_query = """
            UPDATE todos
            SET status = 'completed',
                completed_at = CURRENT_TIMESTAMP,
                base_points = ?,
                bonus_points = ?,
                total_points_earned = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            RETURNING *
            """

            result = conn.execute(update_query, [
                base_points, bonus_points, total_points, todo_id
            ]).fetchone()

            # Update user stats and daily activity
            self._update_completion_stats(conn, total_points)

            conn.commit()
            return self._row_to_model(dict(result))

        except Exception as e:
            conn.rollback()
            raise e

    def _calculate_base_points(self, size: TaskSize) -> int:
        """Calculate base points for task size."""
        points_map = {
            TaskSize.SMALL: 1,
            TaskSize.MEDIUM: 3,
            TaskSize.LARGE: 5
        }
        return points_map.get(size, 3)

    def _calculate_bonus_points(self, todo: Todo) -> int:
        """Calculate bonus points based on streaks, goals, etc."""
        # Implementation depends on current user stats
        return 0  # Placeholder

    def _update_completion_stats(self, conn, points_earned: int) -> None:
        """Update user stats and daily activity after completion."""
        # Update daily activity
        today = date.today()

        # Upsert daily activity
        conn.execute("""
        INSERT INTO daily_activity (activity_date, tasks_completed, total_points_earned)
        VALUES (?, 1, ?)
        ON CONFLICT(activity_date)
        DO UPDATE SET
            tasks_completed = daily_activity.tasks_completed + 1,
            total_points_earned = daily_activity.total_points_earned + ?,
            updated_at = CURRENT_TIMESTAMP
        """, [today, points_earned, points_earned])

        # Update user stats
        conn.execute("""
        UPDATE user_stats
        SET total_tasks_completed = total_tasks_completed + 1,
            total_points = total_points + ?,
            last_completion_date = ?,
            updated_at = CURRENT_TIMESTAMP
        """, [points_earned, today])
```

### Query Optimization

#### Common Query Patterns
```python
# src/todo/db/queries.py
"""Optimized queries for common operations."""

DASHBOARD_QUERY = """
WITH overdue_count AS (
    SELECT COUNT(*) as count
    FROM todos
    WHERE due_date < CURRENT_DATE
    AND status NOT IN ('completed', 'archived')
),
today_stats AS (
    SELECT
        COALESCE(tasks_completed, 0) as tasks_today,
        COALESCE(total_points_earned, 0) as points_today
    FROM daily_activity
    WHERE activity_date = CURRENT_DATE
),
user_info AS (
    SELECT current_streak_days, total_points, level
    FROM user_stats
    LIMIT 1
)
SELECT
    (SELECT count FROM overdue_count) as overdue_count,
    (SELECT tasks_today FROM today_stats) as tasks_completed_today,
    (SELECT points_today FROM today_stats) as points_earned_today,
    (SELECT current_streak_days FROM user_info) as current_streak,
    (SELECT total_points FROM user_info) as total_points,
    (SELECT level FROM user_info) as current_level
"""

RECENT_ACTIVITY_QUERY = """
SELECT
    activity_date,
    tasks_completed,
    total_points_earned,
    daily_goal_met,
    streak_active
FROM daily_activity
WHERE activity_date >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY activity_date DESC
LIMIT 30
"""
```

## Migration System

### Schema Versioning
```python
# src/todo/db/migrations.py
from typing import List, Dict, Any
from pathlib import Path

class Migration:
    """Represents a database migration."""

    def __init__(self, version: int, name: str, up_sql: str, down_sql: str = ""):
        self.version = version
        self.name = name
        self.up_sql = up_sql
        self.down_sql = down_sql

class MigrationManager:
    """Manages database schema migrations."""

    def __init__(self, db_connection):
        self.db = db_connection
        self._ensure_migration_table()

    def _ensure_migration_table(self) -> None:
        """Create migration tracking table."""
        conn = self.db.connect()
        conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

    def get_current_version(self) -> int:
        """Get current schema version."""
        conn = self.db.connect()
        result = conn.execute(
            "SELECT MAX(version) FROM schema_migrations"
        ).fetchone()
        return result[0] if result[0] is not None else 0

    def run_migrations(self) -> None:
        """Run all pending migrations."""
        current_version = self.get_current_version()
        migrations = self._get_pending_migrations(current_version)

        for migration in migrations:
            self._apply_migration(migration)

    def _get_pending_migrations(self, current_version: int) -> List[Migration]:
        """Get list of migrations to apply."""
        # Load migration definitions
        return [
            Migration(1, "initial_schema", self._get_initial_schema()),
            Migration(2, "add_gamification", self._get_gamification_schema()),
            # Add more migrations as needed
        ]

    def _apply_migration(self, migration: Migration) -> None:
        """Apply a single migration."""
        conn = self.db.connect()
        conn.begin()

        try:
            # Execute migration SQL
            conn.execute(migration.up_sql)

            # Record migration
            conn.execute("""
            INSERT INTO schema_migrations (version, name)
            VALUES (?, ?)
            """, [migration.version, migration.name])

            conn.commit()
            print(f"Applied migration {migration.version}: {migration.name}")

        except Exception as e:
            conn.rollback()
            raise Exception(f"Migration {migration.version} failed: {e}")
```

## Implementation Steps

### Step 1: Database Connection Setup
1. Create `src/todo/db/__init__.py`
2. Implement `DatabaseConnection` class
3. Add configuration integration
4. Test basic connection functionality

### Step 2: Schema Creation
1. Create migration system
2. Define initial schema migration
3. Implement schema validation
4. Test schema creation and constraints

### Step 3: Repository Implementation
1. Create base repository pattern
2. Implement TodoRepository with core operations
3. Add CategoryRepository for categories
4. Implement AI and gamification repositories

### Step 4: Query Optimization
1. Create indexes for common queries
2. Implement complex analytical queries
3. Add query performance monitoring
4. Test with realistic data volumes

### Step 5: Transaction Management
1. Implement proper transaction handling
2. Add rollback mechanisms for failures
3. Test concurrent access patterns
4. Implement connection pooling if needed

## Success Criteria
- [ ] All tables created with proper constraints
- [ ] Repository pattern implemented for all models
- [ ] Migration system working correctly
- [ ] Complex queries optimized and tested
- [ ] Transaction handling robust
- [ ] Full test coverage for database operations
- [ ] Performance acceptable for expected data volumes
- [ ] No data integrity issues under normal operations
