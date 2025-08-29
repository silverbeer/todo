# Data Models - Implementation Plan

## Overview
This document defines all Pydantic models for the todo application, including core entities, AI enrichment data, gamification elements, and configuration models.

## Core Models

### TodoStatus Enum
```python
from enum import Enum

class TodoStatus(str, Enum):
    """Status of a todo item."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ARCHIVED = "archived"
    OVERDUE = "overdue"  # Computed status
```

### TaskSize Enum
```python
class TaskSize(str, Enum):
    """Size/complexity estimation for tasks."""
    SMALL = "small"    # 1 point
    MEDIUM = "medium"  # 3 points
    LARGE = "large"    # 5 points
```

### Priority Enum
```python
class Priority(str, Enum):
    """Task priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"
```

### Category Model
```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class Category(BaseModel):
    """Todo category with optional color and icon."""
    id: Optional[int] = None
    name: str = Field(..., min_length=1, max_length=50)
    color: Optional[str] = Field(None, regex=r"^#[0-9a-fA-F]{6}$")
    icon: Optional[str] = Field(None, max_length=2)  # Single emoji or character
    description: Optional[str] = Field(None, max_length=200)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True
```

### RecurrenceRule Model
```python
from pydantic import BaseModel, Field, validator
from typing import Optional, Literal
from datetime import datetime, date

class RecurrenceRule(BaseModel):
    """Defines how a task should recur."""
    id: Optional[int] = None
    pattern: Literal["daily", "weekly", "monthly", "yearly", "custom"] = "weekly"
    interval_value: int = Field(default=1, ge=1)  # Every N days/weeks/months
    weekdays: Optional[list[int]] = Field(None, description="0=Monday, 6=Sunday")
    day_of_month: Optional[int] = Field(None, ge=1, le=31)
    end_date: Optional[date] = None
    max_occurrences: Optional[int] = Field(None, ge=1)
    next_due_date: Optional[date] = None
    created_from_ai: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @validator("weekdays")
    def validate_weekdays(cls, v):
        if v is not None:
            if not all(0 <= day <= 6 for day in v):
                raise ValueError("Weekdays must be between 0-6")
        return v

    class Config:
        from_attributes = True
```

### Main Todo Model
```python
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime, date
from uuid import uuid4

class Todo(BaseModel):
    """Core todo item model."""
    id: Optional[int] = None
    uuid: str = Field(default_factory=lambda: str(uuid4()))
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = Field(None, max_length=2000)
    status: TodoStatus = TodoStatus.PENDING

    # Size and priority (can be user override or AI suggested)
    user_override_size: Optional[TaskSize] = None
    ai_suggested_size: Optional[TaskSize] = None
    final_size: TaskSize = TaskSize.MEDIUM  # What's actually used for scoring

    user_override_priority: Optional[Priority] = None
    ai_suggested_priority: Optional[Priority] = None
    final_priority: Priority = Priority.MEDIUM

    # Categorization
    category_id: Optional[int] = None
    category: Optional[Category] = None  # Populated by DB queries

    # Time tracking
    estimated_minutes: Optional[int] = Field(None, ge=1)
    actual_minutes: Optional[int] = Field(None, ge=1)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    due_date: Optional[date] = None

    # Recurrence
    recurrence_rule_id: Optional[int] = None
    recurrence_rule: Optional[RecurrenceRule] = None
    parent_todo_id: Optional[int] = None  # For recurring instances

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
        if self.due_date and self.status not in [TodoStatus.COMPLETED, TodoStatus.ARCHIVED]:
            return date.today() > self.due_date
        return False

    @property
    def effective_size(self) -> TaskSize:
        """Get the effective task size (user override or AI suggestion)."""
        return self.user_override_size or self.ai_suggested_size or TaskSize.MEDIUM

    @property
    def effective_priority(self) -> Priority:
        """Get the effective priority (user override or AI suggestion)."""
        return self.user_override_priority or self.ai_suggested_priority or Priority.MEDIUM

    class Config:
        from_attributes = True
        use_enum_values = True
```

## AI Enrichment Models

### AIProvider Enum
```python
class AIProvider(str, Enum):
    """Supported AI providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
```

### AIEnrichment Model
```python
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

class AIEnrichment(BaseModel):
    """AI-generated enrichment data for a todo."""
    id: Optional[int] = None
    todo_id: int
    provider: AIProvider
    model_name: str = Field(..., description="e.g., gpt-4, claude-3-sonnet")

    # AI suggestions
    suggested_category: Optional[str] = None
    suggested_priority: Optional[Priority] = None
    suggested_size: Optional[TaskSize] = None
    estimated_duration_minutes: Optional[int] = Field(None, ge=1)

    # Recurrence detection
    is_recurring_candidate: bool = False
    suggested_recurrence_pattern: Optional[str] = None

    # AI reasoning and confidence
    reasoning: Optional[str] = Field(None, max_length=1000)
    confidence_score: float = Field(default=0.5, ge=0.0, le=1.0)

    # Context used for enrichment
    context_keywords: List[str] = Field(default_factory=list)
    similar_tasks_found: int = Field(default=0, ge=0)

    # Metadata
    enriched_at: datetime = Field(default_factory=datetime.utcnow)
    processing_time_ms: Optional[int] = Field(None, ge=0)

    class Config:
        from_attributes = True
```

