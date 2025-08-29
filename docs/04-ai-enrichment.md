# AI Enrichment - Implementation Plan

> **⚠️ IMPORTANT**: Review this document before implementation. As we develop the application, requirements may change and this documentation should be updated to reflect any modifications to the AI enrichment system.

## Overview
This document outlines the AI enrichment system using PydanticAI to automatically categorize, size, and enhance todo items with minimal user input. The system supports multiple LLM providers (OpenAI and Claude) with intelligent fallback and learning capabilities.

## Core AI Enrichment System

### PydanticAI Agent Configuration
```python
# src/todo/ai/enrichment.py
from pydantic_ai import Agent, RunContext
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime
from todo.models.todo import TaskSize, Priority
from todo.models.ai import AIProvider

class TodoEnrichmentRequest(BaseModel):
    """Input for todo enrichment."""
    title: str = Field(..., description="The todo title/description")
    user_context: Optional[str] = Field(None, description="Additional context from user")
    similar_tasks: List[str] = Field(default_factory=list, description="Previously similar tasks")

class TodoEnrichmentResponse(BaseModel):
    """AI enrichment response model."""
    suggested_category: str = Field(..., description="Suggested category name")
    suggested_priority: Priority = Field(..., description="Task priority level")
    suggested_size: TaskSize = Field(..., description="Task size/complexity")
    estimated_duration_minutes: int = Field(..., ge=5, le=480, description="Estimated time in minutes")

    # Recurrence detection
    is_recurring_candidate: bool = Field(False, description="Is this likely a recurring task?")
    suggested_recurrence_pattern: Optional[str] = Field(None, description="If recurring, suggested pattern")

    # AI reasoning
    reasoning: str = Field(..., max_length=500, description="Brief explanation of categorization")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence in suggestions")

    # Context analysis
    detected_keywords: List[str] = Field(default_factory=list, description="Key terms identified")
    urgency_indicators: List[str] = Field(default_factory=list, description="Words suggesting urgency")

# Create the enrichment agent
todo_enrichment_agent = Agent(
    'openai:gpt-4o-mini',  # Default model
    result_type=TodoEnrichmentResponse,
    system_prompt="""
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
    """,
)
```

### AI Provider Management
```python
# src/todo/ai/providers.py
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import asyncio
from pydantic_ai import Agent
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
from todo.core.config import get_app_config
from todo.models.ai import AIProvider

class BaseLLMProvider(ABC):
    """Base class for LLM providers."""

    def __init__(self, api_key: str, model_name: str):
        self.api_key = api_key
        self.model_name = model_name

    @abstractmethod
    async def create_agent(self, system_prompt: str, result_type: type) -> Agent:
        """Create a PydanticAI agent for this provider."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is available."""
        pass

class OpenAIProvider(BaseLLMProvider):
    """OpenAI provider implementation."""

    def __init__(self, api_key: str, model_name: str = "gpt-4o-mini"):
        super().__init__(api_key, model_name)
        self.client = AsyncOpenAI(api_key=api_key)

    async def create_agent(self, system_prompt: str, result_type: type) -> Agent:
        """Create OpenAI agent."""
        return Agent(
            f'openai:{self.model_name}',
            result_type=result_type,
            system_prompt=system_prompt,
        )

    async def health_check(self) -> bool:
        """Check OpenAI API availability."""
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1
            )
            return True
        except Exception:
            return False

class AnthropicProvider(BaseLLMProvider):
    """Anthropic (Claude) provider implementation."""

    def __init__(self, api_key: str, model_name: str = "claude-3-haiku-20240307"):
        super().__init__(api_key, model_name)
        self.client = AsyncAnthropic(api_key=api_key)

    async def create_agent(self, system_prompt: str, result_type: type) -> Agent:
        """Create Anthropic agent."""
        return Agent(
            f'anthropic:{self.model_name}',
            result_type=result_type,
            system_prompt=system_prompt,
        )

    async def health_check(self) -> bool:
        """Check Anthropic API availability."""
        try:
            response = await self.client.messages.create(
                model=self.model_name,
                max_tokens=1,
                messages=[{"role": "user", "content": "test"}]
            )
            return True
        except Exception:
            return False

class ProviderManager:
    """Manages multiple AI providers with fallback."""

    def __init__(self):
        self.config = get_app_config()
        self.providers: Dict[AIProvider, BaseLLMProvider] = {}
        self._initialize_providers()

    def _initialize_providers(self):
        """Initialize available providers."""
        if self.config.ai.openai_api_key:
            self.providers[AIProvider.OPENAI] = OpenAIProvider(
                self.config.ai.openai_api_key,
                self.config.ai.openai_model
            )

        if self.config.ai.anthropic_api_key:
            self.providers[AIProvider.ANTHROPIC] = AnthropicProvider(
                self.config.ai.anthropic_api_key,
                self.config.ai.anthropic_model
            )

    async def get_available_provider(self, preferred: Optional[AIProvider] = None) -> Optional[BaseLLMProvider]:
        """Get available provider with fallback logic."""
        # Try preferred provider first
        if preferred and preferred in self.providers:
            provider = self.providers[preferred]
            if await provider.health_check():
                return provider

        # Try default provider
        default = self.providers.get(self.config.ai.default_provider)
        if default and await default.health_check():
            return default

        # Try any available provider
        for provider in self.providers.values():
            if await provider.health_check():
                return provider

        return None
```

