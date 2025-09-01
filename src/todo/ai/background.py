"""Background AI enrichment to keep UI responsive."""

import asyncio

from ..core.config import get_app_config
from ..db.connection import DatabaseConnection
from ..db.repository import AIEnrichmentRepository, CategoryRepository, TodoRepository
from .enrichment_service import EnrichmentService


class BackgroundEnrichmentService:
    """Handle background AI enrichment to keep UI responsive."""

    def __init__(self, db_connection: DatabaseConnection | None = None):
        if db_connection:
            self.db = db_connection
        else:
            config = get_app_config()
            self.db = DatabaseConnection(config.database.database_path)

        self.enrichment_service = EnrichmentService(self.db)
        self.todo_repo = TodoRepository(self.db)
        self.ai_repo = AIEnrichmentRepository(self.db)
        self.category_repo = CategoryRepository(self.db)
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
                title=todo.title, description=todo.description
            )

            if enrichment:
                # Save enrichment
                enrichment.todo_id = todo_id
                self.ai_repo.create(enrichment)

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
            updates["ai_suggested_size"] = enrichment.suggested_size
            updates["final_size"] = enrichment.suggested_size

        if not todo.user_override_priority and not todo.ai_suggested_priority:
            updates["ai_suggested_priority"] = enrichment.suggested_priority
            updates["final_priority"] = enrichment.suggested_priority

        # Apply category if we can find matching category
        if enrichment.suggested_category and not todo.category_id:
            category = self.category_repo.get_by_name(enrichment.suggested_category)
            if category:
                updates["category_id"] = category.id

        if updates:
            self.todo_repo.update_todo(todo.id, updates)
