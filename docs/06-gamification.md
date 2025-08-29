# Gamification System - Implementation Plan

> **⚠️ IMPORTANT**: Review this document before implementation. As we develop the application, requirements may change and this documentation should be updated to reflect any modifications to the gamification and scoring systems.

## Overview
This document outlines the complete gamification system designed to make todo management engaging and addictive. The system includes points, levels, streaks, achievements, goals, and penalties to motivate consistent task completion and productivity.

## Core Scoring System

### Point Values and Calculation
```python
# src/todo/core/scoring.py
from typing import Dict, List, Optional, Tuple
from datetime import date, datetime, timedelta
from todo.models.todo import Todo, TaskSize
from todo.models.gamification import UserStats, DailyActivity, Achievement
from todo.db.repositories.gamification import GamificationRepository
from todo.db.repositories.todo import TodoRepository

class ScoringService:
    """Core service for calculating points, bonuses, and managing gamification."""

    def __init__(self):
        self.gamification_repo = GamificationRepository()
        self.todo_repo = TodoRepository()

        # Base point values
        self.base_points = {
            TaskSize.SMALL: 1,
            TaskSize.MEDIUM: 3,
            TaskSize.LARGE: 5,
        }

        # Bonus multipliers
        self.streak_multipliers = {
            3: 1.1,   # 10% bonus for 3-day streak
            7: 1.25,  # 25% bonus for 7-day streak
            14: 1.4,  # 40% bonus for 14-day streak
            30: 1.6,  # 60% bonus for 30-day streak
            60: 1.8,  # 80% bonus for 60-day streak
            100: 2.0, # 100% bonus for 100-day streak
        }

        # Daily goal bonus
        self.daily_goal_bonus_rate = 0.5  # 50% bonus for hitting daily goal

        # Level thresholds (points needed for each level)
        self.level_thresholds = [
            0, 100, 250, 500, 1000, 1750, 2750, 4000, 5500, 7500, 10000,
            13000, 16500, 20500, 25000, 30000, 35500, 41500, 48000, 55000,
            # Continues exponentially...
        ]

    def calculate_completion_points(self, todo: Todo) -> Tuple[int, int, int]:
        """
        Calculate points for completing a todo.

        Returns:
            Tuple of (base_points, bonus_points, total_points)
        """
        # Get base points
        base_points = self.base_points.get(todo.final_size, 3)

        # Calculate bonuses
        bonus_points = 0

        # Streak bonus
        current_stats = self.gamification_repo.get_user_stats()
        streak_multiplier = self._get_streak_multiplier(current_stats.current_streak_days)
        if streak_multiplier > 1.0:
            streak_bonus = int(base_points * (streak_multiplier - 1.0))
            bonus_points += streak_bonus

        # Daily goal bonus
        today_activity = self.gamification_repo.get_today_activity()
        daily_goal = current_stats.daily_goal

        # Check if this completion will hit daily goal
        tasks_after_completion = (today_activity.tasks_completed if today_activity else 0) + 1
        if tasks_after_completion >= daily_goal:
            if not today_activity or not today_activity.daily_goal_met:
                # First time hitting goal today - bonus applies to all tasks completed today
                daily_bonus = int(base_points * self.daily_goal_bonus_rate)
                bonus_points += daily_bonus

        # Category bonus (optional - could reward less fun categories)
        if todo.category and todo.category.name in ['Work', 'Finance', 'Health']:
            category_bonus = 1  # Extra point for "less fun" categories
            bonus_points += category_bonus

        # Overdue penalty recovery bonus
        if todo.is_overdue:
            # Small bonus for finally completing overdue tasks
            recovery_bonus = 1
            bonus_points += recovery_bonus

        total_points = base_points + bonus_points
        return base_points, bonus_points, total_points

    def _get_streak_multiplier(self, streak_days: int) -> float:
        """Get streak multiplier based on current streak."""
        multiplier = 1.0
        for threshold, mult in sorted(self.streak_multipliers.items(), reverse=True):
            if streak_days >= threshold:
                multiplier = mult
                break
        return multiplier

    def apply_overdue_penalties(self) -> int:
        """
        Apply penalties for overdue tasks.

        Returns:
            Total penalty points applied
        """
        overdue_todos = self.todo_repo.get_overdue_todos()
        total_penalty = 0

        for todo in overdue_todos:
            days_overdue = (date.today() - todo.due_date).days
            penalty = min(days_overdue, 5)  # Max 5 point penalty per task

            # Apply penalty to user stats
            current_stats = self.gamification_repo.get_user_stats()
            new_total = max(0, current_stats.total_points - penalty)
            self.gamification_repo.update_user_stats({'total_points': new_total})

            # Record penalty in daily activity
            today_activity = self.gamification_repo.get_today_activity()
            if today_activity:
                new_penalty = today_activity.overdue_penalty_applied + penalty
                self.gamification_repo.update_daily_activity(date.today(), {
                    'overdue_penalty_applied': new_penalty
                })

            total_penalty += penalty

        return total_penalty

    def calculate_level(self, total_points: int) -> Tuple[int, int, int]:
        """
        Calculate current level and progress.

        Returns:
            Tuple of (current_level, points_to_next_level, points_for_current_level)
        """
        current_level = 1
        points_for_current_level = 0

        for level, threshold in enumerate(self.level_thresholds, 1):
            if total_points >= threshold:
                current_level = level
                points_for_current_level = threshold
            else:
                break

        # Calculate points needed for next level
        next_level_threshold = self.level_thresholds[current_level] if current_level < len(self.level_thresholds) else float('inf')
        points_to_next_level = next_level_threshold - total_points

        return current_level, points_to_next_level, points_for_current_level

    def update_streak(self, completion_date: date = None) -> int:
        """
        Update user streak based on completion.

        Returns:
            New streak count
        """
        if completion_date is None:
            completion_date = date.today()

        current_stats = self.gamification_repo.get_user_stats()
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

        # Update user stats
        self.gamification_repo.update_user_stats({
            'current_streak_days': new_streak,
            'longest_streak_days': longest_streak,
            'last_completion_date': completion_date
        })

        return new_streak
```

