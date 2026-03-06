from functools import lru_cache

import httpx
from pydantic_ai import Embedder
from pydantic_ai.embeddings.openai import OpenAIEmbeddingModel
from pydantic_ai.models.instrumented import InstrumentationSettings
from pydantic_ai.providers.azure import AzureProvider

from app.core.config import settings


def _validate_azure_settings() -> None:
    if not settings.AZURE_API_KEY_1:
        raise ValueError("AZURE_API_KEY_1 is required but not set.")
    if not settings.AZURE_API_BASE_1:
        raise ValueError("AZURE_API_BASE_1 is required but not set.")
    if not settings.AZURE_API_VERSION_1:
        raise ValueError("AZURE_API_VERSION_1 is required but not set.")


@lru_cache(maxsize=1)
def get_azure_embedding_embedder() -> Embedder:
    _validate_azure_settings()
    http_client = httpx.AsyncClient(timeout=settings.LLM_REQUEST_TIMEOUT)
    provider = AzureProvider(
        azure_endpoint=settings.AZURE_API_BASE_1,
        api_version=settings.AZURE_API_VERSION_1,
        api_key=settings.AZURE_API_KEY_1,
        http_client=http_client,
    )
    # TODO: consider large model
    model = OpenAIEmbeddingModel("text-embedding-3-small", provider=provider)
    instrumentation = InstrumentationSettings(version=3)
    return Embedder(model, instrument=instrumentation)
