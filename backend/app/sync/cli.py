import asyncio
import logging
import sys

from app.scheduler import sync_conversations_job

logging.basicConfig(level=logging.INFO, format="%(message)s")

logger = logging.getLogger(__name__)


def main() -> int:
    logger.info("Manual conversation sync triggered")
    try:
        asyncio.run(sync_conversations_job(debug=True))
        logger.info("Conversation sync completed successfully")
    except Exception:
        logger.exception("Error during conversation sync")
        return 1
    else:
        return 0


if __name__ == "__main__":
    sys.exit(main())
