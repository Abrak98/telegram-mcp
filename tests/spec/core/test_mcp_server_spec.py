"""Spec tests for MCP Server module."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.mcp.responses import error_response, json_response, truncate
from src.mcp.server import TelegramMCPServer
from src.storage import Storage
from src.telegram.models import MediaType, Message


def make_message(
    id: int,
    text: str,
    date: datetime,
    sender: str = "user",
) -> Message:
    return Message(
        id=id,
        date=date,
        sender_id=100,
        sender_name=sender,
        text=text,
        reply_to_msg_id=None,
        forward_from=None,
        media_type=MediaType.NONE,
    )


class TestResponses:
    """Tests for response formatting."""

    def test_json_response(self) -> None:
        """JSON response formatting."""
        data = {"key": "value", "number": 123}
        result = json_response(data)
        parsed = json.loads(result)
        assert parsed == data

    def test_error_response(self) -> None:
        """Error response formatting."""
        result = error_response("Something went wrong", "Try this instead")
        parsed = json.loads(result)
        assert parsed["error"] == "Something went wrong"
        assert parsed["hint"] == "Try this instead"

    def test_truncate_short(self) -> None:
        """Truncate doesn't modify short text."""
        text = "Short text"
        result = truncate(text, limit=100)
        assert result == text

    def test_truncate_long(self) -> None:
        """TC9: Truncation."""
        text = "x" * 25000
        result = truncate(text, limit=20000)
        assert len(result) < 25000
        assert "truncated" in result


class TestListChats:
    """Tests for list_chats tool."""

    @pytest.fixture
    def server(self, tmp_path: Path) -> TelegramMCPServer:
        data_path = tmp_path / "data"
        data_path.mkdir()

        config_content = """
[group.test1]
id = 111
depth_months = 3
description = "Test Chat 1"

[group.test2]
id = 222
depth_months = 3
description = "Test Chat 2"
"""
        (data_path / "chats.toml").write_text(config_content)
        return TelegramMCPServer(data_path)

    @pytest.mark.asyncio
    async def test_list_chats(self, server: TelegramMCPServer) -> None:
        """TC1: list_chats."""
        result = await server._handle_tool("list_chats", {})
        parsed = json.loads(result)

        assert len(parsed) == 2
        assert any(c["id"] == 111 for c in parsed)
        assert any(c["id"] == 222 for c in parsed)


class TestSearchBlocks:
    """Tests for search_blocks tool."""

    @pytest.fixture
    def server(self, tmp_path: Path) -> TelegramMCPServer:
        data_path = tmp_path / "data"
        data_path.mkdir()

        config_content = """
[group.test]
id = 111
depth_months = 3
description = "Test Chat"
"""
        (data_path / "chats.toml").write_text(config_content)
        return TelegramMCPServer(data_path)

    @pytest.mark.asyncio
    async def test_search_blocks_limit(
        self, server: TelegramMCPServer, tmp_path: Path
    ) -> None:
        """TC3: search_blocks limit."""
        # Create many blocks
        storage = Storage(tmp_path / "data")
        for i in range(50):
            date = datetime(2024, 1, 15 + i // 24, i % 24, 0, tzinfo=UTC)
            msg = make_message(i, "keyword", date)
            await storage.write_messages(111, "Test", [msg])

        result = await server._handle_tool(
            "search_blocks",
            {"keywords": ["keyword"], "limit": 10},
        )
        parsed = json.loads(result)

        assert len(parsed) == 10


class TestReadBlock:
    """Tests for read_block tool."""

    @pytest.fixture
    def server(self, tmp_path: Path) -> TelegramMCPServer:
        data_path = tmp_path / "data"
        data_path.mkdir()

        config_content = """
[group.test]
id = 111
depth_months = 3
description = "Test Chat"
"""
        (data_path / "chats.toml").write_text(config_content)
        return TelegramMCPServer(data_path)

    @pytest.mark.asyncio
    async def test_read_block(
        self, server: TelegramMCPServer, tmp_path: Path
    ) -> None:
        """Read block returns messages."""
        storage = Storage(tmp_path / "data")
        date = datetime(2024, 1, 15, 14, 0, tzinfo=UTC)
        messages = [
            make_message(1, "Hello", date.replace(minute=5)),
            make_message(2, "World", date.replace(minute=10)),
        ]
        await storage.write_messages(111, "Test", messages)

        result = await server._handle_tool(
            "read_block",
            {"chat_id": 111, "block": "2024-01-15_14"},
        )

        assert "Hello" in result
        assert "World" in result


class TestReadBlocks:
    """Tests for read_blocks tool."""

    @pytest.fixture
    def server(self, tmp_path: Path) -> TelegramMCPServer:
        data_path = tmp_path / "data"
        data_path.mkdir()

        config_content = """
[group.test]
id = 111
depth_months = 3
description = "Test Chat"
"""
        (data_path / "chats.toml").write_text(config_content)
        return TelegramMCPServer(data_path)

    @pytest.mark.asyncio
    async def test_read_blocks_max_limit(self, server: TelegramMCPServer) -> None:
        """TC6: read_blocks max limit."""
        blocks = [f"2024-01-{i:02d}_14" for i in range(1, 16)]  # 15 blocks

        result = await server._handle_tool(
            "read_blocks",
            {"chat_id": 111, "blocks": blocks},
        )
        parsed = json.loads(result)

        assert "error" in parsed
        assert "10" in parsed["error"]


class TestSyncChat:
    """Tests for sync_chat tool."""

    @pytest.fixture
    def server(self, tmp_path: Path) -> TelegramMCPServer:
        data_path = tmp_path / "data"
        data_path.mkdir()

        config_content = """
[group.test]
id = 111
depth_months = 3
description = "Test Chat"
"""
        (data_path / "chats.toml").write_text(config_content)
        return TelegramMCPServer(data_path)

    @pytest.mark.asyncio
    async def test_sync_chat_soft_mode(
        self, server: TelegramMCPServer
    ) -> None:
        """TC8: sync_chat works for any chat (soft mode - whitelist only affects list_chats)."""
        result = await server._handle_tool(
            "sync_chat",
            {"chat_id": 999},
        )
        parsed = json.loads(result)

        # Soft mode: no whitelist blocking, error comes from Telegram (not found)
        assert "error" in parsed
        assert "whitelist" not in parsed["error"].lower()


class TestValidation:
    """Tests for parameter validation."""

    @pytest.fixture
    def server(self, tmp_path: Path) -> TelegramMCPServer:
        data_path = tmp_path / "data"
        data_path.mkdir()
        (data_path / "chats.toml").write_text("")
        return TelegramMCPServer(data_path)

    @pytest.mark.asyncio
    async def test_read_message_not_found(self, server: TelegramMCPServer) -> None:
        """TC4: read_message not found."""
        result = await server._handle_tool(
            "read_message",
            {"chat_id": 111, "msg_id": 99999},
        )
        parsed = json.loads(result)

        assert "error" in parsed


class TestUnknownTool:
    """Tests for unknown tool handling."""

    @pytest.fixture
    def server(self, tmp_path: Path) -> TelegramMCPServer:
        data_path = tmp_path / "data"
        data_path.mkdir()
        (data_path / "chats.toml").write_text("")
        return TelegramMCPServer(data_path)

    @pytest.mark.asyncio
    async def test_unknown_tool(self, server: TelegramMCPServer) -> None:
        """Unknown tool returns error."""
        result = await server._handle_tool("nonexistent_tool", {})
        parsed = json.loads(result)

        assert "error" in parsed
        assert "Unknown tool" in parsed["error"]
