from datetime import datetime

from pydantic import BaseModel


class ChatConfig(BaseModel):
    """Конфигурация чата из chats.toml."""

    id: int
    alias: str
    type: str  # "personal", "group", "channel"
    depth_months: int
    description: str


class StorageMeta(BaseModel):
    """Метаданные чата из meta.json."""

    chat_id: int
    chat_name: str
    chat_type: str  # "user", "group", "channel"
    oldest_msg_id: int
    newest_msg_id: int
    oldest_date: datetime
    newest_date: datetime
    last_sync: datetime
    total_messages: int
