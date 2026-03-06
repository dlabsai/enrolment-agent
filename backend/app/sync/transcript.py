from app.sync.message import SyncMessage


def format_transcript(messages: list[SyncMessage]) -> str:
    transcript_lines: list[str] = []
    for msg in messages:
        role = msg.role.upper()
        content = msg.content
        timestamp = msg.timestamp
        transcript_lines.append(f"[{timestamp}]\n{role}: {content}")

    return "\n\n".join(transcript_lines)


def format_transcript_for_summary(messages: list[SyncMessage]) -> str:
    transcript_lines: list[str] = []
    for msg in messages:
        role = msg.role.upper()
        content = msg.content
        transcript_lines.append(f"{role}: {content}")

    return "\n\n".join(transcript_lines)
