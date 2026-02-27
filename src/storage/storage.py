import json
from collections import defaultdict
from pathlib import Path

import aiofiles

from src.telegram.models import Message

from .config import load_chat_configs
from .models import ChatConfig, StorageMeta
from .parser import (
    block_name_to_date,
    date_to_block_name,
    format_block_header,
    format_message,
    parse_block_header,
    parse_message_line,
)


class Storage:
    """Абстракция хранения сообщений в файловой системе."""

    def __init__(self, data_path: Path) -> None:
        """
        Инициализация storage.

        Args:
            data_path: путь к директории data/
        """
        self._data_path = data_path
        self._data_path.mkdir(parents=True, exist_ok=True)

        config_path = data_path / "chats.toml"
        self._chat_configs = load_chat_configs(config_path)

    def get_chat_config(self, chat_id: int) -> ChatConfig | None:
        """Получить конфиг чата по ID. None если не в whitelist."""
        return self._chat_configs.get(chat_id)

    def list_chat_configs(self) -> list[ChatConfig]:
        """Список всех чатов из whitelist."""
        return list(self._chat_configs.values())

    def get_chat_path(self, chat_id: int) -> Path:
        """Путь к директории чата."""
        return self._data_path / "chats" / str(chat_id)

    def get_block_path(self, chat_id: int, block: str) -> Path:
        """Путь к файлу блока."""
        return self.get_chat_path(chat_id) / f"{block}.md"

    def get_media_path(self, chat_id: int, msg_id: int, filename: str) -> Path:
        """Путь к медиа файлу."""
        return self.get_chat_path(chat_id) / "media" / f"{msg_id}_{filename}"

    def _get_meta_path(self, chat_id: int) -> Path:
        """Путь к meta.json."""
        return self.get_chat_path(chat_id) / "meta.json"

    async def write_messages(
        self, chat_id: int, chat_name: str, messages: list[Message]
    ) -> int:
        """
        Записать сообщения в часовые блоки.

        Returns:
            Количество записанных сообщений.
        """
        if not messages:
            return 0

        chat_path = self.get_chat_path(chat_id)
        chat_path.mkdir(parents=True, exist_ok=True)

        # Группировка по блокам
        blocks: dict[str, list[Message]] = defaultdict(list)
        for msg in messages:
            block_name = date_to_block_name(msg.date)
            blocks[block_name].append(msg)

        written = 0
        for block_name, block_messages in blocks.items():
            block_path = self.get_block_path(chat_id, block_name)
            block_date = block_name_to_date(block_name)

            # Сортировка по времени
            block_messages.sort(key=lambda m: m.date)

            # Формирование контента
            if block_path.exists():
                # Append к существующему
                lines = [format_message(msg, block_date) for msg in block_messages]
                content = "\n" + "\n".join(lines) + "\n"
                async with aiofiles.open(block_path, "a", encoding="utf-8") as f:
                    await f.write(content)
            else:
                # Новый файл
                header = format_block_header(block_date, chat_name)
                lines = [format_message(msg, block_date) for msg in block_messages]
                content = header + "\n" + "\n".join(lines) + "\n"
                async with aiofiles.open(block_path, "w", encoding="utf-8") as f:
                    await f.write(content)

            written += len(block_messages)

        return written

    async def read_block(self, chat_id: int, block: str) -> list[Message]:
        """
        Прочитать все сообщения из блока.

        Returns:
            Список Message, пустой если блок не существует.
        """
        block_path = self.get_block_path(chat_id, block)
        if not block_path.exists():
            return []

        async with aiofiles.open(block_path, encoding="utf-8") as f:
            content = await f.read()

        lines = content.strip().split("\n")
        messages = []

        block_date = block_name_to_date(block)

        for line in lines:
            if line.startswith("#"):
                # Header line
                parsed = parse_block_header(line)
                if parsed:
                    block_date, _ = parsed
                continue

            msg = parse_message_line(line, block_date)
            if msg:
                messages.append(msg)

        return messages

    async def read_message(self, chat_id: int, msg_id: int) -> Message | None:
        """
        Найти сообщение по ID во всех блоках чата.

        Note:
            В текущей реализации ID не сохраняется в markdown,
            поэтому этот метод не может найти сообщение по ID.
            Нужен индекс или хранение ID в файле.
        """
        # TODO: Реализовать когда будет индекс или хранение ID
        return None

    async def list_blocks(self, chat_id: int) -> list[str]:
        """
        Список всех блоков чата.

        Returns:
            Список имён блоков, отсортированных по дате DESC.
        """
        chat_path = self.get_chat_path(chat_id)
        if not chat_path.exists():
            return []

        blocks = []
        for path in chat_path.glob("*.md"):
            block_name = path.stem  # без .md
            blocks.append(block_name)

        # Сортировка по дате DESC
        blocks.sort(reverse=True)
        return blocks

    async def get_meta(self, chat_id: int) -> StorageMeta | None:
        """Получить метаданные чата."""
        meta_path = self._get_meta_path(chat_id)
        if not meta_path.exists():
            return None

        async with aiofiles.open(meta_path, encoding="utf-8") as f:
            content = await f.read()

        data = json.loads(content)
        return StorageMeta(**data)

    async def update_meta(self, chat_id: int, meta: StorageMeta) -> None:
        """Записать/обновить meta.json чата."""
        chat_path = self.get_chat_path(chat_id)
        chat_path.mkdir(parents=True, exist_ok=True)

        meta_path = self._get_meta_path(chat_id)
        content = meta.model_dump_json(indent=2)

        async with aiofiles.open(meta_path, "w", encoding="utf-8") as f:
            await f.write(content)
