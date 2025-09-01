"""Main service for AI todo enrichment."""

from datetime import datetime

from ..core.config import get_app_config
from ..db.connection import DatabaseConnection
from ..db.repository import AIEnrichmentRepository
from ..models import AIEnrichment, AIProvider
from .enrichment import (
    DEFAULT_ENRICHMENT_PROMPT,
    TodoEnrichmentRequest,
    TodoEnrichmentResponse,
)
from .learning import LearningService
from .providers import ProviderManager


class EnrichmentService:
    """Main service for AI todo enrichment."""

    def __init__(self, db_connection: DatabaseConnection | None = None):
        self.config = get_app_config()
        self.provider_manager = ProviderManager()
        self.learning_service = LearningService(db_connection)

        if db_connection:
            self.ai_repo = AIEnrichmentRepository(db_connection)
        else:
            # Use default connection
            default_db = DatabaseConnection(self.config.database.database_path)
            self.ai_repo = AIEnrichmentRepository(default_db)

    async def enrich_todo(
        self,
        title: str,
        description: str | None = None,
        user_context: str | None = None,
        preferred_provider: AIProvider | None = None,
    ) -> AIEnrichment | None:
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
        provider = await self.provider_manager.get_available_provider(
            preferred_provider
        )
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
            title=full_text, user_context=user_context, similar_tasks=similar_tasks
        )

        # Apply learning context
        enhanced_prompt = await self.learning_service.enhance_prompt_with_learning(
            DEFAULT_ENRICHMENT_PROMPT, title, provider.model_name
        )

        try:
            # Create agent with enhanced prompt
            agent = await provider.create_agent(enhanced_prompt, TodoEnrichmentResponse)

            # Get enrichment
            start_time = datetime.utcnow()
            result = await agent.run(request.model_dump_json())
            processing_time = int(
                (datetime.utcnow() - start_time).total_seconds() * 1000
            )

            # Determine provider type
            provider_type = (
                AIProvider.OPENAI
                if "openai" in provider.model_name
                else AIProvider.ANTHROPIC
            )

            # Create enrichment record
            enrichment = AIEnrichment(
                todo_id=0,  # Will be set by caller
                provider=provider_type,
                model_name=provider.model_name,
                suggested_category=result.output.suggested_category,
                suggested_priority=result.output.suggested_priority,
                suggested_size=result.output.suggested_size,
                estimated_duration_minutes=result.output.estimated_duration_minutes,
                is_recurring_candidate=result.output.is_recurring_candidate,
                suggested_recurrence_pattern=result.output.suggested_recurrence_pattern,
                reasoning=result.output.reasoning,
                confidence_score=result.output.confidence_score,
                context_keywords=result.output.detected_keywords,
                similar_tasks_found=len(similar_tasks),
                processing_time_ms=processing_time,
            )

            return enrichment

        except Exception as e:
            print(f"Enrichment failed: {e}")
            # Try fallback provider if available
            if preferred_provider:
                return await self.enrich_todo(title, description, user_context, None)
            return None

    async def _get_similar_tasks(self, _title: str, limit: int = 5) -> list[str]:
        """Find similar tasks for context."""
        # Simple keyword-based similarity for now
        # Could be enhanced with embeddings later

        # Simple keyword-based similarity for now
        # Could use full-text search or embeddings later

        similar = []
        # For now, just return empty list as we don't have search_by_title method
        # This could be enhanced later with full-text search
        return similar[:limit]

    def should_enrich(self, confidence_threshold: float | None = None) -> bool:
        """Check if enrichment should be performed."""
        # Use threshold for future enhancements
        _ = confidence_threshold or self.config.ai.confidence_threshold
        return self.config.ai.enable_auto_enrichment