### Achievement System
```python
# src/todo/core/achievements.py
from typing import List, Dict, Any, Optional
from datetime import date, timedelta
from todo.models.gamification import Achievement, UserStats
from todo.db.repositories.gamification import GamificationRepository

class AchievementService:
    """Service for managing achievements and unlocking progress."""

    def __init__(self):
        self.gamification_repo = GamificationRepository()

        # Define all achievements
        self.achievement_definitions = [
            # Task Completion Achievements
            {
                'name': 'First Steps',
                'description': 'Complete your first task',
                'icon': '🎯',
                'requirement_type': 'tasks_completed',
                'requirement_value': 1,
                'bonus_points': 10,
            },
            {
                'name': 'Getting Started',
                'description': 'Complete 10 tasks',
                'icon': '🚀',
                'requirement_type': 'tasks_completed',
                'requirement_value': 10,
                'bonus_points': 25,
            },
            {
                'name': 'Productive',
                'description': 'Complete 50 tasks',
                'icon': '⚡',
                'requirement_type': 'tasks_completed',
                'requirement_value': 50,
                'bonus_points': 50,
            },
            {
                'name': 'Century Club',
                'description': 'Complete 100 tasks',
                'icon': '💯',
                'requirement_type': 'tasks_completed',
                'requirement_value': 100,
                'bonus_points': 100,
            },
            {
                'name': 'Task Master',
                'description': 'Complete 500 tasks',
                'icon': '👑',
                'requirement_type': 'tasks_completed',
                'requirement_value': 500,
                'bonus_points': 250,
            },
            {
                'name': 'Legendary',
                'description': 'Complete 1000 tasks',
                'icon': '🏆',
                'requirement_type': 'tasks_completed',
                'requirement_value': 1000,
                'bonus_points': 500,
            },

            # Streak Achievements
            {
                'name': 'Consistency',
                'description': 'Maintain a 3-day streak',
                'icon': '📅',
                'requirement_type': 'streak_days',
                'requirement_value': 3,
                'bonus_points': 15,
            },
            {
                'name': 'Week Warrior',
                'description': 'Maintain a 7-day streak',
                'icon': '🔥',
                'requirement_type': 'streak_days',
                'requirement_value': 7,
                'bonus_points': 35,
            },
            {
                'name': 'Fortnight Force',
                'description': 'Maintain a 14-day streak',
                'icon': '🌟',
                'requirement_type': 'streak_days',
                'requirement_value': 14,
                'bonus_points': 70,
            },
            {
                'name': 'Month Champion',
                'description': 'Maintain a 30-day streak',
                'icon': '🏆',
                'requirement_type': 'streak_days',
                'requirement_value': 30,
                'bonus_points': 150,
            },
            {
                'name': 'Unstoppable',
                'description': 'Maintain a 100-day streak',
                'icon': '🚀',
                'requirement_type': 'streak_days',
                'requirement_value': 100,
                'bonus_points': 500,
            },

            # Points Achievements
            {
                'name': 'Point Collector',
                'description': 'Earn 100 points',
                'icon': '💎',
                'requirement_type': 'points_earned',
                'requirement_value': 100,
                'bonus_points': 25,
            },
            {
                'name': 'Point Hoarder',
                'description': 'Earn 1000 points',
                'icon': '💍',
                'requirement_type': 'points_earned',
                'requirement_value': 1000,
                'bonus_points': 100,
            },
            {
                'name': 'Point Master',
                'description': 'Earn 5000 points',
                'icon': '👑',
                'requirement_type': 'points_earned',
                'requirement_value': 5000,
                'bonus_points': 500,
            },

            # Daily Goal Achievements
            {
                'name': 'Goal Getter',
                'description': 'Hit your daily goal for the first time',
                'icon': '🎯',
                'requirement_type': 'daily_goals_met',
                'requirement_value': 1,
                'bonus_points': 20,
            },
            {
                'name': 'Consistent Achiever',
                'description': 'Hit daily goal 7 times',
                'icon': '⭐',
                'requirement_type': 'daily_goals_met',
                'requirement_value': 7,
                'bonus_points': 50,
            },
            {
                'name': 'Goal Crusher',
                'description': 'Hit daily goal 30 times',
                'icon': '💪',
                'requirement_type': 'daily_goals_met',
                'requirement_value': 30,
                'bonus_points': 150,
            },

            # Special Achievements
            {
                'name': 'Night Owl',
                'description': 'Complete a task after 10 PM',
                'icon': '🦉',
                'requirement_type': 'special_late_completion',
                'requirement_value': 1,
                'bonus_points': 15,
            },
            {
                'name': 'Early Bird',
                'description': 'Complete a task before 6 AM',
                'icon': '🐦',
                'requirement_type': 'special_early_completion',
                'requirement_value': 1,
                'bonus_points': 15,
            },
            {
                'name': 'Perfectionist',
                'description': 'Complete 10 tasks in a row without any overdue',
                'icon': '✨',
                'requirement_type': 'perfect_streak',
                'requirement_value': 10,
                'bonus_points': 75,
            },
        ]

    def check_and_unlock_achievements(self, user_stats: UserStats) -> List[Achievement]:
        """
        Check for newly unlocked achievements.

        Returns:
            List of newly unlocked achievements
        """
        newly_unlocked = []

        # Get current achievement states
        achievements = self.gamification_repo.get_all_achievements()
        achievements_by_name = {a.name: a for a in achievements}

        for definition in self.achievement_definitions:
            achievement = achievements_by_name.get(definition['name'])

            # Skip if already unlocked
            if achievement and achievement.is_unlocked:
                continue

            # Check if requirement is met
            is_unlocked = self._check_requirement(definition, user_stats)

            if is_unlocked:
                if achievement:
                    # Update existing achievement
                    self.gamification_repo.unlock_achievement(achievement.id)
                    achievement.is_unlocked = True
                    achievement.unlocked_at = datetime.utcnow()
                else:
                    # Create new achievement
                    achievement = Achievement(
                        name=definition['name'],
                        description=definition['description'],
                        icon=definition['icon'],
                        requirement_type=definition['requirement_type'],
                        requirement_value=definition['requirement_value'],
                        bonus_points=definition['bonus_points'],
                        is_unlocked=True,
                        unlocked_at=datetime.utcnow()
                    )
                    achievement = self.gamification_repo.create_achievement(achievement)

                # Award bonus points
                if definition['bonus_points'] > 0:
                    current_points = user_stats.total_points
                    new_points = current_points + definition['bonus_points']
                    self.gamification_repo.update_user_stats({'total_points': new_points})

                newly_unlocked.append(achievement)

        return newly_unlocked

    def _check_requirement(self, definition: Dict[str, Any], user_stats: UserStats) -> bool:
        """Check if achievement requirement is met."""
        requirement_type = definition['requirement_type']
        requirement_value = definition['requirement_value']

        if requirement_type == 'tasks_completed':
            return user_stats.total_tasks_completed >= requirement_value
        elif requirement_type == 'streak_days':
            return user_stats.current_streak_days >= requirement_value
        elif requirement_type == 'points_earned':
            return user_stats.total_points >= requirement_value
        elif requirement_type == 'daily_goals_met':
            # Count days where daily goal was met
            goals_met = self.gamification_repo.count_daily_goals_met()
            return goals_met >= requirement_value
        elif requirement_type in ['special_late_completion', 'special_early_completion', 'perfect_streak']:
            # These would require custom tracking - implement as needed
            return False

        return False

    def get_achievement_progress(self, user_stats: UserStats) -> Dict[str, Dict[str, Any]]:
        """Get progress toward all achievements."""
        progress = {}

        for definition in self.achievement_definitions:
            current_progress = self._get_current_progress(definition, user_stats)
            progress[definition['name']] = {
                'current': current_progress,
                'required': definition['requirement_value'],
                'percentage': min(100, (current_progress / definition['requirement_value']) * 100),
                'completed': current_progress >= definition['requirement_value']
            }

        return progress

    def _get_current_progress(self, definition: Dict[str, Any], user_stats: UserStats) -> int:
        """Get current progress value for an achievement."""
        requirement_type = definition['requirement_type']

        if requirement_type == 'tasks_completed':
            return user_stats.total_tasks_completed
        elif requirement_type == 'streak_days':
            return user_stats.current_streak_days
        elif requirement_type == 'points_earned':
            return user_stats.total_points
        elif requirement_type == 'daily_goals_met':
            return self.gamification_repo.count_daily_goals_met()

        return 0
```

