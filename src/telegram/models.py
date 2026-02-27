from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class ChatType(Enum):
    USER = "user"
    GROUP = "group"
    CHANNEL = "channel"


class MediaType(Enum):
    NONE = "none"
    PHOTO = "photo"
    VIDEO = "video"
    DOCUMENT = "document"
    VOICE = "voice"
    STICKER = "sticker"
    OTHER = "other"


class Dialog(BaseModel):
    id: int
    name: str
    type: ChatType
    unread_count: int


class Message(BaseModel):
    id: int
    date: datetime
    sender_id: int | None
    sender_name: str
    text: str
    reply_to_msg_id: int | None
    forward_from: str | None
    media_type: MediaType
