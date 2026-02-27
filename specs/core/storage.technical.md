# Storage

Narrative-Hash: de384ba490ec424a7ee1828b9c10e4e4
Status: committed

## Dependencies

- `tomli` — парсинг chats.toml
- `pydantic` — модели данных
- `aiofiles` — async файловые операции

## State

```python
class Storage:
    _data_path: Path
    _chat_configs: dict[int, ChatConfig]  # cache, загружается из chats.toml
```

## Models

```python
class ChatConfig(BaseModel):
    id: int
    alias: str  # "john", "clickhouse"
    type: str  # "personal", "group", "channel"
    depth_months: int
    description: str

class StorageMeta(BaseModel):
    chat_id: int
    chat_name: str
    chat_type: str  # "user", "group", "channel"
    oldest_msg_id: int
    newest_msg_id: int
    oldest_date: datetime
    newest_date: datetime
    last_sync: datetime
    total_messages: int
```

## Methods

```python
class Storage:
    def __init__(self, data_path: Path) -> None:
        """
        Инициализация storage.
        Загружает chats.toml в память.
        Создаёт data_path если не существует.
        """

    def get_chat_config(self, chat_id: int) -> ChatConfig | None:
        """Получить конфиг чата по ID. None если не в whitelist."""

    def list_chat_configs(self) -> list[ChatConfig]:
        """Список всех чатов из whitelist."""

    async def write_messages(
        self,
        chat_id: int,
        chat_name: str,
        messages: list[Message]
    ) -> int:
        """
        Записать сообщения в часовые блоки.

        Args:
            chat_id: ID чата
            chat_name: название для заголовка блока
            messages: список сообщений (Message из telegram.models)

        Returns:
            Количество записанных сообщений.

        Сообщения группируются по часам (UTC).
        Каждый блок — отдельный .md файл.
        Если блок существует — append, не перезапись.
        """

    async def read_block(self, chat_id: int, block: str) -> list[Message]:
        """
        Прочитать все сообщения из блока.

        Args:
            chat_id: ID чата
            block: идентификатор блока "YYYY-MM-DD_HH"

        Returns:
            Список Message, пустой если блок не существует.
        """

    async def read_message(self, chat_id: int, msg_id: int) -> Message | None:
        """
        Найти сообщение по ID во всех блоках чата.

        Returns:
            Message если найдено, None если нет.

        Note:
            Медленная операция — перебор всех блоков.
            Для частого использования нужен индекс.
        """

    async def list_blocks(self, chat_id: int) -> list[str]:
        """
        Список всех блоков чата.

        Returns:
            ["2024-01-15_14", "2024-01-15_15", ...] — отсортированы по дате DESC.
        """

    async def get_meta(self, chat_id: int) -> StorageMeta | None:
        """Получить метаданные чата. None если meta.json не существует."""

    async def update_meta(self, chat_id: int, meta: StorageMeta) -> None:
        """Записать/обновить meta.json чата."""

    def get_chat_path(self, chat_id: int) -> Path:
        """Путь к директории чата: data/chats/<chat_id>/"""

    def get_block_path(self, chat_id: int, block: str) -> Path:
        """Путь к файлу блока: data/chats/<chat_id>/<block>.md"""

    def get_media_path(self, chat_id: int, msg_id: int, filename: str) -> Path:
        """Путь к медиа: data/chats/<chat_id>/media/<msg_id>_<filename>"""
```

## File Formats

### chats.toml

```toml
[personal.john]
id = 123456789
depth_months = 3
description = "Джон, коллега backend"

[group.clickhouse]
id = -100111222333
depth_months = 12
description = "ClickHouse RU"
```

### meta.json

```json
{
  "chat_id": 123456789,
  "chat_name": "ClickHouse RU",
  "chat_type": "group",
  "oldest_msg_id": 1000,
  "newest_msg_id": 5000,
  "oldest_date": "2024-01-01T00:00:00Z",
  "newest_date": "2024-01-15T14:30:00Z",
  "last_sync": "2024-01-15T15:00:00Z",
  "total_messages": 4000
}
```

### Block file (YYYY-MM-DD_HH.md)

```markdown
# 2024-01-15 14:00-15:00 UTC | Chat Name

[14:05] @username: текст сообщения
[14:07] @other_user: [Reply #1234] ответ на сообщение
[14:10] @someone: [Photo] подпись к фото
[14:12] @forward: [Fwd: Channel Name] пересланное сообщение
[14:15] @user: [Video] описание видео
[14:20] @user: [Document] filename.pdf
[14:25] @user: [Voice]
[14:30] @user: [Sticker]
```

