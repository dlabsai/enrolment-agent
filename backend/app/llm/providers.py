from functools import lru_cache

import httpx
from pydantic_ai.models import Model
from pydantic_ai.models.instrumented import InstrumentationSettings
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIResponsesModel
from pydantic_ai.profiles.openai import OpenAIModelProfile, openai_model_profile
from pydantic_ai.providers.azure import AzureProvider
from pydantic_ai.providers.openai import OpenAIProvider

from app.core.config import settings


def _get_azure_resource(deployment_name: str) -> tuple[str, str, str]:
    """Get Azure resource credentials for a deployment.

    Returns (api_base, api_version, api_key) for the appropriate resource.
    Uses AZURE_MODEL_RESOURCE_MAP to determine which resource to use.
    Models not in the map default to resource 1.
    """
    resource_map: dict[str, str] = {}
    if settings.AZURE_MODEL_RESOURCE_MAP:
        for mapping in settings.AZURE_MODEL_RESOURCE_MAP.split(","):
            if ":" in mapping:
                model, resource = mapping.strip().split(":", 1)
                resource_map[model.strip()] = resource.strip()

    resource_num = resource_map.get(deployment_name, "1")

    if resource_num == "2":
        return (settings.AZURE_API_BASE_2, settings.AZURE_API_VERSION_2, settings.AZURE_API_KEY_2)
    if resource_num == "3":
        return (settings.AZURE_API_BASE_3, settings.AZURE_API_VERSION_3, settings.AZURE_API_KEY_3)

    return (settings.AZURE_API_BASE_1, settings.AZURE_API_VERSION_1, settings.AZURE_API_KEY_1)


def _get_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=settings.LLM_REQUEST_TIMEOUT)


def _build_azure_model(deployment_name: str) -> Model:
    api_base, api_version, api_key = _get_azure_resource(deployment_name)
    normalized_base = api_base.rstrip("/")

    if normalized_base.endswith("/openai/v1"):
        profile = openai_model_profile(deployment_name)
        if deployment_name == "Mistral-Large-3":
            profile = OpenAIModelProfile.from_profile(profile).update(
                OpenAIModelProfile(openai_supports_tool_choice_required=False)
            )
        return OpenAIChatModel(
            deployment_name,
            provider=OpenAIProvider(
                base_url=api_base, api_key=api_key or None, http_client=_get_http_client()
            ),
            profile=profile,
        )

    return OpenAIResponsesModel(
        deployment_name,
        provider=AzureProvider(
            azure_endpoint=api_base,
            api_version=api_version,
            api_key=api_key,
            http_client=_get_http_client(),
        ),
    )


def get_pydantic_ai_model(model_name: str) -> Model | str:
    """Resolve model names for PydanticAI.

    Azure is special-cased because deployment names must be routed to the correct
    Azure resource (endpoint/version/key) via AZURE_MODEL_RESOURCE_MAP.

    Supports:
    - azure:deployment-name -> OpenAIChatModel with AzureProvider
    - Standard PydanticAI format (provider:model) is passed through
    """
    if model_name.startswith("azure:"):
        # Azure OpenAI - route to Azure or OpenAI-compatible endpoints
        deployment_name = model_name.split("azure:", 1)[-1]
        return _build_azure_model(deployment_name)
    if model_name.startswith("openai:"):
        model = model_name.split("openai:", 1)[-1]
        return OpenAIResponsesModel(
            model,
            provider=OpenAIProvider(
                api_key=settings.OPENAI_API_KEY or None, http_client=_get_http_client()
            ),
        )
    return model_name


@lru_cache(maxsize=1)
def get_instrumentation_settings() -> InstrumentationSettings:
    return InstrumentationSettings(version=3)