### Main Enrichment Service
```python
# src/todo/ai/enrichment_service.py
import asyncio
from typing import Optional, List
from datetime import datetime
from todo.ai.providers import ProviderManager
from todo.ai.enrichment import TodoEnrichmentRequest, TodoEnrichmentResponse, todo_enrichment_agent
from todo.ai.learning import LearningService
from todo.models.ai import AIEnrichment, AIProvider
from todo.db.repositories.ai import AIEnrichmentRepository
from todo.core.config import get_app_config

class EnrichmentService:
    """Main service for AI todo enrichment."""

    def __init__(self):
        self.config = get_app_config()
        self.provider_manager = ProviderManager()
        self.learning_service = LearningService()
        self.ai_repo = AIEnrichmentRepository()

    async def enrich_todo(self,
                         title: str,
                         description: Optional[str] = None,
                         user_context: Optional[str] = None,
                         preferred_provider: Optional[AIProvider] = None) -> Optional[AIEnrichment]:
        """
        Enrich a todo item with AI analysis.

        Args:
            title: Todo title
            description: Optional description
            user_context: Additional context
            preferred_provider: Preferred AI provider

        Returns:
            AIEnrichment object or None if enrichment fails
        """
        if not self.config.ai.enable_auto_enrichment:
            return None

        # Get available provider
        provider = await self.provider_manager.get_available_provider(preferred_provider)
        if not provider:
            print("Warning: No AI providers available for enrichment")
            return None

        # Prepare enrichment request
        full_text = f"{title}"
        if description:
            full_text += f" - {description}"

        # Get similar tasks for context
        similar_tasks = await self._get_similar_tasks(title)

        request = TodoEnrichmentRequest(
            title=full_text,
            user_context=user_context,
            similar_tasks=similar_tasks
        )

        # Apply learning context
        enhanced_prompt = await self.learning_service.enhance_prompt_with_learning(
            todo_enrichment_agent.system_prompt, title, provider.model_name
        )

        try:
            # Create agent with enhanced prompt
            agent = await provider.create_agent(enhanced_prompt, TodoEnrichmentResponse)

            # Get enrichment
            start_time = datetime.utcnow()
            result = await agent.run(request.model_dump_json())
            processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            # Create enrichment record
            enrichment = AIEnrichment(
                todo_id=0,  # Will be set by caller
                provider=AIProvider.OPENAI if "openai" in provider.model_name else AIProvider.ANTHROPIC,
                model_name=provider.model_name,
                suggested_category=result.data.suggested_category,
                suggested_priority=result.data.suggested_priority,
                suggested_size=result.data.suggested_size,
                estimated_duration_minutes=result.data.estimated_duration_minutes,
                is_recurring_candidate=result.data.is_recurring_candidate,
                suggested_recurrence_pattern=result.data.suggested_recurrence_pattern,
                reasoning=result.data.reasoning,
                confidence_score=result.data.confidence_score,
                context_keywords=result.data.detected_keywords,
                similar_tasks_found=len(similar_tasks),
                processing_time_ms=processing_time
            )

            return enrichment

        except Exception as e:
            print(f"Enrichment failed: {e}")
            # Try fallback provider if available
            if preferred_provider:
                return await self.enrich_todo(title, description, user_context, None)
            return None

    async def _get_similar_tasks(self, title: str, limit: int = 5) -> List[str]:
        """Find similar tasks for context."""
        # Simple keyword-based similarity for now
        # Could be enhanced with embeddings later
        from todo.db.repositories.todo import TodoRepository

        todo_repo = TodoRepository()
        keywords = title.lower().split()

        similar = []
        for keyword in keywords[:3]:  # Top 3 keywords
            if len(keyword) > 3:  # Skip short words
                todos = todo_repo.search_by_title(keyword, limit=3)
                similar.extend([t.title for t in todos])

        return similar[:limit]

    def should_enrich(self, confidence_threshold: Optional[float] = None) -> bool:
        """Check if enrichment should be performed."""
        threshold = confidence_threshold or self.config.ai.confidence_threshold
        return self.config.ai.enable_auto_enrichment
```