### Goal Management System
```python
# src/todo/core/goals.py
from typing import Dict, Any, Tuple
from datetime import date, datetime, timedelta
from todo.models.gamification import UserStats, DailyActivity
from todo.db.repositories.gamification import GamificationRepository

class GoalService:
    """Service for managing and tracking productivity goals."""

    def __init__(self):
        self.gamification_repo = GamificationRepository()

    def check_daily_goal_completion(self, tasks_completed_today: int) -> Tuple[bool, int]:
        """
        Check if daily goal has been met.

        Returns:
            Tuple of (goal_met, bonus_points_awarded)
        """
        user_stats = self.gamification_repo.get_user_stats()
        daily_goal = user_stats.daily_goal

        goal_met = tasks_completed_today >= daily_goal
        bonus_points = 0

        if goal_met:
            # Check if this is the first time hitting goal today
            today_activity = self.gamification_repo.get_today_activity()
            if not today_activity or not today_activity.daily_goal_met:
                # Award bonus points for hitting daily goal
                bonus_points = self._calculate_daily_goal_bonus(daily_goal)

                # Update daily activity
                updates = {
                    'daily_goal_met': True,
                    'daily_goal_bonus_earned': bonus_points
                }
                self.gamification_repo.update_daily_activity(date.today(), updates)

                # Update user total points
                new_total = user_stats.total_points + bonus_points
                self.gamification_repo.update_user_stats({'total_points': new_total})

        return goal_met, bonus_points

    def check_weekly_goal_progress(self) -> Dict[str, Any]:
        """Check progress toward weekly goal."""
        user_stats = self.gamification_repo.get_user_stats()
        weekly_goal = user_stats.weekly_goal

        # Get week start (Monday)
        today = date.today()
        week_start = today - timedelta(days=today.weekday())

        # Count tasks completed this week
        weekly_activity = self.gamification_repo.get_activity_for_period(week_start, today)
        tasks_this_week = sum(activity.tasks_completed for activity in weekly_activity)

        goal_met = tasks_this_week >= weekly_goal
        percentage = (tasks_this_week / weekly_goal) * 100 if weekly_goal > 0 else 0

        return {
            'goal': weekly_goal,
            'current': tasks_this_week,
            'percentage': min(100, percentage),
            'goal_met': goal_met,
            'days_remaining': 7 - today.weekday(),
            'average_needed_per_day': max(0, (weekly_goal - tasks_this_week) / max(1, 7 - today.weekday()))
        }

    def check_monthly_goal_progress(self) -> Dict[str, Any]:
        """Check progress toward monthly goal."""
        user_stats = self.gamification_repo.get_user_stats()
        monthly_goal = user_stats.monthly_goal

        # Get month boundaries
        today = date.today()
        month_start = today.replace(day=1)

        # Count tasks completed this month
        monthly_activity = self.gamification_repo.get_activity_for_period(month_start, today)
        tasks_this_month = sum(activity.tasks_completed for activity in monthly_activity)

        goal_met = tasks_this_month >= monthly_goal
        percentage = (tasks_this_month / monthly_goal) * 100 if monthly_goal > 0 else 0

        # Calculate days remaining in month
        next_month = month_start.replace(month=month_start.month + 1) if month_start.month < 12 else month_start.replace(year=month_start.year + 1, month=1)
        days_in_month = (next_month - month_start).days
        days_remaining = (next_month - today).days

        return {
            'goal': monthly_goal,
            'current': tasks_this_month,
            'percentage': min(100, percentage),
            'goal_met': goal_met,
            'days_remaining': days_remaining,
            'average_needed_per_day': max(0, (monthly_goal - tasks_this_month) / max(1, days_remaining))
        }

    def _calculate_daily_goal_bonus(self, daily_goal: int) -> int:
        """Calculate bonus points for hitting daily goal."""
        # Base bonus of 2 points per task in goal
        base_bonus = daily_goal * 2

        # Additional bonus for higher goals
        if daily_goal >= 10:
            base_bonus += 10  # High achiever bonus
        elif daily_goal >= 5:
            base_bonus += 5   # Ambitious bonus

        return base_bonus

    def suggest_goal_adjustments(self, user_stats: UserStats) -> Dict[str, int]:
        """Suggest goal adjustments based on recent performance."""
        # Analyze last 30 days of activity
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

        activity = self.gamification_repo.get_activity_for_period(start_date, end_date)

        if not activity:
            return {}

        # Calculate averages
        total_days = len(activity)
        total_tasks = sum(a.tasks_completed for a in activity)
        average_daily = total_tasks / total_days if total_days > 0 else 0

        # Calculate weekly and monthly averages
        average_weekly = average_daily * 7
        average_monthly = average_daily * 30

        suggestions = {}

        # Suggest daily goal adjustment
        current_daily = user_stats.daily_goal
        if average_daily > current_daily * 1.2:
            # User consistently exceeds goal
            suggestions['daily_goal'] = int(average_daily * 1.1)
        elif average_daily < current_daily * 0.8:
            # User struggles to meet goal
            suggestions['daily_goal'] = max(1, int(average_daily * 1.1))

        # Suggest weekly goal adjustment
        current_weekly = user_stats.weekly_goal
        if average_weekly > current_weekly * 1.2:
            suggestions['weekly_goal'] = int(average_weekly * 1.1)
        elif average_weekly < current_weekly * 0.8:
            suggestions['weekly_goal'] = max(7, int(average_weekly * 1.1))

        # Suggest monthly goal adjustment
        current_monthly = user_stats.monthly_goal
        if average_monthly > current_monthly * 1.2:
            suggestions['monthly_goal'] = int(average_monthly * 1.1)
        elif average_monthly < current_monthly * 0.8:
            suggestions['monthly_goal'] = max(30, int(average_monthly * 1.1))

        return suggestions
```

