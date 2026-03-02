# Telegram Client

Narrative-Hash: 622e5ce52f85ecfe82df0f909ef1038c
Status: committed

## Dependencies

- `telethon` — Telegram MTProto API
- `pydantic` — модели данных
- `python-dotenv` — загрузка .env

## State

```python
class TelegramClient:
    _client: telethon.TelegramClient
    _config: TelegramConfig
    _connected: bool
```

```python
class TelegramConfig(BaseModel):
    api_id: int
    api_hash: str
    phone: str
    session_path: Path = Path.home() / ".config" / "telegram-mcp" / "session"

    @classmethod
    def from_env(cls) -> "TelegramConfig":
        """Загрузка из .env файла"""
```

## Models

```python
class ChatType(Enum):
    USER = "user"
    GROUP = "group"
    CHANNEL = "channel"

class Dialog(BaseModel):
    id: int
    name: str
    type: ChatType
    unread_count: int

class MediaType(Enum):
    NONE = "none"
    PHOTO = "photo"
    VIDEO = "video"
    DOCUMENT = "document"
    VOICE = "voice"
    STICKER = "sticker"
    OTHER = "other"

class Message(BaseModel):
    id: int
    date: datetime
    sender_id: int | None
    sender_name: str
    text: str
    reply_to_msg_id: int | None
    forward_from: str | None  # "User Name" или "Channel Name"
    media_type: MediaType
```

## Methods

```python
class TelegramClient:
    def __init__(self, config: TelegramConfig) -> None:
        """Создание клиента без подключения."""

    async def connect(self) -> None:
        """
        Подключение и авторизация.
        При первом запуске запрашивает код из Telegram.
        """

    async def disconnect(self) -> None:
        """Отключение от Telegram."""

    async def get_dialogs(self) -> list[Dialog]:
        """
        Получение списка всех диалогов пользователя.
        Возвращает: id, name, type, unread_count.
        """

    async def get_messages(
        self,
        chat_id: int,
        *,
        limit: int = 100,
        offset_id: int | None = None,
        min_date: datetime | None = None,
        max_date: datetime | None = None,
    ) -> list[Message]:
        """
        Получение сообщений из чата.

        Args:
            chat_id: ID чата
            limit: максимум сообщений (default 100)
            offset_id: получить сообщения старше этого ID
            min_date: не старше этой даты
            max_date: не новее этой даты

        Returns:
            Список сообщений, отсортированный по дате (новые первыми).
        """

    async def get_message_by_id(self, chat_id: int, message_id: int) -> Message | None:
        """
        Получение одного сообщения по ID.

        Returns:
            Message если найдено, None если не существует.
        """

    async def get_chat_info(self, chat_id: int) -> Dialog:
        """
        Получение информации о чате по ID.

        Returns:
            Dialog с id, name, type, unread_count.

        Raises:
            ValueError: если чат не найден или недоступен.
        """

    async def download_media(
        self,
        chat_id: int,
        msg_id: int,
        download_path: str,
    ) -> str | None:
        """
        Скачивание медиа из сообщения.

        Args:
            chat_id: ID чата
            msg_id: ID сообщения
            download_path: путь для сохранения

        Returns:
            Путь к скачанному файлу или None если нет медиа.
        """

    async def resolve_username(self, username: str) -> tuple[int, str, ChatType]:
        """
        Получение chat_id по @username.

        Args:
            username: Telegram username (с или без @)

        Returns:
            Кортеж (chat_id, name, chat_type).

        Raises:
            ValueError: если username не найден.
        """
```

## Invariants

1. `get_dialogs()`, `get_messages()`, `get_message_by_id()`, `get_chat_info()`, `download_media()`, `resolve_username()` требуют `_connected == True`, иначе `RuntimeError`
2. Все публичные методы — async
3. `Message.text` — пустая строка если сообщение без текста (медиа)
4. `Message.sender_name` — "Unknown" если отправитель недоступен
5. `Message.forward_from` — None если не форвард
6. `Dialog.type` определяется по типу Telethon entity:
   - `telethon.types.User` → `ChatType.USER`
   - `telethon.types.Chat` → `ChatType.GROUP`
   - `telethon.types.Channel` → `ChatType.CHANNEL`

