import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.tree_utils import get_current_branch_path
from app.core.db import get_session
from app.models import Conversation, ConversationSync, Message
from app.sync.message import SyncMessage
from app.sync.summary import summarize_conversation
from app.sync.transcript import format_transcript, format_transcript_for_summary
from app.sync.variables import extract_variables

logger = logging.getLogger(__name__)

SYNC_DELAY_MINUTES = 2


def _populate_default_user_flags(sync_record: ConversationSync) -> tuple[str, bool]:
    """Ensure program/online fields always have defaults."""
    program = sync_record.program or "BS/BA"
    online = sync_record.online if sync_record.online is not None else False

    sync_record.program = program
    sync_record.online = online

    return program, online


async def _get_messages(
    conversation_id: str | UUID, after_message_id: str | None = None
) -> list[SyncMessage]:
    logger.debug(
        f"Fetching messages for conversation {conversation_id} after message_id {after_message_id}"
    )

    try:
        async with get_session() as session:
            conv_uuid = (
                conversation_id if isinstance(conversation_id, UUID) else UUID(conversation_id)
            )
            active_branch_ids = await get_current_branch_path(session, conv_uuid)

            if not active_branch_ids:
                logger.warning(f"No messages found for conversation {conversation_id}")
                return []

            db_messages: list[Message] = []
            for message_id in active_branch_ids:
                db_message = await session.get(Message, message_id)
                if db_message:
                    db_messages.append(db_message)

            messages: list[SyncMessage] = []
            for db_message in db_messages:
                messages.append(
                    SyncMessage(
                        id=str(db_message.id),
                        role=db_message.role,
                        content=db_message.content,
                        timestamp=db_message.created_at.replace(tzinfo=UTC).isoformat(),
                    )
                )

            if after_message_id:
                try:
                    index = next(i for i, msg in enumerate(messages) if msg.id == after_message_id)
                    messages = messages[index + 1 :]
                    logger.debug(
                        f"Filtered to {len(messages)} messages after message_id {after_message_id}"
                    )
                except StopIteration:
                    logger.warning(
                        f"Message ID {after_message_id} not found in conversation, "
                        "returning all messages"
                    )

            logger.debug(f"Returning {len(messages)} messages from database")
            return messages

    except Exception:
        logger.exception("Error fetching messages from database")
        raise


async def sync_conversation(
    sync_record: ConversationSync,
    db_session: AsyncSession,
    *,
    debug: bool = False,
    force_immediate: bool = False,
) -> bool:
    logger.debug(f"Starting sync for conversation {sync_record.conversation_id}")

    if not sync_record.conversation_id:
        logger.debug(f"ConversationSync {sync_record.id} has no conversation_id yet, skipping")
        return True

    try:
        new_messages = await _get_messages(sync_record.conversation_id, sync_record.last_message_id)

        if not new_messages:
            logger.debug(f"No new messages for conversation {sync_record.conversation_id}")
            return True

        complete_messages = [
            msg for msg in new_messages if not (msg.role == "assistant" and not msg.content.strip())
        ]

        if not complete_messages:
            logger.debug(
                f"All new messages for conversation {sync_record.conversation_id} are "
                f"incomplete (empty assistant messages)"
            )
            return True

        logger.debug(
            f"Found {len(complete_messages)} complete new messages for conversation "
            f"{sync_record.conversation_id}"
        )

        # Check if at least SYNC_DELAY_MINUTES have passed since the last message
        # Skip this check if force_immediate is True
        if not force_immediate:
            last_message = complete_messages[-1]
            last_message_time = datetime.fromisoformat(last_message.timestamp)
            now = datetime.now(UTC)
            time_since_last_message = now - last_message_time

            if time_since_last_message < timedelta(minutes=SYNC_DELAY_MINUTES):
                minutes_remaining = SYNC_DELAY_MINUTES - (
                    time_since_last_message.total_seconds() / 60
                )
                logger.debug(
                    f"Skipping sync for conversation {sync_record.conversation_id} - "
                    f"last message was {time_since_last_message.total_seconds() / 60:.1f} "
                    f"minutes ago, waiting {minutes_remaining:.1f} more minutes"
                )
                return True

        all_messages = await _get_messages(sync_record.conversation_id, after_message_id=None)

        complete_all_messages = [
            msg for msg in all_messages if not (msg.role == "assistant" and not msg.content.strip())
        ]

        transcript_with_timestamps = format_transcript(complete_all_messages)
        transcript_for_summary = format_transcript_for_summary(complete_all_messages)

        summary = await summarize_conversation(
            transcript_for_summary, conversation_id=str(sync_record.conversation_id)
        )

        variables = await extract_variables(
            transcript_for_summary, conversation_id=str(sync_record.conversation_id)
        )
        sync_record.program = variables.user_degree_program_of_interest or "BS/BA"  # type: ignore[reportGeneralTypeIssues]
        sync_record.online = variables.user_wants_to_study_on_campus or False

        program, online = _populate_default_user_flags(sync_record)

        user_data: dict[str, Any] = {  # noqa: F841 # pyright: ignore[reportUnusedVariable]
            "first_name": sync_record.first_name,
            "last_name": sync_record.last_name,
            "email": sync_record.email,
            "phone": sync_record.phone,
            "zip": sync_record.zip,
            "user_id": sync_record.user_id,
            "program": program,
            "online": online,
        }

        if debug:
            debug_dir = Path("src") / "debug_output"
            debug_dir.mkdir(exist_ok=True)

            transcript_file = debug_dir / f"{sync_record.conversation_id}_transcript.txt"
            transcript_file.write_text(transcript_with_timestamps, encoding="utf-8")
            logger.info(f"Debug: Saved transcript to {transcript_file}")

            summary_file = debug_dir / f"{sync_record.conversation_id}_summary.txt"
            summary_file.write_text(summary, encoding="utf-8")
            logger.info(f"Debug: Saved summary to {summary_file}")

        consent_data: dict[str, Any] = {  # noqa: F841 # pyright: ignore[reportUnusedVariable]
            "first_name": sync_record.first_name,
            "last_name": sync_record.last_name,
            "email": sync_record.email,
            "phone": sync_record.phone,
            "zip": sync_record.zip,
            "user_id": sync_record.user_id,
            "conversation_id": sync_record.conversation_id,
            "environment": sync_record.environment,
            "program": sync_record.program,
            "online": sync_record.online,
        }

        sync_record.transcript = transcript_with_timestamps
        sync_record.summary = summary
        sync_record.last_message_id = complete_messages[-1].id

        # Also save summary to the conversation record for display in internal UI
        conversation = await db_session.get(Conversation, sync_record.conversation_id)
        if conversation:
            conversation.summary = summary

        await db_session.commit()

    except Exception:
        logger.exception(f"Error syncing conversation {sync_record.conversation_id}")
        await db_session.rollback()
        return False
    else:
        logger.info(f"Sync completed for conversation {sync_record.conversation_id}")
        return True
