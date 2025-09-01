"""AI learning system for user feedback."""

from ..db.connection import DatabaseConnection
from ..db.repository import AILearningFeedbackRepository
from ..models import AILearningFeedback, AIProvider, TaskSize


class LearningService:
    """Service for AI learning from user feedback."""

    def __init__(self, db_connection: DatabaseConnection | None = None):
        if db_connection:
            self.feedback_repo = AILearningFeedbackRepository(db_connection)
        else:
            # Use default connection
            from ..core.config import get_app_config

            config = get_app_config()
            default_db = DatabaseConnection(config.database.database_path)
            self.feedback_repo = AILearningFeedbackRepository(default_db)

    async def record_user_override(
        self,
        original_task: str,
        ai_provider: AIProvider,
        ai_suggestions: dict,
        user_corrections: dict,
    ) -> None:
        """Record user corrections for learning."""

        # Determine correction types
        correction_types = []

        if "size" in user_corrections and user_corrections[
            "size"
        ] != ai_suggestions.get("size"):
            if self._size_to_int(user_corrections["size"]) > self._size_to_int(
                ai_suggestions["size"]
            ):
                correction_types.append("size_increase")
            else:
                correction_types.append("size_decrease")

        if "category" in user_corrections and user_corrections[
            "category"
        ] != ai_suggestions.get("category"):
            correction_types.append("category_change")

        if "priority" in user_corrections and user_corrections[
            "priority"
        ] != ai_suggestions.get("priority"):
            correction_types.append("priority_change")

        # Extract keywords for learning
        keywords = self._extract_keywords(original_task)

        # Record feedback for each correction type
        for correction_type in correction_types:
            feedback = AILearningFeedback(
                original_task_text=original_task,
                ai_provider=ai_provider,
                ai_suggested_category=ai_suggestions.get("category"),
                ai_suggested_size=ai_suggestions.get("size"),
                ai_suggested_priority=ai_suggestions.get("priority"),
                user_corrected_category=user_corrections.get("category"),
                user_corrected_size=user_corrections.get("size"),
                user_corrected_priority=user_corrections.get("priority"),
                task_keywords=keywords,
                correction_type=correction_type,
            )

            self.feedback_repo.create(feedback)

    async def enhance_prompt_with_learning(
        self, base_prompt: str, task_text: str, model_name: str
    ) -> str:
        """Enhance system prompt with learning from past corrections."""

        keywords = self._extract_keywords(task_text)
        learning_context = await self._get_learning_context(keywords, model_name)

        if not learning_context:
            return base_prompt

        enhanced_prompt = base_prompt + "\n\nLEARNING CONTEXT:\n"
        enhanced_prompt += (
            "Based on past user corrections, please consider these patterns:\n"
        )

        for pattern in learning_context:
            enhanced_prompt += f"- {pattern}\n"

        return enhanced_prompt

    async def _get_learning_context(
        self, keywords: list[str], _model_name: str
    ) -> list[str]:
        """Get relevant learning patterns for the current task."""

        patterns = []

        # Get recent feedback for similar keywords
        for keyword in keywords[:3]:  # Top 3 keywords
            feedback_items = self.feedback_repo.get_by_keyword(keyword, limit=5)

            for feedback in feedback_items:
                if feedback.correction_type == "size_increase":
                    patterns.append(
                        f"Tasks with '{keyword}' are often larger than initially estimated"
                    )
                elif feedback.correction_type == "size_decrease":
                    patterns.append(
                        f"Tasks with '{keyword}' are often smaller than initially estimated"
                    )
                elif (
                    feedback.correction_type == "category_change"
                    and feedback.user_corrected_category
                ):
                    patterns.append(
                        f"Tasks with '{keyword}' are often categorized as '{feedback.user_corrected_category}'"
                    )

        return list(set(patterns))  # Remove duplicates

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract meaningful keywords from task text."""
        import re

        # Simple keyword extraction
        words = re.findall(r"\b\w{3,}\b", text.lower())  # Words 3+ characters

        # Remove common stop words
        stop_words = {
            "the",
            "and",
            "for",
            "with",
            "from",
            "that",
            "this",
            "have",
            "are",
            "was",
            "will",
            "can",
        }
        keywords = [word for word in words if word not in stop_words]

        return keywords[:10]  # Top 10 keywords

    def _size_to_int(self, size: TaskSize) -> int:
        """Convert task size to integer for comparison."""
        size_map = {TaskSize.SMALL: 1, TaskSize.MEDIUM: 2, TaskSize.LARGE: 3}
        return size_map.get(size, 2)
