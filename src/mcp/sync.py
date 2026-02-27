"""Sync logic with file-based locking."""

import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from filelock import FileLock, Timeout

from src.extraction import TextExtractor
from src.storage import Storage, StorageMeta
from src.telegram import TelegramClient
from src.telegram.models import MediaType, Message


class SyncManager:
    """Manages chat synchronization with file-based locking."""

    def __init__(
        self,
        telegram: TelegramClient,
        storage: Storage,
        data_path: Path,
    ) -> None:
        self._telegram = telegram
        self._storage = storage
        self._data_path = data_path
        self._extractor = TextExtractor()
        self._media_path = data_path / "media"

    def _get_lock_path(self, chat_id: int) -> Path:
        """Get path to sync lock file."""
        chat_path = self._storage.get_chat_path(chat_id)
        chat_path.mkdir(parents=True, exist_ok=True)
        return chat_path / ".sync.lock"

    async def sync_chat(
        self,
        chat_id: int,
        months: int = 3,
        timeout: float = 1.0,
        force: bool = False,
    ) -> dict:
        """
        Synchronize chat with Telegram.

        Args:
            chat_id: Chat ID to sync
            months: How many months back to sync
            timeout: Lock timeout in seconds
            force: If True, delete all existing data and resync from scratch

        Returns:
            dict with status, messages_synced, blocks_created, duration_seconds

        Raises:
            RuntimeError: If sync already in progress
        """
        lock_path = self._get_lock_path(chat_id)
        lock = FileLock(lock_path)

        try:
            with lock.acquire(timeout=timeout):
                if force:
                    await self._clear_chat_data(chat_id)
                return await self._do_sync(chat_id, months)
        except Timeout:
            raise RuntimeError("Sync already in progress")

    async def _clear_chat_data(self, chat_id: int) -> None:
        """Delete all blocks and meta for a chat."""
        import shutil

        chat_path = self._storage.get_chat_path(chat_id)
        if chat_path.exists():
            shutil.rmtree(chat_path)
        chat_path.mkdir(parents=True, exist_ok=True)

    async def _do_sync(self, chat_id: int, months: int) -> dict:
        """Perform actual sync."""
        start_time = time.time()

        # Calculate date range
        max_date = datetime.now(UTC)
        min_date = max_date - timedelta(days=months * 30)

        # Get chat info
        chat_info = await self._telegram.get_chat_info(chat_id)

        # Get existing meta
        meta = await self._storage.get_meta(chat_id)

        # Determine what to fetch
        offset_id = None
        if meta:
            offset_id = meta.newest_msg_id

        # Fetch messages
        all_messages: list[Message] = []
        while True:
            messages = await self._telegram.get_messages(
                chat_id,
                limit=100,
                offset_id=offset_id,
                min_date=min_date,
                max_date=max_date,
            )

            if not messages:
                break

            all_messages.extend(messages)
            offset_id = messages[-1].id

            # Safety limit
            if len(all_messages) > 10000:
                break

        # Extract text from media (OCR)
        if all_messages:
            all_messages = await self._extract_media_texts(chat_id, all_messages)

        # Write to storage
        if all_messages:
            await self._storage.write_messages(chat_id, chat_info.name, all_messages)

        # Update meta
        blocks = await self._storage.list_blocks(chat_id)

        if all_messages:
            oldest_msg = min(all_messages, key=lambda m: m.date)
            newest_msg = max(all_messages, key=lambda m: m.date)

            new_meta = StorageMeta(
                chat_id=chat_id,
                chat_name=chat_info.name,
                chat_type=chat_info.type.value,
                oldest_msg_id=oldest_msg.id,
                newest_msg_id=newest_msg.id,
                oldest_date=oldest_msg.date,
                newest_date=newest_msg.date,
                last_sync=datetime.now(UTC),
                total_messages=len(all_messages) + (meta.total_messages if meta else 0),
            )
            await self._storage.update_meta(chat_id, new_meta)

        duration = time.time() - start_time

        return {
            "status": "success",
            "messages_synced": len(all_messages),
            "blocks_created": len(blocks),
            "duration_seconds": round(duration, 2),
        }

    async def ensure_data(self, chat_id: int, months: int = 3) -> bool:
        """
        Ensure chat has data, sync if needed (lazy load).

        Returns:
            True if data exists or was synced successfully.
        """
        meta = await self._storage.get_meta(chat_id)
        if meta:
            return True

        try:
            await self.sync_chat(chat_id, months)
            return True
        except Exception:
            return False

    async def _extract_media_texts(
        self, chat_id: int, messages: list[Message]
    ) -> list[Message]:
        """Extract text from media in messages using OCR."""
        self._media_path.mkdir(parents=True, exist_ok=True)
        result = []

        for msg in messages:
            # Only process photos and documents
            if msg.media_type not in (MediaType.PHOTO, MediaType.DOCUMENT):
                result.append(msg)
                continue

            # Try to download and extract text
            try:
                path = await self._telegram.download_media(
                    chat_id, msg.id, str(self._media_path)
                )
                if not path:
                    result.append(msg)
                    continue

                file_path = Path(path)
                if not self._extractor.can_extract(file_path):
                    result.append(msg)
                    continue

                extracted = self._extractor.extract(file_path)
                if extracted:
                    # Append extracted text to message
                    new_text = msg.text
                    if new_text:
                        new_text += "\n\n"
                    new_text += f"[Extracted from {file_path.name}]\n{extracted}"
                    msg = msg.model_copy(update={"text": new_text})
                    # Cleanup: delete media file after successful extraction
                    file_path.unlink(missing_ok=True)

                result.append(msg)
            except Exception:
                # On error, keep original message
                result.append(msg)

        return result
