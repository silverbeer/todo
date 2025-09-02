"""Gamification scoring system for todo completion and user engagement."""

from datetime import date, timedelta
from typing import Any

from ..db.connection import DatabaseConnection
from ..db.repository import DailyActivityRepository, TodoRepository, UserStatsRepository
from ..models import TaskSize, Todo, UserStats


class ScoringService:
    """Core service for calculating points, bonuses, and managing gamification."""

    def __init__(self, db_connection: DatabaseConnection):
        """Initialize scoring service with database connection."""
        self.db = db_connection
        self.todo_repo = TodoRepository(db_connection)
        self.user_stats_repo = UserStatsRepository(db_connection)
        self.daily_activity_repo = DailyActivityRepository(db_connection)

        # Base point values by task size
        self.base_points = {
            TaskSize.SMALL: 1,
            TaskSize.MEDIUM: 3,
            TaskSize.LARGE: 5,
        }

        # Streak bonus multipliers
        self.streak_multipliers = {
            3: 1.1,  # 10% bonus for 3-day streak
            7: 1.25,  # 25% bonus for 7-day streak
            14: 1.4,  # 40% bonus for 14-day streak
            30: 1.6,  # 60% bonus for 30-day streak
            60: 1.8,  # 80% bonus for 60-day streak
            100: 2.0,  # 100% bonus for 100-day streak
        }

        # Daily goal bonus rate
        self.daily_goal_bonus_rate = 0.5  # 50% bonus for hitting daily goal

        # Level thresholds (points needed for each level)
        self.level_thresholds = [
            0,
            100,
            250,
            500,
            1000,
            1750,
            2750,
            4000,
            5500,
            7500,
            10000,
            13000,
            16500,
            20500,
            25000,
            30000,
            35500,
            41500,
            48000,
            55000,
            62500,
            70500,
            79000,
            88000,
            97500,
            107500,
            118000,
            129000,
            140500,
            152500,
            165000,  # Up to level 31
        ]

    def calculate_completion_points(self, todo: Todo) -> tuple[int, int, int]:
        """
        Calculate points for completing a todo.

        Args:
            todo: The todo being completed.

        Returns:
            Tuple of (base_points, bonus_points, total_points)
        """
        # Get base points from task size
        base_points = self.base_points.get(
            todo.final_size, self.base_points[TaskSize.MEDIUM]
        )
        bonus_points = 0

        # Get current user stats for streak calculations
        current_stats = self.user_stats_repo.get_current_stats()
        if not current_stats:
            # Initialize stats if they don't exist
            current_stats = self._initialize_user_stats()

        # Calculate streak bonus
        streak_multiplier = self._get_streak_multiplier(
            current_stats.current_streak_days
        )
        if streak_multiplier > 1.0:
            streak_bonus = int(base_points * (streak_multiplier - 1.0))
            bonus_points += streak_bonus

        # Calculate daily goal bonus
        today_activity = self.daily_activity_repo.get_today_activity()
        daily_goal = current_stats.daily_goal

        # Check if this completion will hit the daily goal
        tasks_completed_today = today_activity.tasks_completed if today_activity else 0
        tasks_after_completion = tasks_completed_today + 1

        if tasks_after_completion >= daily_goal and (
            not today_activity or not today_activity.daily_goal_met
        ):
            # First time hitting goal today - apply bonus
            daily_bonus = int(base_points * self.daily_goal_bonus_rate)
            bonus_points += daily_bonus

        # Category bonus for "less fun" categories
        if (
            hasattr(todo, "category")
            and todo.category
            and hasattr(todo.category, "name")
            and todo.category.name
            in [
                "Work",
                "Finance",
                "Health",
            ]
        ):
            category_bonus = 1  # Extra point for important but less fun categories
            bonus_points += category_bonus

        # Overdue task completion bonus
        if todo.due_date and todo.due_date < date.today():
            recovery_bonus = 1  # Small bonus for completing overdue tasks
            bonus_points += recovery_bonus

        total_points = base_points + bonus_points
        return base_points, bonus_points, total_points

    def apply_completion_scoring(
        self, todo: Todo, completion_date: date = None
    ) -> dict[str, Any]:
        """
        Apply full scoring logic when a todo is completed.

        Args:
            todo: The completed todo.
            completion_date: Date of completion (defaults to today).

        Returns:
            Dictionary with scoring results.
        """
        if completion_date is None:
            completion_date = date.today()

        # Calculate points for this completion
        base_points, bonus_points, total_points = self.calculate_completion_points(todo)

        # Update streak
        new_streak = self.update_streak(completion_date)

        # Update user stats
        current_stats = self.user_stats_repo.get_current_stats()
        if not current_stats:
            current_stats = self._initialize_user_stats()

        new_total_points = current_stats.total_points + total_points
        new_total_completed = current_stats.total_tasks_completed + 1

        # Calculate new level
        current_level, points_to_next, points_for_current = self.calculate_level(
            new_total_points
        )
        level_up = current_level > current_stats.level

        # Update user stats
        self.user_stats_repo.update_stats(
            {
                "total_points": new_total_points,
                "total_tasks_completed": new_total_completed,
                "level": current_level,
                "points_to_next_level": points_to_next,
                "current_streak_days": new_streak,
                "last_completion_date": completion_date,
            }
        )

        # Update daily activity
        self._update_daily_activity(completion_date, total_points)

        return {
            "base_points": base_points,
            "bonus_points": bonus_points,
            "total_points": total_points,
            "new_streak": new_streak,
            "level_up": level_up,
            "new_level": current_level,
            "daily_goal_met": self._check_daily_goal_met(completion_date),
        }

    def update_streak(self, completion_date: date = None) -> int:
        """
        Update user streak based on completion.

        Args:
            completion_date: Date of completion (defaults to today).

        Returns:
            New streak count.
        """
        if completion_date is None:
            completion_date = date.today()

        current_stats = self.user_stats_repo.get_current_stats()
        if not current_stats:
            current_stats = self._initialize_user_stats()

        last_completion = current_stats.last_completion_date

        if last_completion is None:
            # First completion ever
            new_streak = 1
        elif completion_date == last_completion:
            # Same day completion - maintain streak
            new_streak = current_stats.current_streak_days
        elif completion_date == last_completion + timedelta(days=1):
            # Next day completion - extend streak
            new_streak = current_stats.current_streak_days + 1
        elif (completion_date - last_completion).days <= 1:
            # Within streak window - maintain
            new_streak = current_stats.current_streak_days
        else:
            # Streak broken - reset to 1
            new_streak = 1

        # Update longest streak if needed
        longest_streak = max(current_stats.longest_streak_days, new_streak)

        # Update user stats with new streak info
        self.user_stats_repo.update_stats(
            {
                "current_streak_days": new_streak,
                "longest_streak_days": longest_streak,
                "last_completion_date": completion_date,
            }
        )

        return new_streak

    def calculate_level(self, total_points: int) -> tuple[int, int, int]:
        """
        Calculate current level and progress.

        Args:
            total_points: Total points earned.

        Returns:
            Tuple of (current_level, points_to_next_level, points_for_current_level)
        """
        current_level = 1
        points_for_current_level = 0

        # Find current level
        for level, threshold in enumerate(self.level_thresholds, 1):
            if total_points >= threshold:
                current_level = level
                points_for_current_level = threshold
            else:
                break

        # Calculate points needed for next level
        if current_level < len(self.level_thresholds):
            next_level_threshold = self.level_thresholds[current_level]
            points_to_next_level = next_level_threshold - total_points
        else:
            # Max level reached
            points_to_next_level = 0

        return current_level, points_to_next_level, points_for_current_level

    def apply_overdue_penalties(self) -> int:
        """
        Apply penalties for overdue tasks.

        Returns:
            Total penalty points applied.
        """
        overdue_todos = self.todo_repo.get_overdue_todos()
        total_penalty = 0

        for todo in overdue_todos:
            if todo.due_date:
                days_overdue = (date.today() - todo.due_date).days
                penalty = min(days_overdue, 5)  # Max 5 point penalty per task

                # Apply penalty to user stats
                current_stats = self.user_stats_repo.get_current_stats()
                if current_stats:
                    new_total = max(0, current_stats.total_points - penalty)
                    self.user_stats_repo.update_stats({"total_points": new_total})

                    # Record penalty in daily activity
                    today_activity = self.daily_activity_repo.get_today_activity()
                    if today_activity:
                        new_penalty = today_activity.overdue_penalty_applied + penalty
                        self.daily_activity_repo.update_activity(
                            date.today(), {"overdue_penalty_applied": new_penalty}
                        )

                    total_penalty += penalty

        return total_penalty

    def get_user_progress(self) -> dict[str, Any]:
        """
        Get comprehensive user progress information.

        Returns:
            Dictionary with user progress data.
        """
        current_stats = self.user_stats_repo.get_current_stats()
        if not current_stats:
            current_stats = self._initialize_user_stats()

        today_activity = self.daily_activity_repo.get_today_activity()

        # Calculate level info
        current_level, points_to_next, points_for_current = self.calculate_level(
            current_stats.total_points
        )

        return {
            "total_points": current_stats.total_points,
            "level": current_level,
            "points_to_next_level": points_to_next,
            "current_streak": current_stats.current_streak_days,
            "longest_streak": current_stats.longest_streak_days,
            "total_completed": current_stats.total_tasks_completed,
            "daily_goal": current_stats.daily_goal,
            "tasks_completed_today": today_activity.tasks_completed
            if today_activity
            else 0,
            "daily_goal_met": today_activity.daily_goal_met
            if today_activity
            else False,
            "points_earned_today": today_activity.total_points_earned
            if today_activity
            else 0,
        }

    def _get_streak_multiplier(self, streak_days: int) -> float:
        """Get streak multiplier based on current streak."""
        multiplier = 1.0
        for threshold, mult in sorted(self.streak_multipliers.items(), reverse=True):
            if streak_days >= threshold:
                multiplier = mult
                break
        return multiplier

    def _initialize_user_stats(self) -> UserStats:
        """Initialize user stats if they don't exist."""
        default_stats = UserStats(
            total_points=0,
            level=1,
            points_to_next_level=100,
            total_tasks_completed=0,
            total_tasks_created=0,
            current_streak_days=0,
            longest_streak_days=0,
            last_completion_date=None,
            daily_goal=3,
            weekly_goal=20,
            monthly_goal=80,
            achievements_unlocked=0,
        )

        # Save to database
        conn = self.db.connect()
        conn.execute(
            """
            INSERT INTO user_stats (
                total_points, level, points_to_next_level, total_tasks_completed,
                total_tasks_created, current_streak_days, longest_streak_days,
                daily_goal, weekly_goal, monthly_goal, achievements_unlocked
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT DO NOTHING
        """,
            [0, 1, 100, 0, 0, 0, 0, 3, 20, 80, 0],
        )

        return default_stats

    def _update_daily_activity(self, activity_date: date, points_earned: int) -> None:
        """Update daily activity record."""
        current_activity = self.daily_activity_repo.get_activity_for_date(activity_date)

        if current_activity:
            # Update existing record
            new_tasks = current_activity.tasks_completed + 1
            new_points = current_activity.total_points_earned + points_earned

            # Check if daily goal is met
            current_stats = self.user_stats_repo.get_current_stats()
            daily_goal_met = new_tasks >= (
                current_stats.daily_goal if current_stats else 3
            )

            self.daily_activity_repo.update_activity(
                activity_date,
                {
                    "tasks_completed": new_tasks,
                    "total_points_earned": new_points,
                    "daily_goal_met": daily_goal_met,
                },
            )
        else:
            # Create new record
            current_stats = self.user_stats_repo.get_current_stats()
            daily_goal_met = (current_stats.daily_goal if current_stats else 3) <= 1

            self.daily_activity_repo.create_activity(
                activity_date=activity_date,
                tasks_completed=1,
                total_points_earned=points_earned,
                daily_goal_met=daily_goal_met,
            )

    def _check_daily_goal_met(self, activity_date: date) -> bool:
        """Check if daily goal was met for given date."""
        activity = self.daily_activity_repo.get_activity_for_date(activity_date)
        return activity.daily_goal_met if activity else False
