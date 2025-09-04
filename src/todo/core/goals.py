"""Goal tracking and management service.

This module provides the GoalService for managing weekly and monthly goals,
tracking progress, and providing goal suggestions based on user behavior patterns.
"""

import contextlib
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any

from ..db.connection import DatabaseConnection
from ..db.repository import UserStatsRepository
from ..models import UserStats


class GoalType(str, Enum):
    """Types of goals that can be set."""

    WEEKLY = "weekly"
    MONTHLY = "monthly"


class GoalCategory(str, Enum):
    """Categories of goals."""

    TASKS_COMPLETED = "tasks_completed"
    POINTS_EARNED = "points_earned"
    STREAK_DAYS = "streak_days"
    PRODUCTIVITY_SCORE = "productivity_score"
    CATEGORY_FOCUS = "category_focus"  # Focus on specific category


class Goal:
    """Represents a user goal."""

    def __init__(
        self,
        goal_id: int,
        goal_type: GoalType,
        category: GoalCategory,
        target_value: int,
        current_value: int = 0,
        period_start: date = None,
        period_end: date = None,
        is_active: bool = True,
        created_at: datetime = None,
    ):
        self.id = goal_id
        self.type = goal_type
        self.category = category
        self.target_value = target_value
        self.current_value = current_value
        self.period_start = period_start or self._calculate_period_start()
        self.period_end = period_end or self._calculate_period_end()
        self.is_active = is_active
        self.created_at = created_at or datetime.now()

    def _calculate_period_start(self) -> date:
        """Calculate the start of the current period."""
        today = date.today()
        if self.type == GoalType.WEEKLY:
            # Start of current week (Monday)
            return today - timedelta(days=today.weekday())
        else:  # MONTHLY
            # Start of current month
            return today.replace(day=1)

    def _calculate_period_end(self) -> date:
        """Calculate the end of the current period."""
        start = self.period_start
        if self.type == GoalType.WEEKLY:
            return start + timedelta(days=6)  # Sunday
        else:  # MONTHLY
            # Last day of the month
            if start.month == 12:
                next_month = start.replace(year=start.year + 1, month=1)
            else:
                next_month = start.replace(month=start.month + 1)
            return next_month - timedelta(days=1)

    @property
    def progress_percentage(self) -> float:
        """Calculate progress percentage (0-100)."""
        if self.target_value == 0:
            return 0.0
        return min(100.0, (self.current_value / self.target_value) * 100)

    @property
    def is_completed(self) -> bool:
        """Check if the goal is completed."""
        return self.current_value >= self.target_value

    @property
    def is_current_period(self) -> bool:
        """Check if this goal is for the current period."""
        today = date.today()
        return self.period_start <= today <= self.period_end

    @property
    def days_remaining(self) -> int:
        """Get the number of days remaining in the period."""
        today = date.today()
        if today > self.period_end:
            return 0
        return (self.period_end - today).days + 1