## Analytics and Insights

### Performance Analytics
```python
# src/todo/core/analytics.py
from typing import Dict, List, Any, Tuple
from datetime import date, datetime, timedelta
from collections import defaultdict
import statistics
from todo.db.repositories.todo import TodoRepository
from todo.db.repositories.gamification import GamificationRepository

class AnalyticsService:
    """Service for generating productivity analytics and insights."""

    def __init__(self):
        self.todo_repo = TodoRepository()
        self.gamification_repo = GamificationRepository()

    def generate_productivity_report(self, days: int = 30) -> Dict[str, Any]:
        """Generate comprehensive productivity report."""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        # Get activity data
        activity = self.gamification_repo.get_activity_for_period(start_date, end_date)
        todos = self.todo_repo.get_todos_for_period(start_date, end_date)

        # Basic statistics
        total_tasks = sum(a.tasks_completed for a in activity)
        total_points = sum(a.total_points_earned for a in activity)
        active_days = len([a for a in activity if a.tasks_completed > 0])

        # Calculate averages
        avg_tasks_per_day = total_tasks / days if days > 0 else 0
        avg_tasks_per_active_day = total_tasks / active_days if active_days > 0 else 0
        avg_points_per_day = total_points / days if days > 0 else 0

        # Productivity trends
        task_counts = [a.tasks_completed for a in activity[-7:]]  # Last 7 days
        trend = self._calculate_trend(task_counts)

        # Category breakdown
        category_stats = self._analyze_category_distribution(todos)

        # Time analysis
        completion_times = self._analyze_completion_patterns(todos)

        # Goal achievement
        goal_stats = self._analyze_goal_achievement(activity)

        return {
            'period': {'start': start_date, 'end': end_date, 'days': days},
            'summary': {
                'total_tasks': total_tasks,
                'total_points': total_points,
                'active_days': active_days,
                'avg_tasks_per_day': round(avg_tasks_per_day, 1),
                'avg_tasks_per_active_day': round(avg_tasks_per_active_day, 1),
                'avg_points_per_day': round(avg_points_per_day, 1),
                'productivity_score': self._calculate_productivity_score(activity)
            },
            'trends': {
                'direction': trend,
                'weekly_pattern': self._analyze_weekly_pattern(activity),
                'best_day': self._find_best_day(activity),
                'consistency_score': self._calculate_consistency(activity)
            },
            'categories': category_stats,
            'timing': completion_times,
            'goals': goal_stats,
            'insights': self._generate_insights(activity, todos)
        }

    def _calculate_trend(self, values: List[int]) -> str:
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

        if n * sum_x2 - sum_x ** 2 == 0:
            return "stable"

        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2)

        if slope > 0.1:
            return "improving"
        elif slope < -0.1:
            return "declining"
        else:
            return "stable"

    def _analyze_category_distribution(self, todos: List[Todo]) -> Dict[str, Any]:
        """Analyze task distribution by category."""
        category_counts = defaultdict(int)
        category_points = defaultdict(int)

        for todo in todos:
            if todo.status == 'completed':
                category = todo.category.name if todo.category else 'Uncategorized'
                category_counts[category] += 1
                category_points[category] += todo.total_points_earned or 0

        total_tasks = sum(category_counts.values())

        return {
            'distribution': {
                cat: {
                    'count': count,
                    'percentage': (count / total_tasks) * 100 if total_tasks > 0 else 0,
                    'points': category_points[cat]
                }
                for cat, count in category_counts.items()
            },
            'most_productive_category': max(category_points.items(), key=lambda x: x[1])[0] if category_points else None,
            'most_frequent_category': max(category_counts.items(), key=lambda x: x[1])[0] if category_counts else None
        }

    def _analyze_completion_patterns(self, todos: List[Todo]) -> Dict[str, Any]:
        """Analyze when tasks are typically completed."""
        completed_todos = [t for t in todos if t.completed_at]

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
        weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

        for weekday in weekdays:
            weekday_distribution[weekday_names[weekday]] += 1

        # Find peak hours
        peak_hour = max(hour_distribution.items(), key=lambda x: x[1])[0] if hour_distribution else None
        peak_day = max(weekday_distribution.items(), key=lambda x: x[1])[0] if weekday_distribution else None

        return {
            'peak_hour': peak_hour,
            'peak_day': peak_day,
            'hour_distribution': dict(hour_distribution),
            'weekday_distribution': dict(weekday_distribution),
            'avg_completion_hour': statistics.mean(hours) if hours else None
        }

    def _calculate_productivity_score(self, activity: List[DailyActivity]) -> int:
        """Calculate overall productivity score (0-100)."""
        if not activity:
            return 0

        # Factors: consistency, volume, goal achievement, trend
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
        trend_score = {'improving': 25, 'stable': 15, 'declining': 5}.get(trend, 10)
        scores.append(trend_score)

        return int(sum(scores))

    def _generate_insights(self, activity: List[DailyActivity], todos: List[Todo]) -> List[str]:
        """Generate actionable insights based on data."""
        insights = []

        if not activity:
            return insights

        # Consistency insights
        active_days = len([a for a in activity if a.tasks_completed > 0])
        consistency_rate = active_days / len(activity)

        if consistency_rate < 0.5:
            insights.append("🎯 Try to be more consistent - aim to complete at least one task every day")
        elif consistency_rate > 0.8:
            insights.append("🔥 Great consistency! You're building excellent habits")

        # Productivity insights
        recent_avg = statistics.mean([a.tasks_completed for a in activity[-7:]])
        earlier_avg = statistics.mean([a.tasks_completed for a in activity[:7]]) if len(activity) >= 14 else recent_avg

        if recent_avg > earlier_avg * 1.2:
            insights.append("📈 Your productivity is trending upward - keep up the momentum!")
        elif recent_avg < earlier_avg * 0.8:
            insights.append("📉 Consider reviewing your goals or breaking down tasks into smaller pieces")

        # Goal insights
        goals_met = len([a for a in activity if a.daily_goal_met])
        goal_rate = goals_met / len(activity)

        if goal_rate < 0.3:
            insights.append("🎯 Consider lowering your daily goal to build momentum")
        elif goal_rate > 0.8:
            insights.append("🚀 You're consistently hitting your goals - consider raising them!")

        # Category insights
        completed_todos = [t for t in todos if t.status == 'completed']
        if completed_todos:
            categories = [t.category.name if t.category else 'Uncategorized' for t in completed_todos]
            most_common = max(set(categories), key=categories.count)
            if most_common != 'Uncategorized':
                insights.append(f"💼 You're most productive with '{most_common}' tasks")

        return insights[:5]  # Return top 5 insights
```

