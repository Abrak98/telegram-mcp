"""Spec tests for Storage module."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.storage import Storage, StorageMeta
from src.telegram.models import MediaType, Message


class TestChatConfig:
    """Tests for chat config loading."""

    def test_load_configs_from_toml(self, tmp_path: Path) -> None:
        """TC1: Загрузка конфига."""
        data_path = tmp_path / "data"
        data_path.mkdir()

        config_content = """
[personal.john]
id = 123456789
depth_months = 3
description = "Джон, коллега backend"

[group.clickhouse]
id = -100111222333
depth_months = 12
description = "ClickHouse RU"
"""
        (data_path / "chats.toml").write_text(config_content)

        storage = Storage(data_path)
        configs = storage.list_chat_configs()

        assert len(configs) == 2

    def test_chat_not_in_whitelist(self, tmp_path: Path) -> None:
        """TC2: Чат не в whitelist."""
        data_path = tmp_path / "data"
        data_path.mkdir()
        (data_path / "chats.toml").write_text("")

        storage = Storage(data_path)
        config = storage.get_chat_config(999)

        assert config is None

    def test_chat_config_fields(self, tmp_path: Path) -> None:
        """Проверка полей ChatConfig."""
        data_path = tmp_path / "data"
        data_path.mkdir()

        config_content = """
