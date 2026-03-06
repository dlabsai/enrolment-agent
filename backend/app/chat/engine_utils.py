from datetime import datetime, timedelta, timezone
from typing import Any

type MessageDict = dict[str, Any]


def get_assistant_message_content(message: dict[str, Any]) -> str:
    return message.get(
        "content",
        "[The LLM provider returned an empty assistant message. "
        "This could be due to the provider's guardrails.]",
    )


def get_current_date_gmt_minus_4() -> str:
    return datetime.now(timezone(timedelta(hours=-4))).strftime("%d %b %Y")