## Integration with CLI

### Gamification Display
```python
# Integration in display.py for showing gamification elements
def show_gamification_summary(self) -> None:
    """Show current gamification status in CLI."""
    user_stats = self.gamification_repo.get_user_stats()
    today_activity = self.gamification_repo.get_today_activity()

    # Create gamification panel
    level, points_to_next, _ = self.scoring_service.calculate_level(user_stats.total_points)

    content = f"""
    [bold cyan]Level {level}[/bold cyan] | [yellow]{user_stats.total_points} points[/yellow]
    [dim]{points_to_next} points to next level[/dim]

    🔥 Streak: [bold orange1]{user_stats.current_streak_days} days[/bold orange1]
    📅 Today: [green]{today_activity.tasks_completed if today_activity else 0}/{user_stats.daily_goal}[/green] tasks
    🏆 Achievement: [bold]{user_stats.achievements_unlocked}[/bold] unlocked
    """

    panel = Panel(
        content.strip(),
        title="🎮 Your Progress",
        border_style="cyan",
        expand=False
    )

    self.console.print(panel)
```

## Implementation Steps

### Step 1: Core Scoring System
1. Create `src/todo/core/scoring.py`
2. Implement point calculation with bonuses
3. Add level calculation and streak management
4. Test scoring logic with various scenarios