### AI Learning System
```python
# src/todo/ai/learning.py
from typing import List, Dict, Optional
from todo.models.ai import AILearningFeedback, AIProvider
from todo.models.todo import TaskSize, Priority
from todo.db.repositories.ai import AILearningFeedbackRepository

class LearningService:
    """Service for AI learning from user feedback."""

    def __init__(self):
        self.feedback_repo = AILearningFeedbackRepository()

    async def record_user_override(self,
                                 original_task: str,
                                 ai_provider: AIProvider,
                                 ai_suggestions: Dict,
                                 user_corrections: Dict) -> None:
        """Record user corrections for learning."""

        # Determine correction types
        correction_types = []

        if 'size' in user_corrections and user_corrections['size'] != ai_suggestions.get('size'):
            if self._size_to_int(user_corrections['size']) > self._size_to_int(ai_suggestions['size']):
                correction_types.append('size_increase')
            else:
                correction_types.append('size_decrease')

        if 'category' in user_corrections and user_corrections['category'] != ai_suggestions.get('category'):
            correction_types.append('category_change')

        if 'priority' in user_corrections and user_corrections['priority'] != ai_suggestions.get('priority'):
            correction_types.append('priority_change')

        # Extract keywords for learning
        keywords = self._extract_keywords(original_task)

        # Record feedback for each correction type
        for correction_type in correction_types:
            feedback = AILearningFeedback(
                original_task_text=original_task,
                ai_provider=ai_provider,
                ai_suggested_category=ai_suggestions.get('category'),
                ai_suggested_size=ai_suggestions.get('size'),
                ai_suggested_priority=ai_suggestions.get('priority'),
                user_corrected_category=user_corrections.get('category'),
                user_corrected_size=user_corrections.get('size'),
                user_corrected_priority=user_corrections.get('priority'),
                task_keywords=keywords,
                correction_type=correction_type
            )

            await self.feedback_repo.create(feedback)

    async def enhance_prompt_with_learning(self,
                                         base_prompt: str,
                                         task_text: str,
                                         model_name: str) -> str:
        """Enhance system prompt with learning from past corrections."""

        keywords = self._extract_keywords(task_text)
        learning_context = await self._get_learning_context(keywords, model_name)

        if not learning_context:
            return base_prompt

        enhanced_prompt = base_prompt + "\n\nLEARNING CONTEXT:\n"
        enhanced_prompt += "Based on past user corrections, please consider these patterns:\n"

        for pattern in learning_context:
            enhanced_prompt += f"- {pattern}\n"

        return enhanced_prompt

    async def _get_learning_context(self, keywords: List[str], model_name: str) -> List[str]:
        """Get relevant learning patterns for the current task."""

        patterns = []

        # Get recent feedback for similar keywords
        for keyword in keywords[:3]:  # Top 3 keywords
            feedback_items = await self.feedback_repo.get_by_keyword(keyword, limit=5)

            for feedback in feedback_items:
                if feedback.correction_type == 'size_increase':
                    patterns.append(f"Tasks with '{keyword}' are often larger than initially estimated")
                elif feedback.correction_type == 'size_decrease':
                    patterns.append(f"Tasks with '{keyword}' are often smaller than initially estimated")
                elif feedback.correction_type == 'category_change':
                    if feedback.user_corrected_category:
                        patterns.append(f"Tasks with '{keyword}' are often categorized as '{feedback.user_corrected_category}'")

        return list(set(patterns))  # Remove duplicates

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract meaningful keywords from task text."""
        import re

        # Simple keyword extraction
        words = re.findall(r'\b\w{3,}\b', text.lower())  # Words 3+ characters

        # Remove common stop words
        stop_words = {'the', 'and', 'for', 'with', 'from', 'that', 'this', 'have', 'are', 'was', 'will', 'can'}
        keywords = [word for word in words if word not in stop_words]

        return keywords[:10]  # Top 10 keywords

    def _size_to_int(self, size: TaskSize) -> int:
        """Convert task size to integer for comparison."""
        size_map = {
            TaskSize.SMALL: 1,
            TaskSize.MEDIUM: 2,
            TaskSize.LARGE: 3
        }
        return size_map.get(size, 2)
```

