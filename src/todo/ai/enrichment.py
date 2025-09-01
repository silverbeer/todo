"""Core AI enrichment models and PydanticAI agent configuration."""

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from ..models import Priority, TaskSize


class TodoEnrichmentRequest(BaseModel):
    """Input for todo enrichment."""

    title: str = Field(..., description="The todo title/description")
    user_context: str | None = Field(None, description="Additional context from user")
    similar_tasks: list[str] = Field(
        default_factory=list, description="Previously similar tasks"
    )


class TodoEnrichmentResponse(BaseModel):
    """AI enrichment response model."""

    suggested_category: str = Field(..., description="Suggested category name")
    suggested_priority: Priority = Field(..., description="Task priority level")
    suggested_size: TaskSize = Field(..., description="Task size/complexity")
    estimated_duration_minutes: int = Field(
        ..., ge=5, le=480, description="Estimated time in minutes"
    )

    # Recurrence detection
    is_recurring_candidate: bool = Field(
        False, description="Is this likely a recurring task?"
    )
    suggested_recurrence_pattern: str | None = Field(
        None, description="If recurring, suggested pattern"
    )

    # AI reasoning
    reasoning: str = Field(
        ..., max_length=500, description="Brief explanation of categorization"
    )
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in suggestions"
    )

    # Context analysis
    detected_keywords: list[str] = Field(
        default_factory=list, description="Key terms identified"
    )
    urgency_indicators: list[str] = Field(
        default_factory=list, description="Words suggesting urgency"
    )


# Default system prompt for enrichment
DEFAULT_ENRICHMENT_PROMPT = """
You are an expert task categorization and planning assistant. Your job is to analyze todo items and provide intelligent enrichment.

CATEGORIES: Work, Personal, Home, Health, Learning, Shopping, Finance, or suggest a new category if none fit.

SIZING GUIDELINES:
- Small (1-15 minutes): Quick tasks, simple emails, brief calls
- Medium (15-60 minutes): Regular tasks, meetings, moderate complexity
- Large (60+ minutes): Complex projects, lengthy activities, deep work

PRIORITY GUIDELINES:
- Low: Nice to have, no deadline pressure
- Medium: Important but flexible timing
- High: Important with time sensitivity
- Urgent: Immediate attention required

RECURRENCE DETECTION:
Look for patterns like "weekly", "monthly", routine activities (gym, groceries, bills), or maintenance tasks.

Be practical and realistic in your assessments. Consider context clues in the task description.
"""


def create_enrichment_agent(model_name: str = "openai:gpt-4o-mini") -> Agent:
    """Create the enrichment agent lazily when needed."""
    return Agent(
        model_name,
        output_type=TodoEnrichmentResponse,
        system_prompt=DEFAULT_ENRICHMENT_PROMPT,
    )


# For backward compatibility
todo_enrichment_agent = None  # Will be created when needed