class GoalService:
    """Service for managing user goals and suggestions."""

    def __init__(self, db: DatabaseConnection):
        self.db = db
        self.user_stats_repo = UserStatsRepository(db)
        self._ensure_goals_table()

    def _ensure_goals_table(self):
        """Ensure the goals table exists."""
        conn = self.db.connect()

        # Create sequence for ID
        with contextlib.suppress(Exception):
            conn.execute("CREATE SEQUENCE IF NOT EXISTS goals_id_seq")

        # Create table
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY DEFAULT nextval('goals_id_seq'),
            goal_type TEXT NOT NULL,
            category TEXT NOT NULL,
            target_value INTEGER NOT NULL,
            current_value INTEGER DEFAULT 0,
            period_start DATE NOT NULL,
            period_end DATE NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        conn.execute(create_table_sql)

    def create_goal(
        self, goal_type: GoalType, category: GoalCategory, target_value: int
    ) -> Goal:
        """Create a new goal."""
        # First, deactivate any existing goals of the same type and category
        self._deactivate_existing_goals(goal_type, category)

        goal = Goal(0, goal_type, category, target_value)

        insert_sql = """
        INSERT INTO goals (goal_type, category, target_value, current_value,
                          period_start, period_end, is_active, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        RETURNING id
        """

        conn = self.db.connect()
        cursor = conn.execute(
            insert_sql,
            (
                goal.type.value,
                goal.category.value,
                goal.target_value,
                goal.current_value,
                goal.period_start,
                goal.period_end,
                goal.is_active,
                goal.created_at,
            ),
        )

        result = cursor.fetchone()
        goal.id = result[0] if result else None
        return goal

    def _deactivate_existing_goals(self, goal_type: GoalType, category: GoalCategory):
        """Deactivate existing goals of the same type and category."""
        update_sql = """
        UPDATE goals
        SET is_active = FALSE
        WHERE goal_type = ? AND category = ? AND is_active = TRUE
        """
        conn = self.db.connect()
        conn.execute(update_sql, (goal_type.value, category.value))

    def get_active_goals(self) -> list[Goal]:
        """Get all active goals."""
        select_sql = """
        SELECT id, goal_type, category, target_value, current_value,
               period_start, period_end, is_active, created_at
        FROM goals
        WHERE is_active = TRUE
        ORDER BY created_at DESC
        """

        conn = self.db.connect()
        cursor = conn.execute(select_sql)
        results = cursor.fetchall()
        goals = []

        for row in results:
            # Handle date conversion - DuckDB may return date objects or strings
            period_start = (
                row[5]
                if isinstance(row[5], date)
                else datetime.strptime(row[5], "%Y-%m-%d").date()
            )
            period_end = (
                row[6]
                if isinstance(row[6], date)
                else datetime.strptime(row[6], "%Y-%m-%d").date()
            )
            created_at = (
                row[8]
                if isinstance(row[8], datetime)
                else datetime.fromisoformat(row[8])
            )

            goal = Goal(
                goal_id=row[0],
                goal_type=GoalType(row[1]),
                category=GoalCategory(row[2]),
                target_value=row[3],
                current_value=row[4],
                period_start=period_start,
                period_end=period_end,
                is_active=bool(row[7]),
                created_at=created_at,
            )
            goals.append(goal)

        return goals

    def get_current_goals(self) -> list[Goal]:
        """Get goals for the current period."""
        return [goal for goal in self.get_active_goals() if goal.is_current_period]

    def update_goal_progress(self, user_stats: UserStats):
        """Update progress for all active goals based on current user stats."""
        current_goals = self.get_current_goals()

        for goal in current_goals:
            new_value = self._calculate_goal_progress(goal, user_stats)
            if new_value != goal.current_value:
                self._update_goal_current_value(goal.id, new_value)
                goal.current_value = new_value

    def _calculate_goal_progress(self, goal: Goal, user_stats: UserStats) -> int:
        """Calculate current progress for a goal based on user stats."""
        if goal.category == GoalCategory.TASKS_COMPLETED:
            # For weekly/monthly goals, we need period-specific completion count
            return self._get_period_task_completions(goal)
        elif goal.category == GoalCategory.POINTS_EARNED:
            # For weekly/monthly goals, we need period-specific points
            return self._get_period_points_earned(goal)
        elif goal.category == GoalCategory.STREAK_DAYS:
            return user_stats.current_streak_days or 0
        elif goal.category == GoalCategory.PRODUCTIVITY_SCORE:
            # Calculate a productivity score based on multiple factors
            return self._calculate_productivity_score(user_stats)

        return 0

    def _get_period_task_completions(self, goal: Goal) -> int:
        """Get task completions for the goal's period."""
        count_sql = """
        SELECT COUNT(*) FROM todos
        WHERE status = 'completed'
        AND completed_at >= ? AND completed_at <= ?
        """

        # Convert dates to datetime strings for comparison
        start_datetime = datetime.combine(goal.period_start, datetime.min.time())
        end_datetime = datetime.combine(goal.period_end, datetime.max.time())

        conn = self.db.connect()
        cursor = conn.execute(count_sql, (start_datetime, end_datetime))
        result = cursor.fetchone()
        return result[0] if result else 0

    def _get_period_points_earned(self, goal: Goal) -> int:
        """Get points earned for the goal's period."""
        # This is an approximation - in a real system you'd track points per completion
        completions = self._get_period_task_completions(goal)
        return completions * 10  # Assume 10 points per task (simplified)

    def _calculate_productivity_score(self, user_stats: UserStats) -> int:
        """Calculate a productivity score (0-100) based on multiple factors."""
        score = 0

        # Task completion factor (40% of score)
        if user_stats.total_tasks_completed:
            score += min(40, user_stats.total_tasks_completed * 2)

        # Streak factor (30% of score)
        if user_stats.current_streak_days:
            score += min(30, user_stats.current_streak_days * 3)

        # Level factor (30% of score)
        if user_stats.level:
            score += min(30, user_stats.level * 5)

        return min(100, score)

    def _update_goal_current_value(self, goal_id: int, new_value: int):
        """Update the current value of a goal."""
        update_sql = "UPDATE goals SET current_value = ? WHERE id = ?"
        conn = self.db.connect()
        conn.execute(update_sql, (new_value, goal_id))

    def get_goal_suggestions(self, user_stats: UserStats) -> list[dict[str, Any]]:
        """Generate goal suggestions based on user behavior patterns."""
        suggestions = []

        # Analyze user's historical performance
        avg_weekly_completions = self._get_average_weekly_completions()
        avg_monthly_completions = self._get_average_monthly_completions()
        current_streak = user_stats.current_streak_days or 0

        # Suggest weekly task completion goals
        if avg_weekly_completions > 0:
            # Suggest 10-20% increase from average
            suggested_weekly = int(avg_weekly_completions * 1.15)
            suggestions.append(
                {
                    "type": GoalType.WEEKLY,
                    "category": GoalCategory.TASKS_COMPLETED,
                    "target_value": max(suggested_weekly, avg_weekly_completions + 1),
                    "reason": f"Based on your average of {avg_weekly_completions} tasks per week",
                    "difficulty": "moderate",
                }
            )

        # Suggest monthly task completion goals
        if avg_monthly_completions > 0:
            suggested_monthly = int(avg_monthly_completions * 1.2)
            suggestions.append(
                {
                    "type": GoalType.MONTHLY,
                    "category": GoalCategory.TASKS_COMPLETED,
                    "target_value": max(suggested_monthly, avg_monthly_completions + 5),
                    "reason": f"Based on your average of {avg_monthly_completions} tasks per month",
                    "difficulty": "moderate",
                }
            )

        # Suggest streak goals
        if current_streak > 0:
            streak_target = max(current_streak + 3, 7)  # At least 7 days
            suggestions.append(
                {
                    "type": GoalType.WEEKLY,
                    "category": GoalCategory.STREAK_DAYS,
                    "target_value": min(streak_target, 7),  # Weekly max is 7
                    "reason": f"Extend your current {current_streak}-day streak",
                    "difficulty": "achievable",
                }
            )

        # Suggest points goals
        avg_points_weekly = (
            avg_weekly_completions * 10 if avg_weekly_completions > 0 else 50
        )
        suggestions.append(
            {
                "type": GoalType.WEEKLY,
                "category": GoalCategory.POINTS_EARNED,
                "target_value": int(avg_points_weekly * 1.1),
                "reason": "Steady points accumulation",
                "difficulty": "easy",
            }
        )

        # Filter out suggestions for goals that already exist
        existing_goals = self.get_current_goals()
        existing_combinations = {(g.type, g.category) for g in existing_goals}

        filtered_suggestions = [
            s
            for s in suggestions
            if (s["type"], s["category"]) not in existing_combinations
        ]

        return filtered_suggestions[:3]  # Return top 3 suggestions

    def _get_average_weekly_completions(self) -> int:
        """Get average weekly task completions over the last 4 weeks."""
        four_weeks_ago = date.today() - timedelta(weeks=4)

        count_sql = """
        SELECT COUNT(*) FROM todos
        WHERE status = 'completed'
        AND completed_at >= ?
        """

        conn = self.db.connect()
        cursor = conn.execute(count_sql, (four_weeks_ago,))
        result = cursor.fetchone()
        total_completions = result[0] if result else 0

        return total_completions // 4  # Average per week

    def _get_average_monthly_completions(self) -> int:
        """Get average monthly task completions over the last 3 months."""
        three_months_ago = date.today() - timedelta(days=90)

        count_sql = """
        SELECT COUNT(*) FROM todos
        WHERE status = 'completed'
        AND completed_at >= ?
        """

        conn = self.db.connect()
        cursor = conn.execute(count_sql, (three_months_ago,))
        result = cursor.fetchone()
        total_completions = result[0] if result else 0

        return total_completions // 3  # Average per month

    def get_goals_summary(self) -> dict[str, Any]:
        """Get a summary of all current goals and their progress."""
        current_goals = self.get_current_goals()

        if not current_goals:
            return {
                "total_goals": 0,
                "completed_goals": 0,
                "in_progress_goals": 0,
                "completion_rate": 0.0,
                "goals": [],
            }

        completed = sum(1 for g in current_goals if g.is_completed)
        in_progress = len(current_goals) - completed

        goals_data = []
        for goal in current_goals:
            goals_data.append(
                {
                    "type": goal.type.value,
                    "category": goal.category.value,
                    "target": goal.target_value,
                    "current": goal.current_value,
                    "progress": goal.progress_percentage,
                    "completed": goal.is_completed,
                    "days_remaining": goal.days_remaining,
                    "period_start": goal.period_start.isoformat(),
                    "period_end": goal.period_end.isoformat(),
                }
            )

        return {
            "total_goals": len(current_goals),
            "completed_goals": completed,
            "in_progress_goals": in_progress,
            "completion_rate": (completed / len(current_goals)) * 100
            if current_goals
            else 0,
            "average_progress": sum(g.progress_percentage for g in current_goals)
            / len(current_goals),
            "goals": goals_data,
        }

    def cleanup_expired_goals(self):
        """Mark expired goals as inactive."""
        today = date.today()

        update_sql = """
        UPDATE goals
        SET is_active = FALSE
        WHERE period_end < ? AND is_active = TRUE
        """

        conn = self.db.connect()
        conn.execute(update_sql, (today,))

    def delete_goal(self, goal_id: int) -> bool:
        """Delete a goal by ID."""
        delete_sql = "DELETE FROM goals WHERE id = ?"
        conn = self.db.connect()
        result = conn.execute(delete_sql, (goal_id,))
        return result.rowcount > 0 if hasattr(result, "rowcount") else True