[personal.john]
id = 123456789
depth_months = 3
description = "Test description"
"""
        (data_path / "chats.toml").write_text(config_content)

        storage = Storage(data_path)
        config = storage.get_chat_config(123456789)

        assert config is not None
        assert config.id == 123456789
        assert config.alias == "john"
        assert config.type == "personal"
        assert config.depth_months == 3
        assert config.description == "Test description"


class TestWriteMessages:
    """Tests for writing messages."""

    @pytest.fixture
    def storage(self, tmp_path: Path) -> Storage:
        data_path = tmp_path / "data"
        data_path.mkdir()
        (data_path / "chats.toml").write_text("")
        return Storage(data_path)

    @pytest.fixture
    def sample_messages(self) -> list[Message]:
        base_date = datetime(2024, 1, 15, 14, 0, tzinfo=UTC)
        return [
            Message(
                id=1,
                date=base_date.replace(minute=5),
                sender_id=100,
                sender_name="user1",
                text="First message",
                reply_to_msg_id=None,
                forward_from=None,
                media_type=MediaType.NONE,
            ),
            Message(
                id=2,
                date=base_date.replace(minute=30),
                sender_id=101,
                sender_name="user2",
                text="Second message",
                reply_to_msg_id=None,
                forward_from=None,
                media_type=MediaType.NONE,
            ),
            Message(
                id=3,
                date=base_date.replace(hour=15, minute=10),
                sender_id=102,
                sender_name="user3",
                text="Third message",
                reply_to_msg_id=None,
                forward_from=None,
                media_type=MediaType.NONE,
            ),
        ]

    @pytest.mark.asyncio
    async def test_write_creates_blocks(
        self, storage: Storage, sample_messages: list[Message]
    ) -> None:
        """TC3: Запись сообщений создаёт блоки."""
        chat_id = 123
        written = await storage.write_messages(chat_id, "Test Chat", sample_messages)

        assert written == 3

        blocks = await storage.list_blocks(chat_id)
        assert len(blocks) == 2
        assert "2024-01-15_14" in blocks
        assert "2024-01-15_15" in blocks

    @pytest.mark.asyncio
    async def test_write_empty_messages(self, storage: Storage) -> None:
        """Запись пустого списка."""
        written = await storage.write_messages(123, "Test", [])
        assert written == 0


class TestReadBlock:
    """Tests for reading blocks."""

    @pytest.fixture
    def storage(self, tmp_path: Path) -> Storage:
        data_path = tmp_path / "data"
        data_path.mkdir()
        (data_path / "chats.toml").write_text("")
        return Storage(data_path)

    @pytest.mark.asyncio
    async def test_read_block(self, storage: Storage) -> None:
        """TC4: Чтение блока."""
        chat_id = 123
        base_date = datetime(2024, 1, 15, 14, 0, tzinfo=UTC)
        messages = [
            Message(
                id=i,
                date=base_date.replace(minute=i * 10),
                sender_id=100 + i,
                sender_name=f"user{i}",
                text=f"Message {i}",
                reply_to_msg_id=None,
                forward_from=None,
                media_type=MediaType.NONE,
            )
            for i in range(5)
        ]

        await storage.write_messages(chat_id, "Test Chat", messages)
        read_messages = await storage.read_block(chat_id, "2024-01-15_14")

        assert len(read_messages) == 5

    @pytest.mark.asyncio
    async def test_read_nonexistent_block(self, storage: Storage) -> None:
        """TC5: Чтение несуществующего блока."""
        messages = await storage.read_block(123, "2099-01-01_00")
        assert messages == []


class TestListBlocks:
    """Tests for listing blocks."""

    @pytest.fixture
    def storage(self, tmp_path: Path) -> Storage:
        data_path = tmp_path / "data"
        data_path.mkdir()
        (data_path / "chats.toml").write_text("")
        return Storage(data_path)

    @pytest.mark.asyncio
    async def test_list_blocks_sorted(self, storage: Storage) -> None:
        """TC6: Список блоков отсортирован."""
        chat_id = 123

        # Create messages in different hours
        messages = []
        for hour in [14, 15, 10]:  # Out of order
            date = datetime(2024, 1, 15 if hour != 10 else 16, hour, 0, tzinfo=UTC)
            messages.append(
                Message(
                    id=hour,
                    date=date,
                    sender_id=100,
                    sender_name="user",
                    text=f"Message at {hour}",
                    reply_to_msg_id=None,
                    forward_from=None,
                    media_type=MediaType.NONE,
                )
            )

        await storage.write_messages(chat_id, "Test", messages)
        blocks = await storage.list_blocks(chat_id)

        # Should be sorted DESC
        assert blocks == ["2024-01-16_10", "2024-01-15_15", "2024-01-15_14"]


class TestParser:
    """Tests for message parsing."""

    @pytest.fixture
    def storage(self, tmp_path: Path) -> Storage:
        data_path = tmp_path / "data"
        data_path.mkdir()
        (data_path / "chats.toml").write_text("")
        return Storage(data_path)

    @pytest.mark.asyncio
    async def test_parse_reply(self, storage: Storage) -> None:
        """TC7: Парсинг reply из markdown."""
        chat_id = 123
        date = datetime(2024, 1, 15, 14, 7, tzinfo=UTC)
        msg = Message(
            id=1,
            date=date,
            sender_id=100,
            sender_name="user",
            text="Reply text",
            reply_to_msg_id=1234,
            forward_from=None,
            media_type=MediaType.NONE,
        )

        await storage.write_messages(chat_id, "Test", [msg])
        read_msgs = await storage.read_block(chat_id, "2024-01-15_14")

        assert len(read_msgs) == 1
        assert read_msgs[0].reply_to_msg_id == 1234
        assert read_msgs[0].text == "Reply text"

    @pytest.mark.asyncio
    async def test_parse_forward(self, storage: Storage) -> None:
        """TC8: Парсинг forward из markdown."""
        chat_id = 123
        date = datetime(2024, 1, 15, 14, 12, tzinfo=UTC)
        msg = Message(
            id=1,
            date=date,
            sender_id=100,
            sender_name="user",
            text="Forward text",
            reply_to_msg_id=None,
            forward_from="Channel Name",
            media_type=MediaType.NONE,
        )

        await storage.write_messages(chat_id, "Test", [msg])
        read_msgs = await storage.read_block(chat_id, "2024-01-15_14")

        assert len(read_msgs) == 1
        assert read_msgs[0].forward_from == "Channel Name"
        assert read_msgs[0].text == "Forward text"

    @pytest.mark.asyncio
    async def test_parse_media(self, storage: Storage) -> None:
        """TC9: Парсинг медиа из markdown."""
        chat_id = 123
        date = datetime(2024, 1, 15, 14, 10, tzinfo=UTC)
        msg = Message(
            id=1,
            date=date,
            sender_id=100,
            sender_name="user",
            text="Photo caption",
            reply_to_msg_id=None,
            forward_from=None,
            media_type=MediaType.PHOTO,
        )

        await storage.write_messages(chat_id, "Test", [msg])
        read_msgs = await storage.read_block(chat_id, "2024-01-15_14")

        assert len(read_msgs) == 1
        assert read_msgs[0].media_type == MediaType.PHOTO
        assert read_msgs[0].text == "Photo caption"


class TestMeta:
    """Tests for metadata."""

    @pytest.fixture
    def storage(self, tmp_path: Path) -> Storage:
        data_path = tmp_path / "data"
        data_path.mkdir()
        (data_path / "chats.toml").write_text("")
        return Storage(data_path)

    @pytest.mark.asyncio
    async def test_meta_crud(self, storage: Storage) -> None:
        """TC10: Meta CRUD."""
        chat_id = 123
        meta = StorageMeta(
            chat_id=chat_id,
            chat_name="Test Chat",
            chat_type="group",
            oldest_msg_id=1000,
            newest_msg_id=5000,
            oldest_date=datetime(2024, 1, 1, tzinfo=UTC),
            newest_date=datetime(2024, 1, 15, 14, 30, tzinfo=UTC),
            last_sync=datetime(2024, 1, 15, 15, 0, tzinfo=UTC),
            total_messages=4000,
        )

        # Initially None
        assert await storage.get_meta(chat_id) is None

        # After update
        await storage.update_meta(chat_id, meta)
        read_meta = await storage.get_meta(chat_id)

        assert read_meta is not None
        assert read_meta.chat_id == chat_id
        assert read_meta.chat_name == "Test Chat"
        assert read_meta.total_messages == 4000


class TestAppend:
    """Tests for appending to existing blocks."""

    @pytest.fixture
    def storage(self, tmp_path: Path) -> Storage:
        data_path = tmp_path / "data"
        data_path.mkdir()
        (data_path / "chats.toml").write_text("")
        return Storage(data_path)

    @pytest.mark.asyncio
    async def test_append_to_existing_block(self, storage: Storage) -> None:
        """TC11: Append к существующему блоку."""
        chat_id = 123
        base_date = datetime(2024, 1, 15, 14, 0, tzinfo=UTC)

        # First write
        msg1 = Message(
            id=1,
            date=base_date.replace(minute=5),
            sender_id=100,
            sender_name="user1",
            text="First",
            reply_to_msg_id=None,
            forward_from=None,
            media_type=MediaType.NONE,
        )
        msg2 = Message(
            id=2,
            date=base_date.replace(minute=10),
            sender_id=101,
            sender_name="user2",
            text="Second",
            reply_to_msg_id=None,
            forward_from=None,
            media_type=MediaType.NONE,
        )
        await storage.write_messages(chat_id, "Test", [msg1, msg2])

        # Append
        msg3 = Message(
            id=3,
            date=base_date.replace(minute=15),
            sender_id=102,
            sender_name="user3",
            text="Third",
            reply_to_msg_id=None,
            forward_from=None,
            media_type=MediaType.NONE,
        )
        await storage.write_messages(chat_id, "Test", [msg3])

        # Read all
        messages = await storage.read_block(chat_id, "2024-01-15_14")
        assert len(messages) == 3


class TestTimezone:
    """Tests for timezone handling."""

    @pytest.fixture
    def storage(self, tmp_path: Path) -> Storage:
        data_path = tmp_path / "data"
        data_path.mkdir()
        (data_path / "chats.toml").write_text("")
        return Storage(data_path)

    @pytest.mark.asyncio
    async def test_utc_timezone(self, storage: Storage) -> None:
        """TC12: UTC timezone."""
        chat_id = 123
        date = datetime(2024, 1, 15, 14, 30, tzinfo=UTC)
        msg = Message(
            id=1,
            date=date,
            sender_id=100,
            sender_name="user",
            text="Test",
            reply_to_msg_id=None,
            forward_from=None,
            media_type=MediaType.NONE,
        )

        await storage.write_messages(chat_id, "Test", [msg])

        blocks = await storage.list_blocks(chat_id)
        assert "2024-01-15_14" in blocks

        # Check file content has UTC
        block_path = storage.get_block_path(chat_id, "2024-01-15_14")
        content = block_path.read_text()
        assert "UTC" in content
