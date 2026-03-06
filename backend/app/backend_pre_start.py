import asyncio
import logging

from sqlalchemy import select
from tenacity import after_log, before_log, retry, stop_after_attempt, wait_fixed

from app.core.db import get_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

max_tries = 60 * 5  # 5 minutes
wait_seconds = 1


@retry(
    stop=stop_after_attempt(max_tries),
    wait=wait_fixed(wait_seconds),
    before=before_log(logger, logging.INFO),
    after=after_log(logger, logging.WARNING),
)
async def init() -> None:
    try:
        async with get_session() as session:
            # Try to create session to check if DB is awake
            await session.execute(select(1))
    except Exception:
        logger.exception("Database connection check failed")
        raise


async def main() -> None:
    logger.info("Initializing service")
    await init()


if __name__ == "__main__":
    asyncio.run(main())