### Step 2: Achievement System
1. Create `src/todo/core/achievements.py`
2. Define all achievement types and requirements
3. Implement achievement checking and unlocking
4. Test achievement progression

### Step 3: Goal Management
1. Create `src/todo/core/goals.py`
2. Implement daily/weekly/monthly goal tracking
3. Add goal suggestion algorithm
4. Test goal completion detection

### Step 4: Analytics Service
1. Create `src/todo/core/analytics.py`
2. Implement productivity reporting
3. Add trend analysis and insights
4. Test analytics with sample data

### Step 5: CLI Integration
1. Update display manager for gamification
2. Add stats and achievements commands
3. Integrate scoring into todo completion
4. Test complete gamification flow

## Success Criteria
- [ ] Point calculation working correctly with bonuses
- [ ] Streak tracking accurate across day boundaries
- [ ] Achievement unlocking functional and engaging
- [ ] Goal tracking updating properly
- [ ] Analytics providing useful insights
- [ ] CLI displaying gamification elements beautifully
- [ ] System motivating consistent task completion
- [ ] Performance acceptable for daily use

## Balancing Considerations
- Points should feel rewarding but not overwhelming
- Streaks should encourage consistency without causing anxiety
- Achievements should provide long-term motivation
- Goals should adapt to user behavior patterns
- Penalties should discourage procrastination without being punitive
