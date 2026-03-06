import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, text

from app.chat.tools.utils import get_azure_embedding_embedder
from app.core.db import engine, get_session
from app.models import Conversation, ConversationSync
from app.rag.build import build_search_db
from app.rag.transform.transform_wp_data import main as transform_wp_main
from app.rag.wordpress.cli import main as wp_main
from app.sync.main import sync_conversation

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def sync_conversations_job(*, debug: bool = False) -> None:
    logger.debug("Starting scheduled conversation sync job")

    try:
        async with get_session() as session:
            # Only sync public conversations (is_public=True)
            result = await session.execute(
                select(ConversationSync)
                .outerjoin(Conversation, ConversationSync.conversation_id == Conversation.id)
                .where(
                    (Conversation.is_public.is_(True))
                    | (Conversation.id == None)  # noqa: E711
                    | (ConversationSync.conversation_id == None)  # noqa: E711
                )
            )
            sync_records = result.scalars().all()

            logger.debug(f"Found {len(sync_records)} ConversationSync records to process")

            success_count = 0
            error_count = 0

            for sync_record in sync_records:
                try:
                    success = await sync_conversation(sync_record, session, debug=debug)
                    if success:
                        success_count += 1
                    else:
                        error_count += 1
                except Exception:
                    logger.exception(f"Error processing ConversationSync {sync_record.id}")
                    error_count += 1

            logger.info(f"Sync job completed. Success: {success_count}, Errors: {error_count}")

    except Exception:
        logger.exception("Error in sync_all_conversations")


async def sync_data_job() -> None:
    """Run the data synchronization job (catalog, WordPress, transform, and storage build)."""
    logger.info("Starting scheduled data sync job")

    try:
        # 1. Sync WordPress data
        logger.info("Running WordPress sync")
        await asyncio.to_thread(wp_main)

        # 2. Transform WordPress data
        logger.info("Transforming WordPress data")
        transform_wp_main()

        # 3. Build chatbot storage (this is async)
        logger.info("Building chatbot storage")
        await build_search_db(get_azure_embedding_embedder(), force_rebuild=False, dry_run=False)

        # 4. Vacuum database
        logger.info("Running database vacuum")
        async with engine.execution_options(isolation_level="AUTOCOMMIT").connect() as conn:
            await conn.execute(text("VACUUM FULL"))
        logger.info("Database vacuum completed")

        logger.info("Data sync job completed successfully")

    except Exception:
        logger.exception("Error in sync_data_job")
