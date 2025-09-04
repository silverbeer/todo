"""Analytics service for generating productivity insights and reports."""

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from ..db.connection import DatabaseConnection
from ..db.repository import DailyActivityRepository, TodoRepository, UserStatsRepository
from ..models import DailyActivity, Todo


class AnalyticsService:
    """Service for generating productivity analytics and insights."""

    def __init__(self, db_connection: DatabaseConnection):
        """Initialize analytics service with database connection."""
        self.db = db_connection
        self.todo_repo = TodoRepository(db_connection)
        self.user_stats_repo = UserStatsRepository(db_connection)
        self.daily_activity_repo = DailyActivityRepository(db_connection)

    def generate_productivity_report(self, days: int = 30) -> dict[str, Any]:
        """Generate comprehensive productivity report."""
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)

            # Get activity data (for future use)
            # activity = self.daily_activity_repo.get_recent_activity(days=days)
            todos = self.todo_repo.get_completed_todos_for_period(start_date, end_date)
            created_todos = self.todo_repo.get_todos_created_for_period(
                start_date, end_date
            )

            # Basic statistics
            total_completed = len(todos)
            total_created = len(created_todos)
            completion_rate = (
                (total_completed / total_created * 100) if total_created > 0 else 0
            )

            # Get current user stats for streak and points
            current_stats = self.user_stats_repo.get_current_stats()
            current_streak = current_stats.current_streak_days if current_stats else 0
            total_points = current_stats.total_points if current_stats else 0

            # Productivity trends
            trend = self._calculate_simple_trend(days=days)

            # Category breakdown
            category_breakdown = self._get_category_breakdown(days=days)

            # Generate insights
            insights = self._generate_insights(current_stats, days=days)

            return {
                "total_completed": total_completed,
                "total_created": total_created,
                "completion_rate": completion_rate,
                "current_streak": current_streak,
                "total_points": total_points,
                "trend": trend,
                "category_breakdown": category_breakdown,
                "insights": insights,
            }
        except Exception:
            # Return default values on error
            return {
                "total_completed": 0,
                "total_created": 0,
                "completion_rate": 0,
                "current_streak": 0,
                "total_points": 0,
                "trend": {"direction": "stable", "slope": 0, "confidence": 0},
                "category_breakdown": [],
                "insights": [],
            }

    def get_streak_analysis(self) -> dict[str, Any]:
        """Analyze streak patterns and performance."""
        try:
            user_stats = self.user_stats_repo.get_current_stats()
            if not user_stats:
                return {"current_streak": 0, "longest_streak": 0, "streak_history": []}

            return {
                "current_streak": user_stats.current_streak_days or 0,
                "longest_streak": user_stats.longest_streak_days or 0,
                "streak_history": [],  # Simplified for now
            }
        except Exception:
            return {"current_streak": 0, "longest_streak": 0, "streak_history": []}

    def get_weekly_summary(self) -> dict[str, Any]:
        """Get current week's productivity summary."""
        try:
            today = date.today()
            week_start = today - timedelta(days=today.weekday())  # Monday
            prev_week_start = week_start - timedelta(days=7)
            prev_week_end = week_start - timedelta(days=1)

            # Get completed todos for current and previous week
            current_week_todos = self.todo_repo.get_completed_todos_for_period(
                week_start, today
            )
            prev_week_todos = self.todo_repo.get_completed_todos_for_period(
                prev_week_start, prev_week_end
            )

            current_week = {
                "week_start": week_start.isoformat(),
                "week_end": (week_start + timedelta(days=6)).isoformat(),
                "completed_tasks": len(current_week_todos),
                "points_earned": len(current_week_todos) * 10,  # Simplified
                "active_days": min(7, (today - week_start).days + 1),
            }

            previous_week = {
                "week_start": prev_week_start.isoformat(),
                "week_end": prev_week_end.isoformat(),
                "completed_tasks": len(prev_week_todos),
                "points_earned": len(prev_week_todos) * 10,  # Simplified
                "active_days": 7,
            }

            return {"current_week": current_week, "previous_week": previous_week}
        except Exception:
            return {
                "current_week": {
                    "week_start": date.today().isoformat(),
                    "week_end": date.today().isoformat(),
                    "completed_tasks": 0,
                    "points_earned": 0,
                    "active_days": 0,
                },
                "previous_week": {
                    "week_start": (date.today() - timedelta(days=7)).isoformat(),
                    "week_end": (date.today() - timedelta(days=1)).isoformat(),
                    "completed_tasks": 0,
                    "points_earned": 0,
                    "active_days": 0,
                },
            }

    def get_monthly_summary(self) -> dict[str, Any]:
        """Get current month's productivity summary."""
        try:
            today = date.today()
            month_start = today.replace(day=1)

            # Previous month
            if month_start.month == 1:
                prev_month_start = month_start.replace(
                    year=month_start.year - 1, month=12
                )
                prev_month_end = month_start - timedelta(days=1)
            else:
                prev_month_start = month_start.replace(month=month_start.month - 1)
                if prev_month_start.month == 12:
                    prev_month_end = prev_month_start.replace(
                        year=prev_month_start.year + 1, month=1
                    ) - timedelta(days=1)
                else:
                    prev_month_end = prev_month_start.replace(
                        month=prev_month_start.month + 1
                    ) - timedelta(days=1)

            # Get completed todos for current and previous month
            current_month_todos = self.todo_repo.get_completed_todos_for_period(
                month_start, today
            )
            prev_month_todos = self.todo_repo.get_completed_todos_for_period(
                prev_month_start, prev_month_end
            )

            current_month = {
                "month_start": month_start.isoformat(),
                "month_end": today.isoformat(),
                "completed_tasks": len(current_month_todos),
                "points_earned": len(current_month_todos) * 10,
                "active_days": (today - month_start).days + 1,
            }

            previous_month = {
                "month_start": prev_month_start.isoformat(),
                "month_end": prev_month_end.isoformat(),
                "completed_tasks": len(prev_month_todos),
                "points_earned": len(prev_month_todos) * 10,
                "active_days": (prev_month_end - prev_month_start).days + 1,
            }

            return {"current_month": current_month, "previous_month": previous_month}
        except Exception:
            return {
                "current_month": {
                    "month_start": date.today().replace(day=1).isoformat(),
                    "month_end": date.today().isoformat(),
                    "completed_tasks": 0,
                    "points_earned": 0,
                    "active_days": 0,
                },
                "previous_month": {
                    "month_start": (date.today().replace(day=1) - timedelta(days=1))
                    .replace(day=1)
                    .isoformat(),
                    "month_end": (
                        date.today().replace(day=1) - timedelta(days=1)
                    ).isoformat(),
                    "completed_tasks": 0,
                    "points_earned": 0,
                    "active_days": 0,
                },
            }

    def _calculate_simple_trend(self, days: int = 30) -> dict[str, Any]:
        """Calculate simple trend analysis."""
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)
            todos = self.todo_repo.get_completed_todos_for_period(start_date, end_date)

            total = len(todos)
            if total < 2:
                return {"direction": "stable", "slope": 0, "confidence": 0}

            # Simple trend based on recent vs. older completions
            mid_date = start_date + timedelta(days=days // 2)
            recent_todos = [
                t for t in todos if t.completed_at and t.completed_at.date() >= mid_date
            ]
            older_todos = [
                t for t in todos if t.completed_at and t.completed_at.date() < mid_date
            ]

            recent_count = len(recent_todos)
            older_count = len(older_todos)

            if recent_count > older_count * 1.2:
                return {"direction": "improving", "slope": 0.2, "confidence": 0.7}
            elif recent_count < older_count * 0.8:
                return {"direction": "declining", "slope": -0.2, "confidence": 0.7}
            else:
                return {"direction": "stable", "slope": 0, "confidence": 0.5}
        except Exception:
            return {"direction": "stable", "slope": 0, "confidence": 0}

    def _get_category_breakdown(self, days: int = 30) -> list[dict[str, Any]]:
        """Get category breakdown for completed tasks."""
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)
            todos = self.todo_repo.get_completed_todos_for_period(start_date, end_date)

            if not todos:
                return []

            category_counts = {}
            total_tasks = len(todos)

            for todo in todos:
                category = todo.category or "Uncategorized"
                category_counts[category] = category_counts.get(category, 0) + 1

            breakdown = []
            for category, count in category_counts.items():
                percentage = (count / total_tasks) * 100
                breakdown.append(
                    {"category": category, "count": count, "percentage": percentage}
                )

            return sorted(breakdown, key=lambda x: x["count"], reverse=True)
        except Exception:
            return []

    def _generate_insights(self, user_stats: Any, days: int = 30) -> list[str]:  # noqa: ARG002
        """Generate insights based on user performance."""
        try:
            insights = []

            if user_stats:
                if (
                    user_stats.current_streak_days
                    and user_stats.current_streak_days > 3
                ):
                    insights.append(
                        f"Great job maintaining a {user_stats.current_streak_days}-day streak!"
                    )

                if (
                    user_stats.total_tasks_completed
                    and user_stats.total_tasks_completed > 20
                ):
                    insights.append("You're building great productivity habits!")

                if user_stats.level and user_stats.level > 1:
                    insights.append(
                        f"You've reached level {user_stats.level} - keep up the momentum!"
                    )

            # Add default insights if none generated
            if not insights:
                insights.append("Start completing tasks to see personalized insights!")

            return insights
        except Exception:
            return ["Keep working on your tasks to unlock insights!"]

    def _analyze_completion_patterns(self, days: int = 30) -> dict[str, Any]:
        """Analyze completion patterns."""
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)
            todos = self.todo_repo.get_completed_todos_for_period(start_date, end_date)

            # Simple pattern analysis
            day_counts = [0] * 7  # Monday = 0, Sunday = 6
            hour_counts = [0] * 24

            for todo in todos:
                if todo.completed_at:
                    day_counts[todo.completed_at.weekday()] += 1
                    hour_counts[todo.completed_at.hour] += 1

            best_day = max(enumerate(day_counts), key=lambda x: x[1])[0]
            best_hour = max(enumerate(hour_counts), key=lambda x: x[1])[0]

            day_names = [
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
            ]

            return {
                "by_day_of_week": [
                    {"day": day_names[i], "count": count}
                    for i, count in enumerate(day_counts)
                ],
                "by_hour": hour_counts,
                "peak_productivity_day": day_names[best_day],
                "peak_productivity_hour": best_hour,
            }
        except Exception:
            return {
                "by_day_of_week": [
                    {"day": day, "count": 0}
                    for day in [
                        "Monday",
                        "Tuesday",
                        "Wednesday",
                        "Thursday",
                        "Friday",
                        "Saturday",
                        "Sunday",
                    ]
                ],
                "by_hour": [0] * 24,
                "peak_productivity_day": "Monday",
                "peak_productivity_hour": 9,
            }

    def _calculate_productivity_score(self, user_stats: Any) -> int:
        """Calculate a productivity score (0-100) based on user stats."""
        try:
            if not user_stats:
                return 0

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
        except Exception:
            return 0

    def _calculate_trend(self, values: list[int]) -> str:
        """Calculate trend direction from values."""
        if len(values) < 2:
            return "stable"

        # Simple linear regression slope
        x = list(range(len(values)))
        y = values

        n = len(values)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(x[i] * y[i] for i in range(n))
        sum_x2 = sum(x[i] ** 2 for i in range(n))

        if n * sum_x2 - sum_x**2 == 0:
            return "stable"

        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x**2)

        if slope > 0.1:
            return "improving"
        elif slope < -0.1:
            return "declining"
        else:
            return "stable"

    def _analyze_category_distribution(self, todos: list[Todo]) -> dict[str, Any]:
        """Analyze task distribution by category."""
        category_counts = defaultdict(int)
        category_points = defaultdict(int)

        for todo in todos:
            category = todo.category.name if todo.category else "Uncategorized"
            category_counts[category] += 1
            category_points[category] += todo.total_points_earned or 0

        total_tasks = sum(category_counts.values()) if category_counts else 0

        distribution = {}
        for cat, count in category_counts.items():
            distribution[cat] = {
                "count": count,
                "percentage": (count / total_tasks) * 100 if total_tasks > 0 else 0,
                "points": category_points[cat],
            }

        return {
            "distribution": distribution,
            "most_productive_category": (
                max(category_points.items(), key=lambda x: x[1])[0]
                if category_points
                else None
            ),
            "most_frequent_category": (
                max(category_counts.items(), key=lambda x: x[1])[0]
                if category_counts
                else None
            ),
        }

    def _analyze_completion_patterns(self, todos: list[Todo]) -> dict[str, Any]:
        """Analyze when tasks are typically completed."""
        completed_todos = [
            t for t in todos if hasattr(t, "completed_at") and t.completed_at
        ]

        if not completed_todos:
            return {}

        # Hour of day analysis
        hours = [t.completed_at.hour for t in completed_todos]
        hour_distribution = defaultdict(int)
        for hour in hours:
            hour_distribution[hour] += 1

        # Day of week analysis
        weekdays = [t.completed_at.weekday() for t in completed_todos]
        weekday_distribution = defaultdict(int)
        weekday_names = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]

        for weekday in weekdays:
            weekday_distribution[weekday_names[weekday]] += 1

        # Find peak hours and days
        peak_hour = (
            max(hour_distribution.items(), key=lambda x: x[1])[0]
            if hour_distribution
            else None
        )
        peak_day = (
            max(weekday_distribution.items(), key=lambda x: x[1])[0]
            if weekday_distribution
            else None
        )

        return {
            "peak_hour": peak_hour,
            "peak_day": peak_day,
            "hour_distribution": dict(hour_distribution),
            "weekday_distribution": dict(weekday_distribution),
            "avg_completion_hour": sum(hours) / len(hours) if hours else None,
        }

    def _analyze_goal_achievement(
        self, activity: list[DailyActivity]
    ) -> dict[str, Any]:
        """Analyze goal achievement patterns."""
        if not activity:
            return {}

        goals_met = len([a for a in activity if a.daily_goal_met])
        total_days = len(activity)
        achievement_rate = (goals_met / total_days) * 100 if total_days > 0 else 0

        # Calculate streaks of consecutive goal achievements
        goal_streaks = []
        current_streak = 0

        for day_activity in activity:
            if day_activity.daily_goal_met:
                current_streak += 1
            else:
                if current_streak > 0:
                    goal_streaks.append(current_streak)
                current_streak = 0

        # Don't forget the current streak if it's ongoing
        if current_streak > 0:
            goal_streaks.append(current_streak)

        return {
            "goals_met": goals_met,
            "total_days": total_days,
            "achievement_rate": round(achievement_rate, 1),
            "best_streak": max(goal_streaks) if goal_streaks else 0,
            "average_streak": sum(goal_streaks) / len(goal_streaks)
            if goal_streaks
            else 0,
            "current_goal_streak": current_streak,
        }

    def _analyze_weekly_pattern(
        self, activity: list[DailyActivity]
    ) -> dict[str, float]:
        """Analyze productivity patterns by day of week."""
        weekday_totals = defaultdict(list)

        for day_activity in activity:
            weekday = day_activity.activity_date.weekday()
            weekday_totals[weekday].append(day_activity.tasks_completed)

        weekday_names = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]

        pattern = {}
        for i in range(7):
            tasks = weekday_totals[i]
            avg = sum(tasks) / len(tasks) if tasks else 0
            pattern[weekday_names[i]] = round(avg, 1)

        return pattern

    def _find_best_day(self, activity: list[DailyActivity]) -> dict[str, Any]:
        """Find the most productive day."""
        if not activity:
            return {}

        best_day = max(activity, key=lambda a: a.tasks_completed)

        return {
            "date": best_day.activity_date,
            "tasks": best_day.tasks_completed,
            "points": best_day.total_points_earned,
            "goal_met": best_day.daily_goal_met,
        }

    def _calculate_consistency(self, activity: list[DailyActivity]) -> int:
        """Calculate consistency score (0-100)."""
        if not activity:
            return 0

        active_days = len([a for a in activity if a.tasks_completed > 0])
        total_days = len(activity)

        return int((active_days / total_days) * 100) if total_days > 0 else 0

    def _calculate_productivity_score(self, activity: list[DailyActivity]) -> int:
        """Calculate overall productivity score (0-100)."""
        if not activity:
            return 0

        scores = []

        # Consistency score (0-25): Based on active days
        active_days = len([a for a in activity if a.tasks_completed > 0])
        consistency_score = min(25, (active_days / len(activity)) * 25)
        scores.append(consistency_score)

        # Volume score (0-25): Based on total tasks
        total_tasks = sum(a.tasks_completed for a in activity)
        avg_tasks_per_day = total_tasks / len(activity)
        volume_score = min(25, avg_tasks_per_day * 5)  # 5 tasks/day = max score
        scores.append(volume_score)

        # Goal achievement score (0-25): Based on daily goals met
        goals_met = len([a for a in activity if a.daily_goal_met])
        goal_score = min(25, (goals_met / len(activity)) * 25)
        scores.append(goal_score)

        # Trend score (0-25): Based on recent improvement
        recent_tasks = [a.tasks_completed for a in activity[-7:]]
        trend = self._calculate_trend(recent_tasks)
        trend_score = {"improving": 25, "stable": 15, "declining": 5}.get(trend, 10)
        scores.append(trend_score)

        return int(sum(scores))