### Background Enrichment
```python
# src/todo/ai/background.py
import asyncio
from typing import Optional
from todo.ai.enrichment_service import EnrichmentService
from todo.db.repositories.todo import TodoRepository
from todo.db.repositories.ai import AIEnrichmentRepository

class BackgroundEnrichmentService:
    """Handle background AI enrichment to keep UI responsive."""

    def __init__(self):
        self.enrichment_service = EnrichmentService()
        self.todo_repo = TodoRepository()
        self.ai_repo = AIEnrichmentRepository()
        self._running_tasks = set()

    def enrich_todo_background(self, todo_id: int) -> None:
        """Start background enrichment for a todo (non-blocking)."""
        task = asyncio.create_task(self._enrich_todo_async(todo_id))
        self._running_tasks.add(task)
        task.add_done_callback(self._running_tasks.discard)

    async def _enrich_todo_async(self, todo_id: int) -> None:
        """Perform actual background enrichment."""
        try:
            # Get todo
            todo = self.todo_repo.get_by_id(todo_id)
            if not todo:
                return

            # Skip if already enriched
            existing_enrichment = self.ai_repo.get_by_todo_id(todo_id)
            if existing_enrichment:
                return

            # Perform enrichment
            enrichment = await self.enrichment_service.enrich_todo(
                title=todo.title,
                description=todo.description
            )

            if enrichment:
                # Save enrichment
                enrichment.todo_id = todo_id
                saved_enrichment = self.ai_repo.create(enrichment)

                # Apply suggestions to todo if confidence is high
                if enrichment.confidence_score >= 0.8:
                    await self._apply_high_confidence_suggestions(todo, enrichment)

        except Exception as e:
            print(f"Background enrichment failed for todo {todo_id}: {e}")

    async def _apply_high_confidence_suggestions(self, todo, enrichment) -> None:
        """Apply high-confidence AI suggestions automatically."""
        updates = {}

        # Only apply if user hasn't set preferences
        if not todo.user_override_size and not todo.ai_suggested_size:
            updates['ai_suggested_size'] = enrichment.suggested_size
            updates['final_size'] = enrichment.suggested_size

        if not todo.user_override_priority and not todo.ai_suggested_priority:
            updates['ai_suggested_priority'] = enrichment.suggested_priority
            updates['final_priority'] = enrichment.suggested_priority

        # Apply category if we can find matching category
        if enrichment.suggested_category and not todo.category_id:
            from todo.db.repositories.category import CategoryRepository
            category_repo = CategoryRepository()
            category = category_repo.get_by_name(enrichment.suggested_category)
            if category:
                updates['category_id'] = category.id

        if updates:
            self.todo_repo.update(todo.id, updates)
```

