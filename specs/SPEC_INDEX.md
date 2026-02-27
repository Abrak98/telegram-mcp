# Spec Index

## Модули

```
core/
├── telegram_client     # API Telegram (committed)
├── storage             # Хранение сообщений (committed)
├── search              # Поиск по хранилищу (committed)
└── mcp_server          # MCP tools для Claude (committed)
```

## Зависимости

```
telegram_client <- storage
storage <- search
search <- mcp_server
storage <- mcp_server
telegram_client <- mcp_server
```

## MCP Tools

```
list_chats
search_blocks
read_block_first_match
read_message
read_message_context
read_message_thread
read_block
read_blocks
read_recent
sync_chat
download_media
```