### AILearningFeedback Model
```python
class AILearningFeedback(BaseModel):
    """Track user corrections to improve AI suggestions."""
    id: Optional[int] = None
    original_task_text: str
    ai_provider: AIProvider

    # Original AI suggestions
    ai_suggested_category: Optional[str] = None
    ai_suggested_size: Optional[TaskSize] = None
    ai_suggested_priority: Optional[Priority] = None

    # User corrections
    user_corrected_category: Optional[str] = None
    user_corrected_size: Optional[TaskSize] = None
    user_corrected_priority: Optional[Priority] = None

    # Learning context
    task_keywords: List[str] = Field(default_factory=list)
    correction_type: str  # "size_increase", "size_decrease", "category_change", etc.

    feedback_timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True
```

## Gamification Models

### UserStats Model
```python
class UserStats(BaseModel):
    """Overall user statistics and gamification data."""
    id: Optional[int] = None

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
    last_completion_date: Optional[date] = None

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
```

### DailyActivity Model
```python
class DailyActivity(BaseModel):
    """Daily activity tracking for gamification."""
    id: Optional[int] = None
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
```

### Achievement Model
```python
class Achievement(BaseModel):
    """Achievement definitions and user progress."""
    id: Optional[int] = None
    name: str = Field(..., max_length=100)
    description: str = Field(..., max_length=500)
    icon: Optional[str] = Field(None, max_length=2)  # Emoji

    # Requirements
    requirement_type: str  # "tasks_completed", "streak_days", "points_earned"
    requirement_value: int = Field(..., ge=1)
    bonus_points: int = Field(default=0, ge=0)

    # User progress
    is_unlocked: bool = False
    progress_current: int = Field(default=0, ge=0)
    unlocked_at: Optional[datetime] = None

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True
```

## Configuration Models

### AIConfig Model
```python
class AIConfig(BaseModel):
    """AI provider configuration."""
    default_provider: AIProvider = AIProvider.OPENAI
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None

    # Model preferences
    openai_model: str = "gpt-4o-mini"
    anthropic_model: str = "claude-3-haiku-20240307"

    # Enrichment settings
    enable_auto_enrichment: bool = True
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    max_retries: int = Field(default=3, ge=1, le=10)
    timeout_seconds: int = Field(default=30, ge=5, le=120)
```

### AppConfig Model
```python
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
```

## Response Models for CLI

### TodoListResponse Model
```python
class TodoListResponse(BaseModel):
    """Response model for todo list commands."""
    todos: List[Todo]
    total_count: int
    filtered_count: int
    has_overdue: bool
    current_streak: int
    points_today: int

    class Config:
        from_attributes = True
```

### StatsResponse Model
```python
class StatsResponse(BaseModel):
    """Response model for statistics display."""
    user_stats: UserStats
    today_activity: DailyActivity
    recent_achievements: List[Achievement]

    class Config:
        from_attributes = True
```

## Implementation Steps

### Step 1: Create Base Models
1. Create `src/todo/models/__init__.py`
2. Create `src/todo/models/base.py` with common base classes
3. Create `src/todo/models/enums.py` with all enum definitions

### Step 2: Implement Core Models
1. Create `src/todo/models/todo.py` with Todo and Category models
2. Create `src/todo/models/recurrence.py` with RecurrenceRule model
3. Add comprehensive validation and property methods

### Step 3: Add AI Models
1. Create `src/todo/models/ai.py` with enrichment and learning models
2. Implement confidence scoring and feedback tracking
3. Add provider abstraction models

### Step 4: Implement Gamification
1. Create `src/todo/models/gamification.py` with stats and achievement models
2. Add point calculation methods
3. Implement streak and goal tracking logic

### Step 5: Configuration Models
1. Create `src/todo/models/config.py` with configuration models
2. Add environment variable integration
3. Implement configuration validation

### Step 6: Testing
1. Write comprehensive unit tests for all models
2. Test validation logic and edge cases
3. Test serialization/deserialization
4. Test computed properties and methods

## Success Criteria
- [ ] All models defined with proper typing and validation
- [ ] Comprehensive test coverage (>95%)
- [ ] No mypy type checking errors
- [ ] Proper enum usage throughout
- [ ] Computed properties working correctly
- [ ] Configuration models loading from environment
- [ ] All model relationships properly defined
- [ ] Serialization/deserialization working for all models
