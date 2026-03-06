import logging
from datetime import UTC, datetime
from pathlib import Path


def _get_logger() -> logging.Logger:
    logger = logging.getLogger("va")
    logger.setLevel(logging.INFO)

    uvicorn_logger = logging.getLogger("uvicorn")
    if uvicorn_logger.handlers:
        for handler in uvicorn_logger.handlers:
            logger.addHandler(handler)
        return logger

    console_formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    return logger


logger = _get_logger()


def current_time_utc() -> datetime:
    return datetime.now(UTC)


def ensure_dir(dir_path: Path) -> None:
    dir_path.mkdir(parents=True, exist_ok=True)


def configure_logfire() -> None:
    import os  # noqa: PLC0415

    import logfire  # noqa: PLC0415

    from app.otel import get_database_span_processor  # noqa: PLC0415

    logfire.configure(
        service_name="va",
        send_to_logfire="if-token-present",
        scrubbing=False,
        additional_span_processors=[get_database_span_processor()],
    )
    if os.getenv("LOGFIRE_INSTRUMENT_DB", "true").lower() == "true":
        logfire.instrument_psycopg()
        logfire.instrument_sqlalchemy()