## Formulas

```
messages_in_range = get_messages(chat_id, min_date=start, max_date=end)
# Возвращает все сообщения где: start <= message.date <= end
```

## Test Cases

### TC1: Подключение

```
GIVEN: валидный TelegramConfig
WHEN: await client.connect()
THEN: client._connected == True
```

### TC2: Ошибка без подключения

```
GIVEN: client._connected == False
WHEN: await client.get_dialogs()
THEN: raises RuntimeError("Not connected")
```

### TC3: Получение диалогов

```
GIVEN: client._connected == True
WHEN: dialogs = await client.get_dialogs()
THEN:
  - isinstance(dialogs, list)
  - all(isinstance(d, Dialog) for d in dialogs)
  - каждый dialog имеет id, name, type
```

### TC4: Получение сообщений с лимитом

```
GIVEN: client._connected == True, chat_id существует
WHEN: messages = await client.get_messages(chat_id, limit=10)
THEN:
  - len(messages) <= 10
  - messages отсортированы по date DESC
```

### TC5: Получение сообщений по дате

```
GIVEN: client._connected == True
WHEN: messages = await client.get_messages(
    chat_id,
    min_date=datetime(2024, 1, 1),
    max_date=datetime(2024, 1, 31)
)
THEN: all(datetime(2024,1,1) <= m.date <= datetime(2024,1,31) for m in messages)
```

### TC6: Пагинация через offset_id

```
GIVEN: первый запрос вернул messages с last_id = messages[-1].id
WHEN: next_page = await client.get_messages(chat_id, offset_id=last_id)
THEN: all(m.id < last_id for m in next_page)
```

### TC7: Сообщение с reply

```
GIVEN: сообщение является ответом на msg_id=123
WHEN: message = (await client.get_messages(chat_id, limit=1))[0]
THEN: message.reply_to_msg_id == 123
```

### TC8: Медиа placeholder

```
GIVEN: сообщение содержит фото без текста
WHEN: message = ...
THEN:
  - message.text == ""
  - message.media_type == MediaType.PHOTO
```

### TC9: Получение сообщения по ID

```
GIVEN: client._connected == True, существует message_id=12345
WHEN: message = await client.get_message_by_id(chat_id, 12345)
THEN: message.id == 12345
```

### TC10: Сообщение не найдено

```
GIVEN: client._connected == True, message_id не существует
WHEN: message = await client.get_message_by_id(chat_id, 99999999)
THEN: message is None
```

### TC11: Получение информации о чате

```
GIVEN: client._connected == True, chat_id существует
WHEN: info = await client.get_chat_info(chat_id)
THEN:
  - info.id == chat_id
  - info.name != ""
  - info.type in [ChatType.USER, ChatType.GROUP, ChatType.CHANNEL]
```

### TC12: Чат не найден

```
GIVEN: client._connected == True, chat_id не существует
WHEN: await client.get_chat_info(invalid_id)
THEN: raises ValueError
```

### TC13: Скачивание медиа

```
GIVEN: client._connected == True, сообщение содержит фото
WHEN: path = await client.download_media(chat_id, msg_id, "/tmp")
THEN: path is not None, файл существует
```

### TC14: Скачивание медиа без медиа

```
GIVEN: client._connected == True, сообщение без медиа
WHEN: path = await client.download_media(chat_id, msg_id, "/tmp")
THEN: path is None
```

### TC15: Resolve username

```
GIVEN: client._connected == True, существующий @username
WHEN: chat_id, name, chat_type = await client.resolve_username("@channelname")
THEN:
  - chat_id is int
  - name != ""
  - chat_type in [ChatType.USER, ChatType.GROUP, ChatType.CHANNEL]
```

### TC16: Resolve username без @

```
GIVEN: client._connected == True, username без @
WHEN: chat_id, name, chat_type = await client.resolve_username("channelname")
THEN: результат идентичен resolve_username("@channelname")
```

## File Structure

```
src/telegram/
├── __init__.py
├── client.py      # TelegramClient
├── config.py      # TelegramConfig
└── models.py      # Dialog, Message, ChatType, MediaType
```
