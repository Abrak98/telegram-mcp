from datetime import UTC, datetime

from telethon import TelegramClient as TelethonClient
from telethon.tl.types import (
    Channel,
    Chat,
    Document,
    MessageMediaDocument,
    MessageMediaPhoto,
    User,
)

from .config import TelegramConfig
from .models import ChatType, Dialog, MediaType, Message


class TelegramClient:
    def __init__(self, config: TelegramConfig) -> None:
        self._config = config
        self._connected = False
        self._client = TelethonClient(
            str(config.session_path),
            config.api_id,
            config.api_hash,
        )

    def _require_connected(self) -> None:
        if not self._connected:
            raise RuntimeError("Not connected")

    async def connect(self) -> None:
        await self._client.start(phone=self._config.phone)
        self._connected = True

    async def disconnect(self) -> None:
        await self._client.disconnect()
        self._connected = False

    async def get_dialogs(self) -> list[Dialog]:
        self._require_connected()
        dialogs = []
        async for dialog in self._client.iter_dialogs():
            chat_type = self._get_chat_type(dialog.entity)
            dialogs.append(
                Dialog(
                    id=dialog.id,
                    name=dialog.name or "",
                    type=chat_type,
                    unread_count=dialog.unread_count,
                )
            )
        return dialogs

    async def get_messages(
        self,
        chat_id: int,
        *,
        limit: int = 100,
        offset_id: int | None = None,
        min_date: datetime | None = None,
        max_date: datetime | None = None,
    ) -> list[Message]:
        self._require_connected()

        kwargs: dict = {"limit": limit}
        if offset_id is not None:
            kwargs["offset_id"] = offset_id
        if min_date is not None:
            kwargs["offset_date"] = min_date
        if max_date is not None:
            kwargs["offset_date"] = max_date

        messages = []
        async for msg in self._client.iter_messages(chat_id, **kwargs):
            msg_date = msg.date if msg.date.tzinfo else msg.date.replace(tzinfo=UTC)
            if min_date and msg_date < min_date:
                continue
            if max_date and msg_date > max_date:
                continue

            messages.append(self._convert_message(msg))

        return messages

    async def get_message_by_id(self, chat_id: int, message_id: int) -> Message | None:
        self._require_connected()
        msg = await self._client.get_messages(chat_id, ids=message_id)
        if msg is None:
            return None
        return self._convert_message(msg)

    async def get_chat_info(self, chat_id: int) -> Dialog:
        self._require_connected()
        try:
            entity = await self._client.get_entity(chat_id)
        except ValueError as e:
            raise ValueError(f"Chat {chat_id} not found") from e

        name = self._get_entity_name(entity)
        chat_type = self._get_chat_type(entity)

        dialog = await self._client.get_dialogs()
        unread = 0
        for d in dialog:
            if d.id == chat_id:
                unread = d.unread_count
                break

        return Dialog(id=chat_id, name=name, type=chat_type, unread_count=unread)

    def _convert_message(self, msg) -> Message:
        sender_id = msg.sender_id
        sender_name = "Unknown"
        if msg.sender:
            sender_name = self._get_entity_name(msg.sender)

        reply_to_msg_id = None
        if msg.reply_to:
            reply_to_msg_id = msg.reply_to.reply_to_msg_id

        forward_from = None
        if msg.forward:
            if msg.forward.from_name:
                forward_from = msg.forward.from_name
            elif msg.forward.sender:
                forward_from = self._get_entity_name(msg.forward.sender)
            elif msg.forward.chat:
                forward_from = self._get_entity_name(msg.forward.chat)

        media_type = self._get_media_type(msg.media)

        return Message(
            id=msg.id,
            date=msg.date.replace(tzinfo=None),
            sender_id=sender_id,
            sender_name=sender_name,
            text=msg.text or "",
            reply_to_msg_id=reply_to_msg_id,
            forward_from=forward_from,
            media_type=media_type,
        )

    @staticmethod
    def _get_chat_type(entity) -> ChatType:
        if isinstance(entity, User):
            return ChatType.USER
        elif isinstance(entity, Chat):
            return ChatType.GROUP
        elif isinstance(entity, Channel):
            return ChatType.CHANNEL
        return ChatType.GROUP

    @staticmethod
    def _get_entity_name(entity) -> str:
        if isinstance(entity, User):
            parts = [entity.first_name or "", entity.last_name or ""]
            return " ".join(p for p in parts if p).strip() or "Unknown"
        elif hasattr(entity, "title"):
            return entity.title or "Unknown"
        return "Unknown"

    @staticmethod
    def _get_media_type(media) -> MediaType:
        if media is None:
            return MediaType.NONE
        if isinstance(media, MessageMediaPhoto):
            return MediaType.PHOTO
        if isinstance(media, MessageMediaDocument):
            doc = media.document
            if isinstance(doc, Document):
                mime = doc.mime_type or ""
                if mime.startswith("video/"):
                    return MediaType.VIDEO
                if mime.startswith("audio/"):
                    return MediaType.VOICE
                if "sticker" in mime or any(
                    hasattr(a, "stickerset") for a in (doc.attributes or [])
                ):
                    return MediaType.STICKER
            return MediaType.DOCUMENT
        return MediaType.OTHER

    async def download_media(
        self,
        chat_id: int,
        msg_id: int,
        download_path: str,
    ) -> str | None:
        """Download media from message."""
        self._require_connected()

        msg = await self._client.get_messages(chat_id, ids=msg_id)
        if not msg or not msg.media:
            return None

        path = await self._client.download_media(msg, download_path)
        return str(path) if path else None

    async def resolve_username(self, username: str) -> tuple[int, str, ChatType]:
        """Resolve @username to chat_id, name, and type."""
        self._require_connected()
        # Strip @ if present
        username = username.lstrip("@")
        entity = await self._client.get_entity(username)
        name = self._get_entity_name(entity)
        chat_type = self._get_chat_type(entity)
        return entity.id, name, chat_type
