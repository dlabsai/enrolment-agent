from dataclasses import dataclass


@dataclass
class SyncMessage:
    id: str
    role: str  # "user" or "assistant"
    content: str
    timestamp: str
