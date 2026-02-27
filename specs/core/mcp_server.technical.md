# MCP Server

Narrative-Hash: 16222869a038bb4992cc9bf72cab3f3c
Status: committed

## Dependencies

- `mcp` — MCP protocol implementation
- `telegram_client` — Telegram API
- `storage` — файловое хранилище
- `search` — поиск по хранилищу
- `extraction` — извлечение текста из PDF/изображений (OCR)
- `filelock` — file-based locking для sync

## State

```python
class MCPServer:
    _telegram: TelegramClient
    _storage: Storage
    _search: Search
    _extractor: TextExtractor
    _sync_locks: dict[int, FileLock]  # chat_id -> lock
```

## Constants

```python
DEFAULT_CHAR_LIMIT = 8000
MAX_CHAR_LIMIT = 20000
DEFAULT_SEARCH_LIMIT = 20
DEFAULT_RECENT_LIMIT = 50
MAX_BLOCKS_PER_REQUEST = 10
PREVIEW_WORDS = 10
```

## Tools

### list_chats

```python
async def list_chats(type: str | None = None) -> str:
    """
    Список доступных чатов из whitelist.

    Args:
        type: фильтр по типу ("user", "group", "channel")

    Returns: JSON
        [
            {
                "id": 123456789,
                "alias": "john",
                "type": "user",
                "description": "Джон, коллега backend",
                "has_data": true,
                "last_sync": "2024-01-15T15:00:00Z"
            },
            ...
        ]
    """
```

### search_blocks

```python
async def search_blocks(
    keywords: list[str],
    chat_id: int | None = None,
    limit: int = 20,
    include_preview: bool = False
) -> str:
    """
    Поиск блоков с ключевыми словами.

    Args:
        keywords: ключевые слова (case-insensitive, OR)
        chat_id: ограничить одним чатом
        limit: максимум результатов (1-100, default 20)
        include_preview: включить preview первого совпадения

    Returns: JSON
        [
            {
                "chat_id": 123,
                "chat_name": "ClickHouse RU",
                "block": "2024-01-15_14",
                "keyword_counts": {"clickhouse": 3, "merge": 1},
                "total_matches": 4,
                "preview": "Вчера обсуждали clickhouse..."  // if include_preview
            },
            ...
        ]

    Triggers lazy load: если chat_id указан и данных нет.
    """
```

### read_block_first_match

```python
async def read_block_first_match(
    chat_id: int,
    block: str,
    keywords: list[str]
) -> str:
    """
    Первое сообщение с совпадением в блоке.

    Returns: Markdown
        [14:05] @username: текст с keyword...

    Error: JSON если не найдено.
    """
```

### read_message

```python
async def read_message(chat_id: int, msg_id: int) -> str:
    """
    Одно сообщение по ID.

    Returns: Markdown
        [14:05] @username: текст сообщения

    Error: JSON если не найдено.

    Triggers lazy load: если данных нет.
    """
```

### read_message_context

```python
async def read_message_context(
    chat_id: int,
    msg_id: int,
    before: int = 5,
    after: int = 5
) -> str:
    """
    Сообщение с контекстом ±N сообщений.

    Returns: Markdown
        [14:00] @user1: ...
        [14:02] @user2: ...
        >>> [14:05] @username: целевое сообщение
        [14:07] @user3: ...
        [14:10] @user4: ...

    Целевое сообщение выделяется маркером >>>.
    """
```

### read_block

```python
async def read_block(chat_id: int, block: str) -> str:
    """
    Весь часовой блок.

    Returns: Markdown — все сообщения блока.

    Truncation: если превышает MAX_CHAR_LIMIT, обрезается с пометкой.
    """
```

### read_blocks

```python
async def read_blocks(chat_id: int, blocks: list[str]) -> str:
    """
    Несколько блоков.

    Args:
        blocks: список блоков (max 10)

    Returns: Markdown — блоки разделены заголовками.

    Error: если blocks > 10.
    """
```

### read_recent

```python
async def read_recent(
    chat_id: int,
    limit: int = 50,
    keywords: list[str] | None = None,
    regex: str | None = None
) -> str:
    """
    Последние сообщения с опциональным фильтром.

    Args:
        limit: максимум сообщений (1-200, default 50)
        keywords: фильтр по словам (OR)
        regex: фильтр по Python regex

    Returns: Markdown

    Triggers lazy load: если данных нет.
    """
```

### sync_chat

```python
async def sync_chat(
    chat_id: int,
    months: int = 3,
    force: bool = False
) -> str:
    """
    Синхронизация чата с Telegram.

    Args:
        chat_id: ID чата
        months: глубина синхронизации
        force: удалить все данные и синхронизировать заново

    Returns: JSON
        {
            "status": "success",
            "messages_synced": 1500,
            "blocks_created": 45,
            "duration_seconds": 12.5
        }

    Features:
        - Auto OCR: извлекает текст из PDF/изображений при синхронизации
        - Cleanup: удаляет media файлы после успешного OCR

    Errors:
        - Chat not found
        - Sync already in progress
        - Telegram API error (FloodWait с временем ожидания)

    Lock: file-based lock на уровне чата.
    """
```

### download_media