## Integration Points

### CLI Integration
```python
# Integration with CLI commands
async def create_todo_with_enrichment(title: str,
                                    description: Optional[str] = None,
                                    skip_ai: bool = False) -> Todo:
    """Create todo with optional AI enrichment."""

    # Create basic todo first
    todo = todo_repo.create_todo(title, description)

    # Start background enrichment unless skipped
    if not skip_ai:
        background_service.enrich_todo_background(todo.id)

    return todo
```

### User Override Handling
```python
# Handle user size/priority overrides
async def update_todo_with_override(todo_id: int,
                                  size: Optional[TaskSize] = None,
                                  priority: Optional[Priority] = None,
                                  category: Optional[str] = None) -> None:
    """Update todo with user overrides and record for learning."""

    todo = todo_repo.get_by_id(todo_id)
    enrichment = ai_repo.get_by_todo_id(todo_id)

    if enrichment and (size or priority or category):
        # Record learning feedback
        ai_suggestions = {
            'size': enrichment.suggested_size,
            'priority': enrichment.suggested_priority,
            'category': enrichment.suggested_category
        }

        user_corrections = {}
        if size: user_corrections['size'] = size
        if priority: user_corrections['priority'] = priority
        if category: user_corrections['category'] = category

        await learning_service.record_user_override(
            todo.title, enrichment.provider, ai_suggestions, user_corrections
        )

    # Apply updates
    updates = {}
    if size:
        updates['user_override_size'] = size
        updates['final_size'] = size
    if priority:
        updates['user_override_priority'] = priority
        updates['final_priority'] = priority

    todo_repo.update(todo_id, updates)
```

## Implementation Steps

### Step 1: Core Enrichment Setup
1. Create `src/todo/ai/__init__.py`
2. Implement base PydanticAI agent configuration
3. Create enrichment request/response models
4. Test basic enrichment functionality

### Step 2: Provider Management
1. Implement provider abstraction layer
2. Add OpenAI and Anthropic provider classes
3. Create provider manager with fallback logic
4. Test provider switching and health checks

### Step 3: Main Enrichment Service
1. Implement main enrichment service
2. Add similarity matching for context
3. Create background processing system
4. Test end-to-end enrichment flow

### Step 4: Learning System
1. Implement feedback recording
2. Create prompt enhancement from learning
3. Add keyword extraction and pattern matching
4. Test learning improvement over time

### Step 5: Integration
1. Integrate with CLI commands
2. Add user override handling
3. Implement confidence-based auto-application
4. Test complete workflow

## Success Criteria
- [ ] AI enrichment working with both OpenAI and Claude
- [ ] Provider fallback functioning correctly
- [ ] Background processing keeps UI responsive
- [ ] Learning system improves suggestions over time
- [ ] User overrides properly recorded and applied
- [ ] High confidence suggestions auto-applied
- [ ] Error handling robust for API failures
- [ ] Performance acceptable for typical use cases

## Configuration Requirements
- API keys for OpenAI and/or Anthropic
- Model selection preferences
- Confidence thresholds
- Enable/disable auto-enrichment
- Timeout and retry settings

## Future Enhancements
- Embedding-based similarity matching
- Custom category creation suggestions
- Time-based pattern recognition
- Multi-language support
- Batch enrichment for existing todos
