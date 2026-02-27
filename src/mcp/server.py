"""MCP Server implementation."""

from pathlib import Path

from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from mcp.server import Server
from src.extraction import TextExtractor
from src.search import Search
from src.storage import Storage
from src.telegram import TelegramClient, TelegramConfig

from .responses import (
    MAX_CHAR_LIMIT,
    error_response,
    json_response,
    truncate,
)
from .sync import SyncManager

# Constants
DEFAULT_SEARCH_LIMIT = 20
DEFAULT_RECENT_LIMIT = 50
MAX_BLOCKS_PER_REQUEST = 10


class TelegramMCPServer:
    """MCP server for Telegram chat search."""

    def __init__(self, data_path: Path) -> None:
        self._data_path = data_path
        self._storage = Storage(data_path)
        self._search = Search(self._storage)
        self._telegram: TelegramClient | None = None
        self._sync: SyncManager | None = None
        self._extractor = TextExtractor()
        self._server = Server("telegram-mcp")

        self._register_tools()

    def _get_telegram(self) -> TelegramClient:
        """Get or create Telegram client."""
        if self._telegram is None:
            config = TelegramConfig.from_env()
            self._telegram = TelegramClient(config)
        return self._telegram

    async def _ensure_connected(self) -> TelegramClient:
        """Ensure Telegram client is connected (lazy connect)."""
        client = self._get_telegram()
        if not client._connected:
            await client.connect()
        return client

    def _get_sync(self) -> SyncManager:
        """Get or create sync manager."""
        if self._sync is None:
            self._sync = SyncManager(
                self._get_telegram(),
                self._storage,
                self._data_path,
            )
        return self._sync

    async def _ensure_sync(self) -> SyncManager:
        """Ensure sync manager with connected client."""
        await self._ensure_connected()
        return self._get_sync()

    def _register_tools(self) -> None:
        """Register all MCP tools."""

        @self._server.list_tools()
        async def list_tools() -> list[Tool]:
            return [
                Tool(
                    name="list_chats",
                    description="List available chats from whitelist",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": ["user", "group", "channel"],
                                "description": "Filter by chat type (optional)",
                            },
                        },
                    },
                ),
                Tool(
                    name="search_blocks",
                    description="Search blocks containing keywords",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "keywords": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Keywords to search (case-insensitive, OR)",
                            },
                            "chat_id": {
                                "type": "integer",
                                "description": "Limit to specific chat",
                            },
                            "limit": {
                                "type": "integer",
                                "default": 20,
                                "description": "Max results (1-100)",
                            },
                            "include_preview": {
                                "type": "boolean",
                                "default": False,
                                "description": "Include preview of first match",
                            },
                        },
                        "required": ["keywords"],
                    },
                ),
                Tool(
                    name="read_block_first_match",
                    description="Get first message matching keywords in block",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "chat_id": {"type": "integer"},
                            "block": {"type": "string"},
                            "keywords": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        "required": ["chat_id", "block", "keywords"],
                    },
                ),
                Tool(
                    name="read_message",
                    description="Read single message by ID",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "chat_id": {"type": "integer"},
                            "msg_id": {"type": "integer"},
                        },
                        "required": ["chat_id", "msg_id"],
                    },
                ),
                Tool(
                    name="read_message_context",
                    description="Read message with surrounding context",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "chat_id": {"type": "integer"},
                            "msg_id": {"type": "integer"},
                            "before": {"type": "integer", "default": 5},
                            "after": {"type": "integer", "default": 5},
                        },
                        "required": ["chat_id", "msg_id"],
                    },
                ),
                Tool(
                    name="read_block",
                    description="Read entire hourly block",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "chat_id": {"type": "integer"},
                            "block": {"type": "string"},
                        },
                        "required": ["chat_id", "block"],
                    },
                ),
                Tool(
                    name="read_blocks",
                    description="Read multiple blocks (max 10)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "chat_id": {"type": "integer"},
                            "blocks": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        "required": ["chat_id", "blocks"],
                    },
                ),
                Tool(
                    name="read_recent",
                    description="Read recent messages with optional filter",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "chat_id": {"type": "integer"},
                            "limit": {"type": "integer", "default": 50},
                            "keywords": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "regex": {"type": "string"},
                        },
                        "required": ["chat_id"],
                    },
                ),
                Tool(
                    name="sync_chat",
                    description="Synchronize chat with Telegram",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "chat_id": {"type": "integer"},
                            "months": {"type": "integer", "default": 3},
                            "force": {"type": "boolean", "default": False},
                        },
                        "required": ["chat_id"],
                    },
                ),
                Tool(
                    name="download_media",
                    description="Download media from message",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "chat_id": {"type": "integer"},
                            "msg_id": {"type": "integer"},
                        },
                        "required": ["chat_id", "msg_id"],
                    },
                ),
                Tool(
                    name="resolve_username",
                    description="Resolve @username to chat_id",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "username": {"type": "string"},
                        },
                        "required": ["username"],
                    },
                ),
                Tool(
                    name="extract_media_text",
                    description="Extract text from PDF/image in message (OCR)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "chat_id": {"type": "integer"},
                            "msg_id": {"type": "integer"},
                        },
                        "required": ["chat_id", "msg_id"],
                    },
                ),
            ]

        @self._server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[TextContent]:
            result = await self._handle_tool(name, arguments)
            return [TextContent(type="text", text=result)]

    async def _handle_tool(self, name: str, args: dict) -> str:
        """Route tool call to appropriate handler."""
        handlers = {
            "list_chats": self._list_chats,
            "search_blocks": self._search_blocks,
            "read_block_first_match": self._read_block_first_match,
            "read_message": self._read_message,
            "read_message_context": self._read_message_context,
            "read_block": self._read_block,
            "read_blocks": self._read_blocks,
            "read_recent": self._read_recent,
            "sync_chat": self._sync_chat,
            "download_media": self._download_media,
            "resolve_username": self._resolve_username,
            "extract_media_text": self._extract_media_text,
        }

        handler = handlers.get(name)
        if not handler:
            return error_response(f"Unknown tool: {name}")

        try:
            return await handler(args)
        except Exception as e:
            return error_response(str(e))

    async def _list_chats(self, args: dict) -> str:
        """List available chats."""
        type_filter = args.get("type")
        configs = self._storage.list_chat_configs()
        result = []

        for config in configs:
            # Filter by type if specified
            if type_filter and config.type != type_filter:
                continue

            meta = await self._storage.get_meta(config.id)
            result.append({
                "id": config.id,
                "alias": config.alias,
                "type": config.type,
                "description": config.description,
                "has_data": meta is not None,
                "last_sync": meta.last_sync.isoformat() if meta else None,
            })

        return json_response(result)

    async def _search_blocks(self, args: dict) -> str:
        """Search blocks containing keywords."""
        keywords = args.get("keywords", [])
        chat_id = args.get("chat_id")
        limit = min(args.get("limit", DEFAULT_SEARCH_LIMIT), 100)
        include_preview = args.get("include_preview", False)

        # Lazy load if needed
        if chat_id:
            await (await self._ensure_sync()).ensure_data(chat_id)

        results = await self._search.search_blocks(
            keywords,
            chat_id=chat_id,
            limit=limit,
            include_preview=include_preview,
        )

        return json_response([r.model_dump() for r in results])

    async def _read_block_first_match(self, args: dict) -> str:
        """Get first message matching keywords in block."""
        chat_id = args["chat_id"]
        block = args["block"]
        keywords = args["keywords"]

        msg = await self._search.find_first_match(chat_id, block, keywords)
        if not msg:
            return error_response("No match found")

        return self._format_message(msg)

    async def _read_message(self, args: dict) -> str:
        """Read single message by ID."""
        chat_id = args["chat_id"]
        msg_id = args["msg_id"]

        # Lazy load
        await (await self._ensure_sync()).ensure_data(chat_id)

        msg = await self._storage.read_message(chat_id, msg_id)
        if not msg:
            return error_response(f"Message {msg_id} not found")

        return self._format_message(msg)

    async def _read_message_context(self, args: dict) -> str:
        """Read message with surrounding context."""
        chat_id = args["chat_id"]
        msg_id = args["msg_id"]
        before = args.get("before", 5)
        after = args.get("after", 5)

        # Lazy load
        await (await self._ensure_sync()).ensure_data(chat_id)

        # Get all blocks and find the message
        blocks = await self._storage.list_blocks(chat_id)
        all_messages = []

        for block in blocks:
            messages = await self._storage.read_block(chat_id, block)
            all_messages.extend(messages)

        # Sort by date
        all_messages.sort(key=lambda m: m.date)

        # Find target message index
        target_idx = None
        for i, msg in enumerate(all_messages):
            if msg.id == msg_id:
                target_idx = i
                break

        if target_idx is None:
            return error_response(f"Message {msg_id} not found")

        # Get context window
        start = max(0, target_idx - before)
        end = min(len(all_messages), target_idx + after + 1)
        context_messages = all_messages[start:end]

        # Format with marker for target message
        lines = []
        for msg in context_messages:
            marker = ">>> " if msg.id == msg_id else "    "
            lines.append(f"{marker}{self._format_message(msg)}")

        return truncate("\n".join(lines), MAX_CHAR_LIMIT)

    async def _read_block(self, args: dict) -> str:
        """Read entire hourly block."""
        chat_id = args["chat_id"]
        block = args["block"]

        messages = await self._storage.read_block(chat_id, block)
        if not messages:
            return error_response(f"Block {block} not found")

        text = self._format_messages(messages, block)
        return truncate(text, MAX_CHAR_LIMIT)

    async def _read_blocks(self, args: dict) -> str:
        """Read multiple blocks."""
        chat_id = args["chat_id"]
        blocks = args["blocks"]

        if len(blocks) > MAX_BLOCKS_PER_REQUEST:
            return error_response(f"Maximum {MAX_BLOCKS_PER_REQUEST} blocks per request")

        parts = []
        for block in blocks:
            messages = await self._storage.read_block(chat_id, block)
            if messages:
                parts.append(self._format_messages(messages, block))

        text = "\n\n---\n\n".join(parts)
        return truncate(text, MAX_CHAR_LIMIT)

    async def _read_recent(self, args: dict) -> str:
        """Read recent messages with optional filter."""
        chat_id = args["chat_id"]
        limit = min(args.get("limit", DEFAULT_RECENT_LIMIT), 200)
        keywords = args.get("keywords")
        regex = args.get("regex")

        # Lazy load
        await (await self._ensure_sync()).ensure_data(chat_id)

        # Get recent blocks
        blocks = await self._storage.list_blocks(chat_id)
        all_messages = []

        for block in blocks:
            messages = await self._storage.read_block(chat_id, block)
            all_messages.extend(messages)
            if len(all_messages) >= limit * 2:  # Buffer for filtering
                break

        # Sort by date desc
        all_messages.sort(key=lambda m: m.date, reverse=True)

        # Filter
        if keywords or regex:
            all_messages = self._search.filter_messages(
                all_messages,
                keywords=keywords,
                regex=regex,
            )

        # Limit
        all_messages = all_messages[:limit]

        text = self._format_messages(all_messages)
        return truncate(text, MAX_CHAR_LIMIT)

    async def _sync_chat(self, args: dict) -> str:
        """Synchronize chat with Telegram."""
        chat_id = args["chat_id"]
        months = args.get("months", 3)
        force = args.get("force", False)

        try:
            result = await (await self._ensure_sync()).sync_chat(chat_id, months, force=force)
            return json_response(result)
        except ValueError as e:
            return error_response(str(e), "Use list_chats to see available chats")
        except RuntimeError as e:
            return error_response(str(e))

    async def _download_media(self, args: dict) -> str:
        """Download media from message."""
        chat_id = args["chat_id"]
        msg_id = args["msg_id"]

        # Ensure connected
        client = await self._ensure_connected()

        # Download to data/media/
        download_path = self._data_path / "media"
        download_path.mkdir(parents=True, exist_ok=True)

        path = await client.download_media(chat_id, msg_id, str(download_path))
        if not path:
            return error_response("No media in message or download failed")

        return json_response({"path": path, "chat_id": chat_id, "msg_id": msg_id})

    async def _resolve_username(self, args: dict) -> str:
        """Resolve @username to chat_id."""
        username = args["username"]

        client = await self._ensure_connected()
        try:
            chat_id, name, chat_type = await client.resolve_username(username)
            return json_response({
                "chat_id": chat_id,
                "name": name,
                "type": chat_type.value,
                "username": username.lstrip("@"),
            })
        except ValueError as e:
            return error_response(str(e), "Check if username exists")

    async def _extract_media_text(self, args: dict) -> str:
        """Extract text from PDF/image in message."""
        chat_id = args["chat_id"]
        msg_id = args["msg_id"]

        client = await self._ensure_connected()

        # Download media
        download_path = self._data_path / "media"
        download_path.mkdir(parents=True, exist_ok=True)

        path = await client.download_media(chat_id, msg_id, str(download_path))
        if not path:
            return error_response("No media in message")

        file_path = Path(path)
        if not self._extractor.can_extract(file_path):
            return error_response(
                f"Unsupported file type: {file_path.suffix}",
                "Supported: PDF, JPG, PNG, WEBP",
            )

        text = self._extractor.extract(file_path)
        if not text:
            return error_response("No text extracted from media")

        return json_response({
            "text": text,
            "file": file_path.name,
            "chat_id": chat_id,
            "msg_id": msg_id,
        })

    def _format_message(self, msg) -> str:
        """Format single message as markdown."""
        time_str = msg.date.strftime("%H:%M")
        parts = [f"[{time_str}] @{msg.sender_name}:"]

        if msg.reply_to_msg_id:
            parts.append(f"[Reply #{msg.reply_to_msg_id}]")
        if msg.forward_from:
            parts.append(f"[Fwd: {msg.forward_from}]")
        if msg.media_type.value != "none":
            parts.append(f"[{msg.media_type.value.capitalize()}]")
        if msg.text:
            parts.append(msg.text)

        return " ".join(parts)

    def _format_messages(self, messages: list, block: str | None = None) -> str:
        """Format list of messages as markdown."""
        lines = []

        if block:
            lines.append(f"## Block: {block}\n")

        for msg in messages:
            lines.append(self._format_message(msg))

        return "\n".join(lines)

    async def run(self) -> None:
        """Run the MCP server."""
        async with stdio_server() as (read_stream, write_stream):
            await self._server.run(
                read_stream,
                write_stream,
                self._server.create_initialization_options(),
            )


def main() -> None:
    """Entry point."""
    import asyncio

    async def _run() -> None:
        server = TelegramMCPServer(Path("data"))
        await server.run()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
