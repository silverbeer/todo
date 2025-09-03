"""Achievement system for recognizing user milestones and providing motivation."""

from datetime import date, datetime
from typing import Any

from ..db.connection import DatabaseConnection
from ..db.repository import (
    AchievementRepository,
    DailyActivityRepository,
    UserStatsRepository,
)
from ..models import Achievement, UserStats


class AchievementService:
    """Service for managing achievements, checking requirements, and unlocking rewards."""

    def __init__(self, db_connection: DatabaseConnection):
        """Initialize achievement service with database connection."""
        self.db = db_connection
        self.achievement_repo = AchievementRepository(db_connection)
        self.user_stats_repo = UserStatsRepository(db_connection)
        self.daily_activity_repo = DailyActivityRepository(db_connection)

        # Enhanced achievement definitions (expanding on the base 10 in schema.sql)
        self.extended_achievement_definitions = [
            # Basic achievements that match schema.sql
            {
                "name": "First Steps",
                "description": "Complete your first task",
                "icon": "🎯",
                "requirement_type": "tasks_completed",
                "requirement_value": 1,
                "bonus_points": 10,
            },
            {
                "name": "Getting Started",
                "description": "Complete 10 tasks",
                "icon": "🚀",
                "requirement_type": "tasks_completed",
                "requirement_value": 10,
                "bonus_points": 25,
            },
            {
                "name": "Productive",
                "description": "Complete 50 tasks",
                "icon": "⚡",
                "requirement_type": "tasks_completed",
                "requirement_value": 50,
                "bonus_points": 50,
            },
            {
                "name": "Century Club",
                "description": "Complete 100 tasks",
                "icon": "💯",
                "requirement_type": "tasks_completed",
                "requirement_value": 100,
                "bonus_points": 100,
            },
            {
                "name": "Task Master",
                "description": "Complete 500 tasks",
                "icon": "👑",
                "requirement_type": "tasks_completed",
                "requirement_value": 500,
                "bonus_points": 250,
            },
            {
                "name": "Day One",
                "description": "Maintain a 1-day streak",
                "icon": "📅",
                "requirement_type": "streak_days",
                "requirement_value": 1,
                "bonus_points": 5,
            },
            {
                "name": "Week Warrior",
                "description": "Maintain a 7-day streak",
                "icon": "🔥",
                "requirement_type": "streak_days",
                "requirement_value": 7,
                "bonus_points": 35,
            },
            {
                "name": "Month Champion",
                "description": "Maintain a 30-day streak",
                "icon": "🏆",
                "requirement_type": "streak_days",
                "requirement_value": 30,
                "bonus_points": 150,
            },
            {
                "name": "Point Collector",
                "description": "Earn 1000 points",
                "icon": "💎",
                "requirement_type": "points_earned",
                "requirement_value": 1000,
                "bonus_points": 100,
            },
            {
                "name": "Point Master",
                "description": "Earn 5000 points",
                "icon": "💍",
                "requirement_type": "points_earned",
                "requirement_value": 5000,
                "bonus_points": 500,
            },
            # Additional task completion milestones
            {
                "name": "Legendary",
                "description": "Complete 1000 tasks",
                "icon": "🏆",
                "requirement_type": "tasks_completed",
                "requirement_value": 1000,
                "bonus_points": 500,
            },
            {
                "name": "Unstoppable",
                "description": "Complete 2500 tasks",
                "icon": "🚀",
                "requirement_type": "tasks_completed",
                "requirement_value": 2500,
                "bonus_points": 1000,
            },
            # Enhanced streak achievements
            {
                "name": "Consistency",
                "description": "Maintain a 3-day streak",
                "icon": "📅",
                "requirement_type": "streak_days",
                "requirement_value": 3,
                "bonus_points": 15,
            },
            {
                "name": "Fortnight Force",
                "description": "Maintain a 14-day streak",
                "icon": "🌟",
                "requirement_type": "streak_days",
                "requirement_value": 14,
                "bonus_points": 70,
            },
            {
                "name": "Streak Master",
                "description": "Maintain a 60-day streak",
                "icon": "🔥",
                "requirement_type": "streak_days",
                "requirement_value": 60,
                "bonus_points": 300,
            },
            {
                "name": "Century Streak",
                "description": "Maintain a 100-day streak",
                "icon": "💯",
                "requirement_type": "streak_days",
                "requirement_value": 100,
                "bonus_points": 500,
            },
            # Point accumulation achievements
            {
                "name": "Point Hunter",
                "description": "Earn 500 points",
                "icon": "💰",
                "requirement_type": "points_earned",
                "requirement_value": 500,
                "bonus_points": 50,
            },
            {
                "name": "Point Hoarder",
                "description": "Earn 2500 points",
                "icon": "💎",
                "requirement_type": "points_earned",
                "requirement_value": 2500,
                "bonus_points": 250,
            },
            {
                "name": "Point Millionaire",
                "description": "Earn 10000 points",
                "icon": "👑",
                "requirement_type": "points_earned",
                "requirement_value": 10000,
                "bonus_points": 1000,
            },
            # Daily goal achievements
            {
                "name": "Goal Getter",
                "description": "Hit your daily goal for the first time",
                "icon": "🎯",
                "requirement_type": "daily_goals_met",
                "requirement_value": 1,
                "bonus_points": 20,
            },
            {
                "name": "Consistent Achiever",
                "description": "Hit daily goal 7 times",
                "icon": "⭐",
                "requirement_type": "daily_goals_met",
                "requirement_value": 7,
                "bonus_points": 50,
            },
            {
                "name": "Goal Crusher",
                "description": "Hit daily goal 30 times",
                "icon": "💪",
                "requirement_type": "daily_goals_met",
                "requirement_value": 30,
                "bonus_points": 150,
            },
            {
                "name": "Goal Master",
                "description": "Hit daily goal 100 times",
                "icon": "🏆",
                "requirement_type": "daily_goals_met",
                "requirement_value": 100,
                "bonus_points": 500,
            },
            # Level-based achievements
            {
                "name": "Level Up",
                "description": "Reach level 5",
                "icon": "📈",
                "requirement_type": "level_reached",
                "requirement_value": 5,
                "bonus_points": 50,
            },
            {
                "name": "High Achiever",
                "description": "Reach level 10",
                "icon": "🌟",
                "requirement_type": "level_reached",
                "requirement_value": 10,
                "bonus_points": 100,
            },
            {
                "name": "Elite Status",
                "description": "Reach level 20",
                "icon": "👑",
                "requirement_type": "level_reached",
                "requirement_value": 20,
                "bonus_points": 250,
            },
            # Special achievements (for future implementation)
            {
                "name": "Night Owl",
                "description": "Complete a task after 10 PM",
                "icon": "🦉",
                "requirement_type": "special_late_completion",
                "requirement_value": 1,
                "bonus_points": 15,
            },
            {
                "name": "Early Bird",
                "description": "Complete a task before 6 AM",
                "icon": "🐦",
                "requirement_type": "special_early_completion",
                "requirement_value": 1,
                "bonus_points": 15,
            },
            {
                "name": "Weekend Warrior",
                "description": "Complete 10 tasks on weekends",
                "icon": "🏃‍♂️",
                "requirement_type": "weekend_completions",
                "requirement_value": 10,
                "bonus_points": 50,
            },
        ]

    def check_and_unlock_achievements(self, user_stats: UserStats) -> list[Achievement]:
        """
        Check for newly unlocked achievements and award bonus points.

        Args:
            user_stats: Current user statistics.

        Returns:
            List of newly unlocked achievements.
        """
        if not user_stats:
            return []

        newly_unlocked = []

        try:
            # Get current achievement states
            all_achievements = self.achievement_repo.get_all_achievements()
            unlocked_names = {a.name for a in all_achievements if a.is_unlocked}

            # Check built-in achievements (from schema.sql) and extended definitions
            all_definitions = self.extended_achievement_definitions

            for definition in all_definitions:
                achievement_name = definition["name"]

                # Skip if already unlocked
                if achievement_name in unlocked_names:
                    continue

                # Check if requirement is met
                is_unlocked = self._check_requirement(definition, user_stats)

                if is_unlocked:
                    # Find existing achievement or create new one
                    existing = next(
                        (a for a in all_achievements if a.name == achievement_name),
                        None,
                    )

                    if existing:
                        # Update existing achievement
                        self.achievement_repo.unlock_achievement(existing.id)
                        existing.is_unlocked = True
                        existing.unlocked_at = datetime.utcnow()
                        newly_unlocked.append(existing)
                    else:
                        # Create new achievement (for extended definitions)
                        new_achievement = Achievement(
                            name=definition["name"],
                            description=definition["description"],
                            icon=definition["icon"],
                            requirement_type=definition["requirement_type"],
                            requirement_value=definition["requirement_value"],
                            bonus_points=definition["bonus_points"],
                            is_unlocked=True,
                            unlocked_at=datetime.utcnow(),
                        )

                        try:
                            created_achievement = self.achievement_repo.create(
                                new_achievement
                            )
                            newly_unlocked.append(created_achievement)
                        except Exception:
                            # Achievement might already exist, skip silently
                            continue

                    # Award bonus points
                    if definition["bonus_points"] > 0:
                        self._award_achievement_bonus(
                            user_stats, definition["bonus_points"]
                        )

        except Exception:
            # Handle database errors gracefully
            pass

        return newly_unlocked

    def _check_requirement(
        self, definition: dict[str, Any], user_stats: UserStats
    ) -> bool:
        """Check if achievement requirement is met."""
        if not user_stats:
            return False

        requirement_type = definition["requirement_type"]
        requirement_value = definition["requirement_value"]

        try:
            if requirement_type == "tasks_completed":
                return (
                    getattr(user_stats, "total_tasks_completed", 0) >= requirement_value
                )
            elif requirement_type == "streak_days":
                return (
                    getattr(user_stats, "current_streak_days", 0) >= requirement_value
                )
            elif requirement_type == "points_earned":
                return getattr(user_stats, "total_points", 0) >= requirement_value
            elif requirement_type == "daily_goals_met":
                # Count days where daily goal was met
                goals_met = self._count_daily_goals_met()
                return goals_met >= requirement_value
            elif requirement_type == "level_reached":
                return getattr(user_stats, "level", 1) >= requirement_value
            elif requirement_type in [
                "special_late_completion",
                "special_early_completion",
                "weekend_completions",
            ]:
                # These would require custom tracking - implement later if needed
                return False
        except (AttributeError, TypeError):
            return False

        return False

    def _count_daily_goals_met(self) -> int:
        """Count the number of days where daily goal was met."""
        # Get recent activity to count goal achievements
        recent_activity = self.daily_activity_repo.get_recent_activity(
            days=365
        )  # Look back 1 year
        return len(
            [activity for activity in recent_activity if activity.daily_goal_met]
        )

    def _award_achievement_bonus(
        self, user_stats: UserStats, bonus_points: int
    ) -> None:
        """Award bonus points for unlocking achievement."""
        new_total_points = user_stats.total_points + bonus_points
        new_achievements_count = user_stats.achievements_unlocked + 1

        self.user_stats_repo.update_stats(
            {
                "total_points": new_total_points,
                "achievements_unlocked": new_achievements_count,
            }
        )

    def get_achievement_progress(
        self, user_stats: UserStats
    ) -> dict[str, dict[str, Any]]:
        """
        Get progress toward all achievements.

        Args:
            user_stats: Current user statistics.

        Returns:
            Dictionary mapping achievement names to progress information.
        """
        progress = {}

        # Get all achievements from database
        all_achievements = self.achievement_repo.get_all_achievements()

        # Add extended definitions that might not be in DB yet
        all_definitions = self.extended_achievement_definitions

        # Create a comprehensive list combining DB achievements and definitions
        achievement_map = {a.name: a for a in all_achievements}

        for definition in all_definitions:
            name = definition["name"]
            current_progress = self._get_current_progress(definition, user_stats)
            required = definition["requirement_value"]
            percentage = (
                min(100, (current_progress / required) * 100) if required > 0 else 0
            )

            # Check if achievement exists in database and is unlocked
            db_achievement = achievement_map.get(name)
            is_unlocked = db_achievement.is_unlocked if db_achievement else False

            progress[name] = {
                "description": definition["description"],
                "icon": definition["icon"],
                "current": current_progress,
                "required": required,
                "percentage": round(percentage, 1),
                "completed": is_unlocked or current_progress >= required,
                "bonus_points": definition["bonus_points"],
                "unlocked": is_unlocked,
            }

        return progress

    def _get_current_progress(
        self, definition: dict[str, Any], user_stats: UserStats
    ) -> int:
        """Get current progress value for an achievement."""
        requirement_type = definition["requirement_type"]

        if requirement_type == "tasks_completed":
            return user_stats.total_tasks_completed
        elif requirement_type == "streak_days":
            return user_stats.current_streak_days
        elif requirement_type == "points_earned":
            return user_stats.total_points
        elif requirement_type == "daily_goals_met":
            return self._count_daily_goals_met()
        elif requirement_type == "level_reached":
            return user_stats.level

        return 0

    def get_achievements_summary(self, user_stats: UserStats) -> dict[str, Any]:
        """
        Get a summary of achievement status.

        Args:
            user_stats: Current user statistics.

        Returns:
            Summary information about achievements.
        """
        all_achievements = self.achievement_repo.get_all_achievements()
        unlocked_achievements = [a for a in all_achievements if a.is_unlocked]

        # Calculate total possible achievements (DB + extended definitions)
        extended_names = {d["name"] for d in self.extended_achievement_definitions}
        db_names = {a.name for a in all_achievements}
        total_possible = len(extended_names | db_names)

        # Find recently unlocked (last 30 days)
        from datetime import timedelta

        thirty_days_ago = date.today() - timedelta(days=30)
        recent_unlocks = [
            a
            for a in unlocked_achievements
            if a.unlocked_at and a.unlocked_at.date() > thirty_days_ago
        ]

        return {
            "total_unlocked": len(unlocked_achievements),
            "total_possible": total_possible,
            "completion_percentage": round(
                (len(unlocked_achievements) / total_possible) * 100, 1
            )
            if total_possible > 0
            else 0,
            "recent_unlocks": len(recent_unlocks),
            "next_milestone": self._find_next_milestone(user_stats),
        }

    def _find_next_milestone(self, user_stats: UserStats) -> dict[str, Any] | None:
        """Find the closest achievement milestone."""
        progress = self.get_achievement_progress(user_stats)

        # Find the closest incomplete achievement
        incomplete = {
            name: data
            for name, data in progress.items()
            if not data["completed"] and data["current"] > 0
        }

        if not incomplete:
            return None

        # Sort by completion percentage (descending) to find closest
        closest = max(incomplete.items(), key=lambda x: x[1]["percentage"])

        return {
            "name": closest[0],
            "description": closest[1]["description"],
            "icon": closest[1]["icon"],
            "current": closest[1]["current"],
            "required": closest[1]["required"],
            "percentage": closest[1]["percentage"],
        }
