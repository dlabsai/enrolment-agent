from typing import Any

import httpx
from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, require_user_roles
from app.core.config import settings
from app.models import UserRole

router = APIRouter(tags=["models"])

_openrouter_models: list[str] = []


@router.get(
    "/models",
    response_model=list[str],
    dependencies=[
        Depends(require_user_roles(get_current_user, UserRole.USER, UserRole.ADMIN, UserRole.DEV))
    ],
)
async def list_models() -> Any:
    available_models: list[str] = []
    use_openrouter = False
    for model in settings.MODELS.split(","):
        model_name = model.strip()
        if model_name == "openrouter:*":
            use_openrouter = True
        elif model_name != "":
            available_models.append(model_name)

    if use_openrouter and not _openrouter_models:
        async with httpx.AsyncClient() as client:
            response = await client.get("https://openrouter.ai/api/v1/models")
            response.raise_for_status()
            openrouter_models = response.json()
            for model in openrouter_models.get("data", []):
                supported_parameters = model.get("supported_parameters", [])
                supports_tools = any(
                    param in supported_parameters for param in ("tools", "tool_choice")
                )
                if supports_tools:
                    _openrouter_models.append("openrouter:" + model["id"].strip())

    return list(dict.fromkeys(available_models + _openrouter_models))
