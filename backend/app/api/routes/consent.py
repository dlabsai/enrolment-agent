import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import SessionDep, get_request_user, require_user_roles
from app.models import ConversationSync, UserRole
from app.programs import PROGRAMS
from app.sync.main import sync_conversation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/consent", tags=["consent"])


class ConsentData(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone: str
    zip: str
    user_id: str
    conversation_id: str | None = None
    widget_closed: bool | None = None
    environment: str | None = None
    program: str | None = None
    online: bool | None = None


class ConsentResponse(BaseModel):
    success: bool
    message: str


def _parse_uuid(value: str | None) -> UUID | None:
    """Parse a string to UUID, returning None if invalid or empty."""
    if not value:
        return None
    try:
        return UUID(value)
    except (ValueError, TypeError):
        logger.warning(f"Invalid UUID format for conversation_id: {value}")
        return None


@router.post(
    "",
    response_model=ConsentResponse,
    dependencies=[Depends(require_user_roles(get_request_user, UserRole.PUBLIC))],
)
async def submit_consent(data: ConsentData, db: SessionDep) -> Any:
    """Submit user consent data and create or update a ConversationSync record.

    This endpoint is called when a user gives consent to have their
    conversation data collected and processed. If a record already exists
    for the same conversation_id, it will be updated instead of creating a duplicate.
    """
    try:
        logger.info(f"Received consent from user {data.user_id}")

        # Validate program if provided
        if data.program and data.program not in PROGRAMS:
            logger.warning(
                f"Invalid program value received: '{data.program}' for user {data.user_id}. "
                f"Valid programs: {PROGRAMS}"
            )

        # Parse conversation_id to UUID
        conversation_uuid = _parse_uuid(data.conversation_id)

        # Check if a sync record already exists for this conversation
        sync_record = None
        if conversation_uuid:
            result = await db.execute(
                select(ConversationSync).where(
                    ConversationSync.conversation_id == conversation_uuid
                )
            )
            sync_record = result.scalar_one_or_none()

        if sync_record:
            # Update existing record with latest consent data
            logger.info(
                f"Updating existing ConversationSync {sync_record.id} for conversation "
                f"{conversation_uuid}"
            )
            sync_record.first_name = data.first_name
            sync_record.last_name = data.last_name
            sync_record.email = data.email
            sync_record.phone = data.phone
            sync_record.zip = data.zip
            sync_record.user_id = data.user_id
            if data.environment:
                sync_record.environment = data.environment
        else:
            # Create new ConversationSync record
            sync_record = ConversationSync(
                first_name=data.first_name,
                last_name=data.last_name,
                email=data.email,
                phone=data.phone,
                zip=data.zip,
                user_id=data.user_id,
                conversation_id=conversation_uuid,
                last_message_id="",  # Will be updated when first sync occurs
                transcript=None,
                summary=None,
                environment=data.environment,
            )
            db.add(sync_record)

        await db.commit()
        await db.refresh(sync_record)

        logger.info(f"Created ConversationSync record {sync_record.id} for user {data.user_id}")

        # Trigger sync if widget was closed
        if data.widget_closed is True:
            logger.info(f"Widget closed for user {data.user_id}, triggering conversation sync")
            try:
                sync_result = await sync_conversation(
                    sync_record, db, debug=False, force_immediate=True
                )
                if sync_result:
                    logger.info(f"Successfully synced conversation for user {data.user_id}")
                else:
                    logger.warning(f"Sync returned False for user {data.user_id}, will retry later")
            except Exception:
                logger.exception(f"Error during immediate sync for user {data.user_id}")
                # Continue - periodic sync will retry later

        return ConsentResponse(success=True, message="Consent data received and saved successfully")
    except Exception as exc:
        logger.exception("Error saving consent data")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to save consent data") from exc
