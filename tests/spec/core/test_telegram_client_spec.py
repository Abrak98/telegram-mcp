"""
Spec tests for TelegramClient.
Based on specs/core/telegram_client.technical.md
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.telegram import ChatType, Dialog, MediaType, Message, TelegramClient, TelegramConfig


class TestTelegramConfig:
    def test_from_env_loads_values(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text(
            "TELEGRAM_API_ID=12345\n"
            "TELEGRAM_API_HASH=abc123hash\n"
            "TELEGRAM_PHONE=+1234567890\n"
        )

        config = TelegramConfig.from_env(env_file)

        assert config.api_id == 12345
        assert config.api_hash == "abc123hash"
        assert config.phone == "+1234567890"
        assert config.session_path == Path("data/session")

    def test_from_env_missing_api_id_raises(self, tmp_path: Path, monkeypatch) -> None:
        # Clear any existing env vars
        monkeypatch.delenv("TELEGRAM_API_ID", raising=False)
        monkeypatch.delenv("TELEGRAM_API_HASH", raising=False)
        monkeypatch.delenv("TELEGRAM_PHONE", raising=False)

        env_file = tmp_path / ".env"
        env_file.write_text(
            "TELEGRAM_API_HASH=abc123hash\n" "TELEGRAM_PHONE=+1234567890\n"
        )

        with pytest.raises(ValueError, match="TELEGRAM_API_ID"):
            TelegramConfig.from_env(env_file)

    def test_from_env_custom_session_path(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text(
            "TELEGRAM_API_ID=12345\n"
            "TELEGRAM_API_HASH=abc123hash\n"
            "TELEGRAM_PHONE=+1234567890\n"
            "TELEGRAM_SESSION_PATH=/custom/path/session\n"
        )

        config = TelegramConfig.from_env(env_file)

        assert config.session_path == Path("/custom/path/session")


class TestTelegramClientConnection:
    """TC1, TC2: Connection tests."""

    def test_client_created_not_connected(self) -> None:
        config = TelegramConfig(
            api_id=12345, api_hash="abc", phone="+1234567890"
        )
        with patch("src.telegram.client.TelethonClient"):
            client = TelegramClient(config)
            assert client._connected is False

    @pytest.mark.asyncio
    async def test_connect_sets_connected_true(self) -> None:
        """TC1: connect() sets _connected = True."""
        config = TelegramConfig(
            api_id=12345, api_hash="abc", phone="+1234567890"
        )
        with patch("src.telegram.client.TelethonClient") as mock_telethon:
            mock_instance = MagicMock()
            mock_instance.start = AsyncMock()
            mock_telethon.return_value = mock_instance

            client = TelegramClient(config)
            await client.connect()

            assert client._connected is True
            mock_instance.start.assert_called_once_with(phone="+1234567890")

    @pytest.mark.asyncio
    async def test_get_dialogs_without_connection_raises(self) -> None:
        """TC2: get_dialogs() without connection raises RuntimeError."""
        config = TelegramConfig(
            api_id=12345, api_hash="abc", phone="+1234567890"
        )
        with patch("src.telegram.client.TelethonClient"):
            client = TelegramClient(config)

            with pytest.raises(RuntimeError, match="Not connected"):
                await client.get_dialogs()

    @pytest.mark.asyncio
    async def test_get_messages_without_connection_raises(self) -> None:
        """TC2: get_messages() without connection raises RuntimeError."""
        config = TelegramConfig(
            api_id=12345, api_hash="abc", phone="+1234567890"
        )
        with patch("src.telegram.client.TelethonClient"):
            client = TelegramClient(config)

            with pytest.raises(RuntimeError, match="Not connected"):
                await client.get_messages(123)

    @pytest.mark.asyncio
    async def test_disconnect_sets_connected_false(self) -> None:
        config = TelegramConfig(
            api_id=12345, api_hash="abc", phone="+1234567890"
        )
        with patch("src.telegram.client.TelethonClient") as mock_telethon:
            mock_instance = MagicMock()
            mock_instance.start = AsyncMock()
            mock_instance.disconnect = AsyncMock()
            mock_telethon.return_value = mock_instance

            client = TelegramClient(config)
            await client.connect()
            await client.disconnect()

            assert client._connected is False


class TestGetDialogs:
    """TC3: get_dialogs() tests."""

    @pytest.mark.asyncio
    async def test_get_dialogs_returns_list_of_dialog(self) -> None:
        """TC3: get_dialogs() returns list of Dialog objects."""
        config = TelegramConfig(
            api_id=12345, api_hash="abc", phone="+1234567890"
        )

        mock_user = MagicMock()
        mock_user.__class__.__name__ = "User"

        mock_dialog = MagicMock()
        mock_dialog.id = 123
        mock_dialog.name = "Test Chat"
        mock_dialog.entity = mock_user
        mock_dialog.unread_count = 5

        async def mock_iter_dialogs():
            yield mock_dialog

        with patch("src.telegram.client.TelethonClient") as mock_telethon:
            mock_instance = MagicMock()
            mock_instance.start = AsyncMock()
            mock_instance.iter_dialogs = mock_iter_dialogs
            mock_telethon.return_value = mock_instance

            with patch("src.telegram.client.User", mock_user.__class__):
                client = TelegramClient(config)
                await client.connect()
                dialogs = await client.get_dialogs()

                assert isinstance(dialogs, list)
                assert len(dialogs) == 1
                assert isinstance(dialogs[0], Dialog)
                assert dialogs[0].id == 123
                assert dialogs[0].name == "Test Chat"


class TestGetMessages:
    """TC4-TC8: get_messages() tests."""

    @pytest.mark.asyncio
    async def test_get_messages_respects_limit(self) -> None:
        """TC4: get_messages() respects limit parameter."""
        config = TelegramConfig(
            api_id=12345, api_hash="abc", phone="+1234567890"
        )

        mock_msg = MagicMock()
        mock_msg.id = 1
        mock_msg.date = datetime(2024, 1, 15, 14, 30)
        mock_msg.sender_id = 100
        mock_msg.sender = None
        mock_msg.text = "Hello"
        mock_msg.reply_to = None
        mock_msg.forward = None
        mock_msg.media = None

        async def mock_iter_messages(chat_id, **kwargs):
            assert kwargs.get("limit") == 10
            yield mock_msg

        with patch("src.telegram.client.TelethonClient") as mock_telethon:
            mock_instance = MagicMock()
            mock_instance.start = AsyncMock()
            mock_instance.iter_messages = mock_iter_messages
            mock_telethon.return_value = mock_instance

            client = TelegramClient(config)
            await client.connect()
            messages = await client.get_messages(123, limit=10)

            assert len(messages) <= 10
            assert all(isinstance(m, Message) for m in messages)


class TestGetMessageById:
    """TC9, TC10: get_message_by_id() tests."""

    @pytest.mark.asyncio
    async def test_get_message_by_id_returns_message(self) -> None:
        """TC9: get_message_by_id() returns Message when found."""
        config = TelegramConfig(
            api_id=12345, api_hash="abc", phone="+1234567890"
        )

        mock_msg = MagicMock()
        mock_msg.id = 12345
        mock_msg.date = datetime(2024, 1, 15, 14, 30)
        mock_msg.sender_id = 100
        mock_msg.sender = None
        mock_msg.text = "Test message"
        mock_msg.reply_to = None
        mock_msg.forward = None
        mock_msg.media = None

        with patch("src.telegram.client.TelethonClient") as mock_telethon:
            mock_instance = MagicMock()
            mock_instance.start = AsyncMock()
            mock_instance.get_messages = AsyncMock(return_value=mock_msg)
            mock_telethon.return_value = mock_instance

            client = TelegramClient(config)
            await client.connect()
            message = await client.get_message_by_id(123, 12345)

            assert message is not None
            assert message.id == 12345

    @pytest.mark.asyncio
    async def test_get_message_by_id_returns_none_when_not_found(self) -> None:
        """TC10: get_message_by_id() returns None when not found."""
        config = TelegramConfig(
            api_id=12345, api_hash="abc", phone="+1234567890"
        )

        with patch("src.telegram.client.TelethonClient") as mock_telethon:
            mock_instance = MagicMock()
            mock_instance.start = AsyncMock()
            mock_instance.get_messages = AsyncMock(return_value=None)
            mock_telethon.return_value = mock_instance

            client = TelegramClient(config)
            await client.connect()
            message = await client.get_message_by_id(123, 99999999)

            assert message is None


class TestGetChatInfo:
    """TC11, TC12: get_chat_info() tests."""

    @pytest.mark.asyncio
    async def test_get_chat_info_returns_dialog(self) -> None:
        """TC11: get_chat_info() returns Dialog with correct info."""
        config = TelegramConfig(
            api_id=12345, api_hash="abc", phone="+1234567890"
        )

        mock_entity = MagicMock()
        mock_entity.title = "Test Group"

        mock_dialog = MagicMock()
        mock_dialog.id = 123
        mock_dialog.unread_count = 3

        with patch("src.telegram.client.TelethonClient") as mock_telethon:
            mock_instance = MagicMock()
            mock_instance.start = AsyncMock()
            mock_instance.get_entity = AsyncMock(return_value=mock_entity)
            mock_instance.get_dialogs = AsyncMock(return_value=[mock_dialog])
            mock_telethon.return_value = mock_instance

            with patch("src.telegram.client.Channel", MagicMock):
                client = TelegramClient(config)
                await client.connect()
                info = await client.get_chat_info(123)

                assert info.id == 123
                assert info.name == "Test Group"

    @pytest.mark.asyncio
    async def test_get_chat_info_raises_when_not_found(self) -> None:
        """TC12: get_chat_info() raises ValueError when chat not found."""
        config = TelegramConfig(
            api_id=12345, api_hash="abc", phone="+1234567890"
        )

        with patch("src.telegram.client.TelethonClient") as mock_telethon:
            mock_instance = MagicMock()
            mock_instance.start = AsyncMock()
            mock_instance.get_entity = AsyncMock(
                side_effect=ValueError("Not found")
            )
            mock_telethon.return_value = mock_instance

            client = TelegramClient(config)
            await client.connect()

            with pytest.raises(ValueError, match="not found"):
                await client.get_chat_info(99999)


class TestMessageContent:
    """TC7, TC8: Message content tests."""

    def test_message_with_reply_to(self) -> None:
        """TC7: Message with reply_to_msg_id."""
        msg = Message(
            id=1,
            date=datetime.now(),
            sender_id=100,
            sender_name="User",
            text="Reply text",
            reply_to_msg_id=123,
            forward_from=None,
            media_type=MediaType.NONE,
        )
        assert msg.reply_to_msg_id == 123

    def test_message_with_media_has_empty_text(self) -> None:
        """TC8: Media message has empty text and correct media_type."""
        msg = Message(
            id=1,
            date=datetime.now(),
            sender_id=100,
            sender_name="User",
            text="",
            reply_to_msg_id=None,
            forward_from=None,
            media_type=MediaType.PHOTO,
        )
        assert msg.text == ""
        assert msg.media_type == MediaType.PHOTO


class TestModels:
    """Model validation tests."""

    def test_chat_type_values(self) -> None:
        assert ChatType.USER.value == "user"
        assert ChatType.GROUP.value == "group"
        assert ChatType.CHANNEL.value == "channel"

    def test_media_type_values(self) -> None:
        assert MediaType.NONE.value == "none"
        assert MediaType.PHOTO.value == "photo"
        assert MediaType.VIDEO.value == "video"
        assert MediaType.DOCUMENT.value == "document"
        assert MediaType.VOICE.value == "voice"
        assert MediaType.STICKER.value == "sticker"
        assert MediaType.OTHER.value == "other"

    def test_dialog_model(self) -> None:
        dialog = Dialog(
            id=123, name="Test", type=ChatType.GROUP, unread_count=5
        )
        assert dialog.id == 123
        assert dialog.name == "Test"
        assert dialog.type == ChatType.GROUP
        assert dialog.unread_count == 5

    def test_message_model(self) -> None:
        msg = Message(
            id=1,
            date=datetime(2024, 1, 15, 14, 30),
            sender_id=100,
            sender_name="John",
            text="Hello",
            reply_to_msg_id=None,
            forward_from=None,
            media_type=MediaType.NONE,
        )
        assert msg.id == 1
        assert msg.sender_name == "John"
        assert msg.text == "Hello"
