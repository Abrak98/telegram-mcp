# Storage

## Intent

Абстракция хранения сообщений. Сейчас — файловая система (markdown по часам), потом — возможно база данных с индексами.

Ключевые функции:
- Запись сообщений в хранилище (Message[] → файлы)
- Чтение блоков, сообщений
- Метаданные чатов (meta.json)
- Управление конфигом чатов (chats.toml)

Формат хранения:
```
data/
├── session.session          # Telethon сессия
├── chats.toml               # whitelist чатов
└── chats/
    └── <chat_id>/
        ├── meta.json        # oldest_msg_id, newest_msg_id, last_sync
        ├── 2024-01-15_14.md # часовой блок
        └── ...
```

Формат markdown файла:
```markdown
# 2024-01-15 14:00-15:00 | Chat Name

[14:05] @username: текст сообщения
[14:07] @other_user: [Reply #1234] ответ на сообщение
[14:10] @someone: [Photo] подпись к фото
[14:12] @forward: [Fwd: Channel Name] пересланное сообщение
```

Важно: storage — только CRUD. Поиск — в отдельном модуле search.

## Clarifications

### Формат meta.json

Q1: Предлагаю структуру meta.json:
```json
{
  "chat_id": 123456789,
  "chat_name": "ClickHouse RU",
  "chat_type": "group",
  "oldest_msg_id": 1000,
  "newest_msg_id": 5000,
  "oldest_date": "2024-01-01T00:00:00",
  "newest_date": "2024-01-15T14:30:00",
  "last_sync": "2024-01-15T15:00:00",
  "total_messages": 4000
}
```
Достаточно? Что добавить/убрать?

A1: Ок

### Формат chats.toml

Q2: Подтверждаю формат из telegram_client:
```toml
[personal.john]
id = 123456789
depth_months = 3
description = "Джон, коллега backend"

[group.clickhouse]
id = -100111222333
depth_months = 12
description = "ClickHouse RU — технические обсуждения"
```
Нужно ли что-то ещё в конфиге чата?

A2: Ок

### Формат сообщения в markdown

Q3: Уточню формат строки сообщения:
```
[14:05] @username: текст сообщения
[14:07] @other_user: [↩ #1234] ответ на сообщение
[14:10] @someone: [📷 Photo] подпись к фото
[14:12] @forward: [↪ From: Channel Name] текст
```

Варианты для медиа:
- `[📷 Photo]` / `[🎬 Video]` / `[📄 Document]` / `[🎤 Voice]` / `[🎭 Sticker]`
- Или проще: `[Photo]` / `[Video]` / `[Document]` без эмодзи?

A3: без эмодзи. Если фото будет содеражть что-то важное, ты должен иметь возможность загрузить его и проанализировать. Но только если ты прям понял, что это нужно сделать

Q3.1: Для загрузки фото нужен отдельный MCP tool (download_media)? Или хранить локальный путь к уже скачанному файлу в markdown?

Предлагаю: отдельный tool `download_media(chat_id, msg_id)` — скачивает медиа по запросу, возвращает путь. Не качать автоматически всё подряд.

A3.1: ок. Куда буешь сохранять?

Q3.2: Предлагаю:
```
data/chats/<chat_id>/media/<msg_id>_<filename>
```
Например: `data/chats/123456/media/5000_photo.jpg`

Так медиа рядом с блоками, легко найти по msg_id. Согласен?

A3.2: Ок, `data/chats/<chat_id>/media/<msg_id>_<filename>`

### API Storage класса

Q4: Предлагаю интерфейс:
```python
class Storage:
    def __init__(self, data_path: Path)

    # Config
    def get_chat_config(self, chat_id: int) -> ChatConfig | None
    def list_chat_configs(self) -> list[ChatConfig]

    # Write
    async def write_messages(self, chat_id: int, messages: list[Message]) -> int

    # Read
    async def read_block(self, chat_id: int, block: str) -> list[Message]
    async def read_message(self, chat_id: int, msg_id: int) -> Message | None
    async def list_blocks(self, chat_id: int) -> list[str]

    # Meta
    async def get_meta(self, chat_id: int) -> StorageMeta | None
    async def update_meta(self, chat_id: int, meta: StorageMeta) -> None
```

Что добавить/изменить?

A4: Это тех спека. Сам решай.

### Конкурентный доступ

Q5: Нужна ли защита от одновременной записи в один файл? Или считаем что всегда один процесс?

A5: Всегда 1 процесс

### Часовой пояс

Q6: В каком timezone хранить время?
- UTC (консистентно, но неудобно читать)
- Local (удобно, но может путать)

Предлагаю UTC в meta.json, local в markdown файлах (для читаемости).

A6: Давай везде и всегда UTC. Я ведь могу переехать куда-то

Status: approved
