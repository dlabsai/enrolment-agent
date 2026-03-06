from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import SessionDep, get_current_user, require_user_roles
from app.core.app_settings import (
    get_effective_settings,
    load_app_settings_cache,
    reset_app_settings,
    update_app_settings,
)
from app.models import UserRole

router = APIRouter(
    prefix="/settings",
    tags=["settings"],
    dependencies=[Depends(require_user_roles(get_current_user, UserRole.ADMIN, UserRole.DEV))],
)


class AppSettingsResponse(BaseModel):
    effective: dict[str, str]
    system: dict[str, str]
    overrides: dict[str, str]


class AppSettingsUpdate(BaseModel):
    university_name: str | None = None
    university_website_url: str | None = None
    university_admissions_phone: str | None = None
    university_transcripts_email: str | None = None
    university_application_url: str | None = None
    university_accreditation_url: str | None = None
    guardrails_blocked_message: str | None = None


@router.get("", response_model=AppSettingsResponse)
async def get_settings() -> Any:
    effective, system, overrides = await get_effective_settings()
    return AppSettingsResponse(effective=effective, system=system, overrides=overrides)


@router.post("", response_model=AppSettingsResponse)
async def update_settings(updates: AppSettingsUpdate, session: SessionDep) -> Any:
    updates_dict = updates.model_dump(exclude_unset=True)
    await update_app_settings(session, updates_dict)
    await session.commit()
    await load_app_settings_cache(session)
    effective, system, overrides = await get_effective_settings()
    return AppSettingsResponse(effective=effective, system=system, overrides=overrides)


@router.delete("", response_model=AppSettingsResponse)
async def reset_settings(session: SessionDep) -> Any:
    await reset_app_settings(session)
    await session.commit()
    await load_app_settings_cache(session)
    effective, system, overrides = await get_effective_settings()
    return AppSettingsResponse(effective=effective, system=system, overrides=overrides)
