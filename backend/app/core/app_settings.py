from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_session
from app.models import AppSettings

_db_overrides_cache: dict[str, str | None] = {}


SETTING_FIELDS = [
    ("university_name", "UNIVERSITY_NAME"),
    ("university_website_url", "UNIVERSITY_WEBSITE_URL"),
    ("university_admissions_phone", "UNIVERSITY_ADMISSIONS_PHONE"),
    ("university_transcripts_email", "UNIVERSITY_TRANSCRIPTS_EMAIL"),
    ("university_application_url", "UNIVERSITY_APPLICATION_URL"),
    ("university_accreditation_url", "UNIVERSITY_ACCREDITATION_URL"),
    ("guardrails_blocked_message", "GUARDRAILS_BLOCKED_MESSAGE"),
]


async def load_app_settings_cache(session: AsyncSession | None = None) -> None:
    global _db_overrides_cache  # noqa: PLW0603
    if session:
        result = await session.execute(select(AppSettings).limit(1))
        row = result.scalar_one_or_none()
    else:
        async with get_session() as sess:
            result = await sess.execute(select(AppSettings).limit(1))
            row = result.scalar_one_or_none()

    if row:
        _db_overrides_cache = {
            "university_name": row.university_name,
            "university_website_url": row.university_website_url,
            "university_admissions_phone": row.university_admissions_phone,
            "university_transcripts_email": row.university_transcripts_email,
            "university_application_url": row.university_application_url,
            "university_accreditation_url": row.university_accreditation_url,
            "guardrails_blocked_message": row.guardrails_blocked_message,
        }
    else:
        _db_overrides_cache = {}


async def get_effective_settings() -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    effective: dict[str, str] = {}
    system: dict[str, str] = {}
    overrides: dict[str, str] = {}

    for field, env_attr in SETTING_FIELDS:
        system_val: str = getattr(settings, env_attr)
        system[field] = system_val

        db_val = _db_overrides_cache.get(field)
        if db_val is not None:
            effective[field] = db_val
            overrides[field] = db_val
        else:
            effective[field] = system_val

    return effective, system, overrides


async def update_app_settings(session: AsyncSession, updates: dict[str, Any]) -> None:
    global _db_overrides_cache  # noqa: PLW0603
    result = await session.execute(select(AppSettings).limit(1))
    row = result.scalar_one_or_none()
    if row:
        for key, value in updates.items():
            setattr(row, key, value)
    else:
        row = AppSettings(**updates)
        session.add(row)
    await session.flush()

    _db_overrides_cache = {
        "university_name": row.university_name,
        "university_website_url": row.university_website_url,
        "university_admissions_phone": row.university_admissions_phone,
        "university_transcripts_email": row.university_transcripts_email,
        "university_application_url": row.university_application_url,
        "university_accreditation_url": row.university_accreditation_url,
        "guardrails_blocked_message": row.guardrails_blocked_message,
    }


async def reset_app_settings(session: AsyncSession) -> None:
    global _db_overrides_cache  # noqa: PLW0603
    result = await session.execute(select(AppSettings).limit(1))
    row = result.scalar_one_or_none()
    if row:
        await session.delete(row)
        await session.flush()
    _db_overrides_cache = {}


def get_guardrails_blocked_message() -> str:
    """Get effective guardrails blocked message: DB override if set, otherwise env default."""
    db_val = _db_overrides_cache.get("guardrails_blocked_message")
    if db_val is not None:
        return db_val
    return settings.GUARDRAILS_BLOCKED_MESSAGE


def get_effective_value(field: str, env_attr: str) -> str:
    """Get effective value: DB override if set, otherwise env default."""
    db_val = _db_overrides_cache.get(field)
    if db_val is not None:
        return db_val
    return str(getattr(settings, env_attr))