```python
async def download_media(chat_id: int, msg_id: int) -> str:
    """
    Скачать медиа из сообщения.

    Returns: JSON
        {
            "path": "data/media/photo.jpg",
            "chat_id": 123,
            "msg_id": 456
        }

    Errors:
        - No media in message or download failed
    """
```

### resolve_username

```python
async def resolve_username(username: str) -> str:
    """
    Получить chat_id по @username.

    Args:
        username: Telegram username (с или без @)

    Returns: JSON
        {
            "chat_id": 123456789,
            "name": "Channel Name",
            "type": "channel",
            "username": "channelname"
        }

    Errors:
        - Username not found
    """
```

### extract_media_text

```python
async def extract_media_text(chat_id: int, msg_id: int) -> str:
    """
    Извлечь текст из PDF/изображения в сообщении (OCR).

    Args:
        chat_id: ID чата
        msg_id: ID сообщения с медиа

    Returns: JSON
        {
            "text": "Извлечённый текст...",
            "file": "document.pdf",
            "chat_id": 123,
            "msg_id": 456
        }

    Supported formats: PDF, JPG, PNG, WEBP, TIFF, BMP

    Errors:
        - No media in message
        - Unsupported file type
        - No text extracted from media
    """
```

## Error Format

```json
{
    "error": "Error message",
    "hint": "Optional hint for user"
}
```

## Invariants

1. Все tools возвращают string (JSON или Markdown)
2. Markdown tools обрезаются при превышении MAX_CHAR_LIMIT
3. Lazy load срабатывает автоматически при отсутствии данных
4. sync_chat защищён file-based lock (`data/chats/<chat_id>/.sync.lock`)
5. Ошибки возвращаются как JSON с полями `error` и опционально `hint`
6. limit параметры валидируются и ограничиваются
7. Whitelist (soft mode): влияет только на list_chats, не блокирует доступ к другим чатам

## Formulas

```python
# Truncation
def truncate(text: str, limit: int = DEFAULT_CHAR_LIMIT) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n\n... [truncated, {len(text) - limit} chars more]"

# Lock path
def get_lock_path(chat_id: int) -> Path:
    return data_path / "chats" / str(chat_id) / ".sync.lock"
```

## Test Cases

### TC1: list_chats

```
GIVEN: chats.toml с 3 чатами, 2 имеют данные
WHEN: result = await server.list_chats()
THEN:
  - JSON с 3 элементами
  - has_data == True для 2 чатов
```

### TC2: search_blocks lazy load

```
GIVEN: chat_id=123, данных нет
WHEN: await server.search_blocks(["test"], chat_id=123)
THEN: сначала выполняется sync, потом поиск
```

### TC3: search_blocks limit

```
GIVEN: 50 блоков с совпадениями
WHEN: result = await server.search_blocks(["test"], limit=10)
THEN: JSON содержит 10 элементов
```

### TC4: read_message not found

```
GIVEN: msg_id не существует
WHEN: result = await server.read_message(chat_id, 99999)
THEN: JSON с error
```

### TC5: read_message_context

```
GIVEN: msg_id=100, before=2, after=2
WHEN: result = await server.read_message_context(chat_id, 100, 2, 2)
THEN:
  - Markdown с 5 сообщениями
  - Центральное выделено >>>
```

### TC6: read_blocks max limit

```
GIVEN: blocks = ["b1", "b2", ..., "b15"] (15 блоков)
WHEN: await server.read_blocks(chat_id, blocks)
THEN: JSON error "Maximum 10 blocks per request"
```

### TC7: sync_chat lock

```
GIVEN: sync уже запущен для chat_id
WHEN: await server.sync_chat(chat_id)
THEN: JSON error "Sync already in progress"
```

### TC8: sync_chat soft mode

```
GIVEN: chat_id не в whitelist
WHEN: await server.sync_chat(unknown_id)
THEN: Ошибка от Telegram (not found), не whitelist error
```

### TC9: truncation

```
GIVEN: блок содержит 25000 символов
WHEN: result = await server.read_block(chat_id, block)
THEN: len(result) <= MAX_CHAR_LIMIT + 50 (с пометкой о truncation)
```

### TC10: download_media success

```
GIVEN: сообщение с фото
WHEN: result = await server.download_media(chat_id, msg_id)
THEN: JSON с path
```

### TC11: download_media no media

```
GIVEN: сообщение только с текстом
WHEN: result = await server.download_media(chat_id, msg_id)
THEN: JSON error "No media in message"
```

### TC12: resolve_username

```
GIVEN: существующий @username
WHEN: result = await server.resolve_username("@channelname")
THEN: JSON с chat_id, name, type
```

### TC13: extract_media_text

```
GIVEN: сообщение с PDF
WHEN: result = await server.extract_media_text(chat_id, msg_id)
THEN: JSON с extracted text
```

### TC14: read_recent with filter

```
GIVEN: 100 последних сообщений, 10 содержат "test"
WHEN: result = await server.read_recent(chat_id, limit=50, keywords=["test"])
THEN: Markdown с 10 сообщениями
```

## File Structure

```
src/mcp/
├── __init__.py
├── server.py      # MCPServer class
├── responses.py   # response formatting (JSON/Markdown)
└── sync.py        # sync logic with locking + OCR
```
