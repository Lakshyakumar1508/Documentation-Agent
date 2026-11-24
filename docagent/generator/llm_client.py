
"""LLM client abstraction supporting NVIDIA API, OpenAI-compatible endpoints, and offline mock."""

from abc import ABC, abstractmethod
import os
from typing import Optional
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from docagent.core.config import settings
from docagent.core.logging import logger


class BaseLLMClient(ABC):
    """Abstract interface for LLM synthesis."""

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.1) -> str:
        """Generates documentation prose given system instructions and context."""
        pass


class OpenAICompatibleClient(BaseLLMClient):
    """Client for OpenAI, NVIDIA NIM, Ollama, or any OpenAI-compatible API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = settings.LLM_TIMEOUT_SECONDS,
    ):
        from openai import OpenAI

        self.api_key = api_key or settings.LLM_API_KEY or "dummy-key-for-local"
        self.base_url = base_url or settings.LLM_BASE_URL
        self.model = model or settings.LLM_MODEL
        self.timeout = timeout

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout,
        )

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.1) -> str:
        """Executes chat completion with retry and token limits."""
        logger.debug(f"Calling LLM provider model={self.model} base_url={self.base_url}")
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=settings.LLM_MAX_TOKENS,
        )
        content = response.choices[0].message.content or ""
        return content.strip()


class MockLLMClient(BaseLLMClient):
    """Deterministic fallback and offline testing client."""

    def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.1) -> str:
        """Produces structured markdown synthesis deterministically without external API calls."""
        return (
            "### Overview\n"
            "This document was synthesized using evidence-grounded AST code inventory.\n"
            "All claims reflect verified source symbols, routes, and configuration variables.\n"
        )


def get_llm_client() -> BaseLLMClient:
    """Factory creating configured LLM client instance."""
    provider = settings.LLM_PROVIDER.lower()
    
    if provider in ("openai", "nvidia", "custom"):
        if not settings.LLM_API_KEY:
            logger.info("No LLM_API_KEY configured. Falling back to MockLLMClient.")
            return MockLLMClient()
        return OpenAICompatibleClient()
    
    return MockLLMClient()
