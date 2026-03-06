from collections.abc import Iterable

from app.models import Message


def format_transcript(messages: Iterable[Message], *, user_label: str) -> str:
    lines: list[str] = []
    for message in messages:
        role = user_label if message.role == "user" else "Assistant"
        lines.append(f"{role}: {message.content}")
    return "\n\n".join(lines)


def build_transcript(messages: Iterable[Message], *, is_internal: bool) -> str:
    user_label = "Staff" if is_internal else "User"
    return format_transcript(messages, user_label=user_label)
