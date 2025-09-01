"""AI provider management with OpenAI and Anthropic support."""

from abc import ABC, abstractmethod

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI
from pydantic_ai import Agent

from ..core.config import get_app_config
from ..models import AIProvider


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
            f"openai:{self.model_name}",
            output_type=result_type,
            system_prompt=system_prompt,
        )

    async def health_check(self) -> bool:
        """Check OpenAI API availability."""
        try:
            await self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1,
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
            f"anthropic:{self.model_name}",
            output_type=result_type,
            system_prompt=system_prompt,
        )

    async def health_check(self) -> bool:
        """Check Anthropic API availability."""
        try:
            await self.client.messages.create(
                model=self.model_name,
                max_tokens=1,
                messages=[{"role": "user", "content": "test"}],
            )
            return True
        except Exception:
            return False


class ProviderManager:
    """Manages multiple AI providers with fallback."""

    def __init__(self):
        self.config = get_app_config()
        self.providers: dict[AIProvider, BaseLLMProvider] = {}
        self._initialize_providers()

    def _initialize_providers(self):
        """Initialize available providers."""
        if self.config.ai.openai_api_key:
            self.providers[AIProvider.OPENAI] = OpenAIProvider(
                self.config.ai.openai_api_key, self.config.ai.openai_model
            )

        if self.config.ai.anthropic_api_key:
            self.providers[AIProvider.ANTHROPIC] = AnthropicProvider(
                self.config.ai.anthropic_api_key, self.config.ai.anthropic_model
            )

    async def get_available_provider(
        self, preferred: AIProvider | None = None
    ) -> BaseLLMProvider | None:
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
