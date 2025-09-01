"""Tests for AI enrichment functionality."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from todo.ai.enrichment import (
    DEFAULT_ENRICHMENT_PROMPT,
    TodoEnrichmentRequest,
    TodoEnrichmentResponse,
    create_enrichment_agent,
)
from todo.ai.enrichment_service import EnrichmentService
from todo.ai.learning import LearningService
from todo.ai.providers import AnthropicProvider, OpenAIProvider, ProviderManager
from todo.db.connection import DatabaseConnection
from todo.db.migrations import MigrationManager
from todo.db.repository import AIEnrichmentRepository, AILearningFeedbackRepository
from todo.models import AIEnrichment, AILearningFeedback, AIProvider, Priority, TaskSize


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test_ai.db"

    db = DatabaseConnection(str(db_path))

    # Initialize schema
    migration_manager = MigrationManager(db)
    migration_manager.initialize_schema()

    yield db

    # Cleanup
    db.close()
    if db_path.exists():
        db_path.unlink()
    Path(temp_dir).rmdir()


@pytest.fixture
def ai_enrichment_repo(temp_db):
    """Create AIEnrichmentRepository with temp database."""
    return AIEnrichmentRepository(temp_db)


@pytest.fixture
def ai_feedback_repo(temp_db):
    """Create AILearningFeedbackRepository with temp database."""
    return AILearningFeedbackRepository(temp_db)


@pytest.fixture
def sample_todo(temp_db):
    """Create a sample todo for testing AI enrichments."""
    from todo.db.repository import TodoRepository

    todo_repo = TodoRepository(temp_db)
    return todo_repo.create_todo("Sample todo for AI testing", "Test description")


class TestTodoEnrichmentModels:
    """Test enrichment request/response models."""

    def test_enrichment_request_creation(self):
        """Test creating enrichment request."""
        request = TodoEnrichmentRequest(
            title="Write unit tests",
            user_context="For the AI module",
            similar_tasks=["Write integration tests", "Add test coverage"],
        )

        assert request.title == "Write unit tests"
        assert request.user_context == "For the AI module"
        assert len(request.similar_tasks) == 2

    def test_enrichment_response_creation(self):
        """Test creating enrichment response."""
        response = TodoEnrichmentResponse(
            suggested_category="Work",
            suggested_priority=Priority.HIGH,
            suggested_size=TaskSize.MEDIUM,
            estimated_duration_minutes=30,
            is_recurring_candidate=False,
            suggested_recurrence_pattern=None,
            reasoning="This is a development task requiring moderate effort",
            confidence_score=0.8,
            detected_keywords=["unit", "tests", "AI"],
            urgency_indicators=["tests"],
        )

        assert response.suggested_category == "Work"
        assert response.suggested_priority == Priority.HIGH
        assert response.suggested_size == TaskSize.MEDIUM
        assert response.estimated_duration_minutes == 30
        assert response.confidence_score == 0.8


class TestProviders:
    """Test AI provider functionality."""

    def test_openai_provider_creation(self):
        """Test OpenAI provider creation."""
        provider = OpenAIProvider("fake-api-key", "gpt-4")

        assert provider.api_key == "fake-api-key"
        assert provider.model_name == "gpt-4"

    def test_anthropic_provider_creation(self):
        """Test Anthropic provider creation."""
        provider = AnthropicProvider("fake-api-key", "claude-3-haiku")

        assert provider.api_key == "fake-api-key"
        assert provider.model_name == "claude-3-haiku"

    @patch("todo.ai.providers.get_app_config")
    def test_provider_manager_initialization(self, mock_config):
        """Test provider manager initialization."""
        # Mock configuration
        mock_ai_config = Mock()
        mock_ai_config.openai_api_key = "openai-key"
        mock_ai_config.anthropic_api_key = "anthropic-key"
        mock_ai_config.openai_model = "gpt-4"
        mock_ai_config.anthropic_model = "claude-3-haiku"
        mock_ai_config.default_provider = AIProvider.OPENAI

        mock_config.return_value = Mock(ai=mock_ai_config)

        manager = ProviderManager()

        assert AIProvider.OPENAI in manager.providers
        assert AIProvider.ANTHROPIC in manager.providers


class TestAIRepositories:
    """Test AI data repositories."""

    def test_ai_enrichment_repository_create(self, ai_enrichment_repo, sample_todo):
        """Test creating AI enrichment record."""
        enrichment = AIEnrichment(
            todo_id=sample_todo.id,
            provider=AIProvider.OPENAI,
            model_name="gpt-4",
            suggested_category="Work",
            suggested_priority=Priority.HIGH,
            suggested_size=TaskSize.MEDIUM,
            estimated_duration_minutes=30,
            reasoning="Development task",
            confidence_score=0.8,
            context_keywords=["test", "development"],
            similar_tasks_found=2,
            processing_time_ms=250,
        )

        saved_enrichment = ai_enrichment_repo.create(enrichment)

        assert saved_enrichment.id is not None
        assert saved_enrichment.todo_id == sample_todo.id
        assert saved_enrichment.provider == AIProvider.OPENAI
        assert abs(saved_enrichment.confidence_score - 0.8) < 0.001

    def test_ai_enrichment_repository_get_by_todo_id(
        self, ai_enrichment_repo, sample_todo
    ):
        """Test retrieving enrichment by todo ID."""
        # Create enrichment
        enrichment = AIEnrichment(
            todo_id=sample_todo.id,
            provider=AIProvider.OPENAI,
            model_name="gpt-4",
            suggested_category="Work",
            confidence_score=0.7,
        )
        ai_enrichment_repo.create(enrichment)

        # Retrieve by todo ID
        retrieved = ai_enrichment_repo.get_by_todo_id(sample_todo.id)

        assert retrieved is not None
        assert retrieved.todo_id == sample_todo.id
        assert retrieved.provider == AIProvider.OPENAI

    def test_ai_feedback_repository_create(self, ai_feedback_repo):
        """Test creating learning feedback record."""
        feedback = AILearningFeedback(
            original_task_text="Write tests for AI module",
            ai_provider=AIProvider.OPENAI,
            ai_suggested_category="Personal",
            ai_suggested_size=TaskSize.SMALL,
            ai_suggested_priority=Priority.LOW,
            user_corrected_category="Work",
            user_corrected_size=TaskSize.MEDIUM,
            user_corrected_priority=Priority.HIGH,
            task_keywords=["tests", "AI", "module"],
            correction_type="category_change",
        )

        saved_feedback = ai_feedback_repo.create(feedback)

        assert saved_feedback.id is not None
        assert saved_feedback.correction_type == "category_change"
        assert saved_feedback.user_corrected_category == "Work"

    def test_ai_feedback_repository_get_by_keyword(self, ai_feedback_repo):
        """Test retrieving feedback by keyword."""
        # Create feedback with keywords
        feedback = AILearningFeedback(
            original_task_text="Write unit tests",
            ai_provider=AIProvider.OPENAI,
            task_keywords=["unit", "tests", "development"],
            correction_type="size_increase",
        )
        ai_feedback_repo.create(feedback)

        # Search by keyword
        results = ai_feedback_repo.get_by_keyword("unit")

        assert len(results) == 1
        assert results[0].correction_type == "size_increase"


class TestLearningService:
    """Test AI learning service."""

    def test_learning_service_initialization(self, temp_db):
        """Test learning service initialization."""
        service = LearningService(temp_db)
        assert service.feedback_repo is not None

    def test_extract_keywords(self, temp_db):
        """Test keyword extraction."""
        service = LearningService(temp_db)

        keywords = service._extract_keywords("Write unit tests for the AI module")

        assert "write" in keywords
        assert "unit" in keywords
        assert "tests" in keywords
        assert "module" in keywords
        # Stop words should be filtered out
        assert "for" not in keywords
        assert "the" not in keywords

    def test_size_to_int_conversion(self, temp_db):
        """Test task size to integer conversion."""
        service = LearningService(temp_db)

        assert service._size_to_int(TaskSize.SMALL) == 1
        assert service._size_to_int(TaskSize.MEDIUM) == 2
        assert service._size_to_int(TaskSize.LARGE) == 3


class TestEnrichmentService:
    """Test main enrichment service."""

    @patch("todo.ai.enrichment_service.get_app_config")
    def test_enrichment_service_initialization(self, mock_config, temp_db):
        """Test enrichment service initialization."""
        # Mock configuration
        mock_ai_config = Mock()
        mock_ai_config.enable_auto_enrichment = True
        mock_ai_config.confidence_threshold = 0.7

        mock_db_config = Mock()
        mock_db_config.database_path = "test.db"

        mock_config.return_value = Mock(ai=mock_ai_config, database=mock_db_config)

        service = EnrichmentService(temp_db)

        assert service.config is not None
        assert service.provider_manager is not None
        assert service.learning_service is not None
        assert service.ai_repo is not None

    @patch("todo.ai.enrichment_service.get_app_config")
    def test_should_enrich_disabled(self, mock_config, temp_db):
        """Test enrichment disabled by configuration."""
        # Mock configuration with enrichment disabled
        mock_ai_config = Mock()
        mock_ai_config.enable_auto_enrichment = False

        mock_config.return_value = Mock(ai=mock_ai_config)

        service = EnrichmentService(temp_db)

        assert not service.should_enrich()

    @patch("todo.ai.enrichment_service.get_app_config")
    def test_should_enrich_enabled(self, mock_config, temp_db):
        """Test enrichment enabled by configuration."""
        # Mock configuration with enrichment enabled
        mock_ai_config = Mock()
        mock_ai_config.enable_auto_enrichment = True
        mock_ai_config.confidence_threshold = 0.7

        mock_config.return_value = Mock(ai=mock_ai_config)

        service = EnrichmentService(temp_db)

        assert service.should_enrich()


class TestEnrichmentAgent:
    """Test enrichment agent creation."""

    def test_create_enrichment_agent(self):
        """Test creating enrichment agent."""
        # This test just ensures the function exists and can be called
        # We can't test the actual agent without API keys
        assert create_enrichment_agent is not None
        assert DEFAULT_ENRICHMENT_PROMPT is not None
        assert "task categorization" in DEFAULT_ENRICHMENT_PROMPT.lower()


# Integration test would require actual API keys, so we'll skip for now
@pytest.mark.skip(reason="Requires API keys for actual AI providers")
class TestAIIntegration:
    """Integration tests for AI enrichment (requires API keys)."""

    async def test_actual_enrichment(self):
        """Test actual AI enrichment with real providers."""
        # This would test with real API calls
        pass