## Invariants

1. Все даты хранятся в UTC
2. Блоки именуются по часу начала в UTC: `YYYY-MM-DD_HH`
3. Сообщения внутри блока отсортированы по времени ASC
4. `list_blocks()` возвращает блоки отсортированные по дате DESC (свежие первыми)
5. `write_messages()` не перезаписывает существующие сообщения — append only
6. `read_message()` парсит формат markdown обратно в Message
7. Медиа типы в markdown без эмодзи: `[Photo]`, `[Video]`, `[Document]`, `[Voice]`, `[Sticker]`
8. Reply формат: `[Reply #<msg_id>]`
9. Forward формат: `[Fwd: <source_name>]`

## Formulas

```
block_name = message.date.strftime("%Y-%m-%d_%H")  # UTC
chat_path = data_path / "chats" / str(chat_id)
block_path = chat_path / f"{block_name}.md"
media_path = chat_path / "media" / f"{msg_id}_{filename}"
```

## Test Cases

### TC1: Загрузка конфига

```
GIVEN: chats.toml существует с 2 чатами
WHEN: storage = Storage(data_path)
THEN: len(storage.list_chat_configs()) == 2
```

### TC2: Чат не в whitelist

```
GIVEN: chat_id=999 отсутствует в chats.toml
WHEN: config = storage.get_chat_config(999)
THEN: config is None
```

### TC3: Запись сообщений создаёт блоки

```
GIVEN: 3 сообщения в разных часах (14:00, 14:30, 15:10)
WHEN: await storage.write_messages(chat_id, "Test", messages)
THEN:
  - создано 2 блока: 2024-01-15_14.md, 2024-01-15_15.md
  - первый блок содержит 2 сообщения
  - второй блок содержит 1 сообщение
```

### TC4: Чтение блока

```
GIVEN: блок 2024-01-15_14.md существует с 5 сообщениями
WHEN: messages = await storage.read_block(chat_id, "2024-01-15_14")
THEN: len(messages) == 5
```

### TC5: Чтение несуществующего блока

```
GIVEN: блок не существует
WHEN: messages = await storage.read_block(chat_id, "2099-01-01_00")
THEN: messages == []
```

### TC6: Список блоков отсортирован

```
GIVEN: блоки 2024-01-15_14, 2024-01-15_15, 2024-01-16_10
WHEN: blocks = await storage.list_blocks(chat_id)
THEN: blocks == ["2024-01-16_10", "2024-01-15_15", "2024-01-15_14"]
```

### TC7: Парсинг reply из markdown

```
GIVEN: строка "[14:07] @user: [Reply #1234] текст"
WHEN: message = parse_message_line(line)
THEN:
  - message.reply_to_msg_id == 1234
  - message.text == "текст"
```

### TC8: Парсинг forward из markdown

```
GIVEN: строка "[14:12] @user: [Fwd: Channel Name] текст"
WHEN: message = parse_message_line(line)
THEN:
  - message.forward_from == "Channel Name"
  - message.text == "текст"
```

### TC9: Парсинг медиа из markdown

```
GIVEN: строка "[14:10] @user: [Photo] подпись"
WHEN: message = parse_message_line(line)
THEN:
  - message.media_type == MediaType.PHOTO
  - message.text == "подпись"
```

### TC10: Meta CRUD

```
GIVEN: meta не существует
WHEN: await storage.update_meta(chat_id, meta)
THEN: await storage.get_meta(chat_id) == meta
```

### TC11: Append к существующему блоку

```
GIVEN: блок существует с 2 сообщениями
WHEN: await storage.write_messages(chat_id, "Test", [new_message_same_hour])
THEN: блок содержит 3 сообщения (append, не перезапись)
```

### TC12: UTC timezone

```
GIVEN: message.date = datetime(2024,1,15,14,30, tzinfo=UTC)
WHEN: await storage.write_messages(...)
THEN: блок называется "2024-01-15_14", время в файле "14:30"
```

## File Structure

```
src/storage/
├── __init__.py
├── storage.py     # Storage class
├── models.py      # ChatConfig, StorageMeta
├── parser.py      # parse/format markdown <-> Message
└── config.py      # загрузка chats.toml
```
