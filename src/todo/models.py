"""Pydantic models for the todo application."""

from datetime import date, datetime
from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, validator


class TodoStatus(str, Enum):
    """Status of a todo item."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ARCHIVED = "archived"
    OVERDUE = "overdue"  # Computed status


class TaskSize(str, Enum):
    """Size/complexity estimation for tasks."""

    SMALL = "small"  # 1 point
    MEDIUM = "medium"  # 3 points
    LARGE = "large"  # 5 points


class Priority(str, Enum):
    """Task priority levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class AIProvider(str, Enum):
    """Supported AI providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class Category(BaseModel):
    """Todo category with optional color and icon."""

    id: int | None = None
    name: str = Field(..., min_length=1, max_length=50)
    color: str | None = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    icon: str | None = Field(None, max_length=2)  # Single emoji or character
    description: str | None = Field(None, max_length=200)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class RecurrenceRule(BaseModel):
    """Defines how a task should recur."""

    id: int | None = None
    pattern: Literal["daily", "weekly", "monthly", "yearly", "custom"] = "weekly"
    interval_value: int = Field(default=1, ge=1)  # Every N days/weeks/months
    weekdays: list[int] | None = Field(None, description="0=Monday, 6=Sunday")
    day_of_month: int | None = Field(None, ge=1, le=31)
    end_date: date | None = None
    max_occurrences: int | None = Field(None, ge=1)
    next_due_date: date | None = None
    created_from_ai: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @validator("weekdays")
    def validate_weekdays(cls, v: list[int] | None) -> list[int] | None:
        """Validate weekday values are between 0-6."""
        if v is not None and not all(0 <= day <= 6 for day in v):
            raise ValueError("Weekdays must be between 0-6")
        return v

    class Config:
        from_attributes = True


class Todo(BaseModel):
    """Core todo item model."""

    id: int | None = None
    uuid: str = Field(default_factory=lambda: str(uuid4()))
    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = Field(None, max_length=2000)
    status: TodoStatus = TodoStatus.PENDING

    # Size and priority (can be user override or AI suggested)
    user_override_size: TaskSize | None = None
    ai_suggested_size: TaskSize | None = None
    final_size: TaskSize = TaskSize.MEDIUM  # What's actually used for scoring

    user_override_priority: Priority | None = None
    ai_suggested_priority: Priority | None = None
    final_priority: Priority = Priority.MEDIUM

    # Categorization
    category_id: int | None = None
    category: Category | None = None  # Populated by DB queries

    # Time tracking
    estimated_minutes: int | None = Field(None, ge=1)
    actual_minutes: int | None = Field(None, ge=1)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    due_date: date | None = None

    # Recurrence
    recurrence_rule_id: int | None = None
    recurrence_rule: RecurrenceRule | None = None
    parent_todo_id: int | None = None  # For recurring instances

    # Gamification
    base_points: int = Field(default=0, ge=0)
    bonus_points: int = Field(default=0, ge=0)
    total_points_earned: int = Field(default=0, ge=0)

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Computed properties
    @property
    def is_overdue(self) -> bool:
        """Check if task is overdue."""
        if self.due_date and self.status not in [
            TodoStatus.COMPLETED,
            TodoStatus.ARCHIVED,
        ]:
            return date.today() > self.due_date
        return False

    @property
    def effective_size(self) -> TaskSize:
        """Get the effective task size (user override or AI suggestion)."""
        return self.user_override_size or self.ai_suggested_size or TaskSize.MEDIUM

    @property
    def effective_priority(self) -> Priority:
        """Get the effective priority (user override or AI suggestion)."""
        return (
            self.user_override_priority or self.ai_suggested_priority or Priority.MEDIUM
        )

    class Config:
        from_attributes = True
        use_enum_values = True


class AIEnrichment(BaseModel):
    """AI-generated enrichment data for a todo."""

    id: int | None = None
    todo_id: int
    provider: AIProvider
    model_name: str = Field(..., description="e.g., gpt-4, claude-3-sonnet")

    # AI suggestions
    suggested_category: str | None = None
    suggested_priority: Priority | None = None
    suggested_size: TaskSize | None = None
    estimated_duration_minutes: int | None = Field(None, ge=1)

    # Recurrence detection
    is_recurring_candidate: bool = False
    suggested_recurrence_pattern: str | None = None

    # AI reasoning and confidence
    reasoning: str | None = Field(None, max_length=1000)
    confidence_score: float = Field(default=0.5, ge=0.0, le=1.0)

    # Context used for enrichment
    context_keywords: list[str] = Field(default_factory=list)
    similar_tasks_found: int = Field(default=0, ge=0)

    # Metadata
    enriched_at: datetime = Field(default_factory=datetime.utcnow)
    processing_time_ms: int | None = Field(None, ge=0)

    class Config:
        from_attributes = True


class AILearningFeedback(BaseModel):
    """Track user corrections to improve AI suggestions."""

    id: int | None = None
    original_task_text: str
    ai_provider: AIProvider

    # Original AI suggestions
    ai_suggested_category: str | None = None
    ai_suggested_size: TaskSize | None = None
    ai_suggested_priority: Priority | None = None

    # User corrections
    user_corrected_category: str | None = None
    user_corrected_size: TaskSize | None = None
    user_corrected_priority: Priority | None = None

    # Learning context
    task_keywords: list[str] = Field(default_factory=list)
    correction_type: str  # "size_increase", "size_decrease", "category_change", etc.

    feedback_timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class UserStats(BaseModel):
    """Overall user statistics and gamification data."""

    id: int | None = None

    # Point tracking
    total_points: int = Field(default=0, ge=0)
    level: int = Field(default=1, ge=1)
    points_to_next_level: int = Field(default=100, ge=0)

    # Task completion
    total_tasks_completed: int = Field(default=0, ge=0)
    total_tasks_created: int = Field(default=0, ge=0)

    # Streak tracking
    current_streak_days: int = Field(default=0, ge=0)
    longest_streak_days: int = Field(default=0, ge=0)
    last_completion_date: date | None = None

    # Goals
    daily_goal: int = Field(default=3, ge=1)
    weekly_goal: int = Field(default=20, ge=1)
    monthly_goal: int = Field(default=80, ge=1)

    # Achievements
    achievements_unlocked: int = Field(default=0, ge=0)

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class DailyActivity(BaseModel):
    """Daily activity tracking for gamification."""

    id: int | None = None
    activity_date: date = Field(default_factory=date.today)

    # Task completion
    tasks_completed: int = Field(default=0, ge=0)
    tasks_created: int = Field(default=0, ge=0)

    # Points breakdown
    base_points_earned: int = Field(default=0, ge=0)
    streak_bonus_earned: int = Field(default=0, ge=0)
    daily_goal_bonus_earned: int = Field(default=0, ge=0)
    total_points_earned: int = Field(default=0, ge=0)

    # Goal achievement
    daily_goal_met: bool = False
    streak_active: bool = False

    # Penalties
    overdue_penalty_applied: int = Field(default=0, ge=0)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class Achievement(BaseModel):
    """Achievement definitions and user progress."""

    id: int | None = None
    name: str = Field(..., max_length=100)
    description: str = Field(..., max_length=500)
    icon: str | None = Field(None, max_length=2)  # Emoji

    # Requirements
    requirement_type: str  # "tasks_completed", "streak_days", "points_earned"
    requirement_value: int = Field(..., ge=1)
    bonus_points: int = Field(default=0, ge=0)

    # User progress
    is_unlocked: bool = False
    progress_current: int = Field(default=0, ge=0)
    unlocked_at: datetime | None = None

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class AIConfig(BaseModel):
    """AI provider configuration."""

    default_provider: AIProvider = AIProvider.OPENAI
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    # Model preferences
    openai_model: str = "gpt-4o-mini"
    anthropic_model: str = "claude-3-haiku-20240307"

    # Enrichment settings
    enable_auto_enrichment: bool = True
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    max_retries: int = Field(default=3, ge=1, le=10)
    timeout_seconds: int = Field(default=30, ge=5, le=120)


class AppConfig(BaseModel):
    """Application configuration."""

    # Database
    database_path: str = "~/.local/share/todo/todos.db"

    # AI settings
    ai: AIConfig = Field(default_factory=AIConfig)

    # Gamification
    enable_gamification: bool = True
    daily_goal: int = Field(default=3, ge=1)
    weekly_goal: int = Field(default=20, ge=1)
    monthly_goal: int = Field(default=80, ge=1)

    # Display preferences
    default_list_limit: int = Field(default=20, ge=1, le=100)
    show_points: bool = True
    show_streaks: bool = True
    use_colors: bool = True

    # Time tracking
    enable_time_tracking: bool = False
    auto_start_timer: bool = False

    class Config:
        env_prefix = "TODO_"


class TodoListResponse(BaseModel):
    """Response model for todo list commands."""

    todos: list[Todo]
    total_count: int
    filtered_count: int
    has_overdue: bool
    current_streak: int
    points_today: int

    class Config:
        from_attributes = True


class StatsResponse(BaseModel):
    """Response model for statistics display."""

    user_stats: UserStats
    today_activity: DailyActivity
    recent_achievements: list[Achievement]

    class Config:
        from_attributes = True
