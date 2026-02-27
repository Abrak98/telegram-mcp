# Telegram MCP Server

MCP (Model Context Protocol) server для поиска по Telegram чатам. Индексирует историю сообщений и предоставляет полнотекстовый поиск через MCP инструменты.

## Возможности

- Синхронизация истории чатов с Telegram
- Полнотекстовый поиск по ключевым словам
- OCR извлечение текста из PDF и изображений
- Чтение сообщений по блокам (часовым интервалам)
- Whitelist чатов с настройкой глубины синхронизации

## Требования

- Python 3.12+
- Telegram API credentials (api_id, api_hash)
- Tesseract OCR (для извлечения текста из изображений)

## Установка

```bash
# Клонирование
git clone <repo-url>
cd telegram-mcp

# Установка зависимостей
pip install -e ".[dev]"

# Tesseract OCR (Ubuntu/Debian)
sudo apt install tesseract-ocr tesseract-ocr-rus

# Конфигурация
cp .env.example .env
mkdir -p data
cp chats.toml.example data/chats.toml
# Заполнить .env и data/chats.toml своими данными
```

## Конфигурация

### .env

```bash
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=your_api_hash_here
TELEGRAM_PHONE=+1234567890
```

Получить credentials: https://my.telegram.org/apps

### data/chats.toml

Whitelist чатов для синхронизации:

```toml
[channel.example]
id = -1001234567890
depth_months = 3
description = "Example channel"

[user.friend]
id = 123456789
depth_months = 12
description = "Friend"
```

## Использование

### Запуск MCP сервера

```bash
telegram-mcp
```

При первом запуске потребуется авторизация в Telegram (код из приложения).

### MCP инструменты

| Инструмент | Описание |
|------------|----------|
| `list_chats` | Список доступных чатов |
| `search_blocks` | Поиск блоков по ключевым словам |
| `read_block` | Чтение часового блока сообщений |
| `read_blocks` | Чтение нескольких блоков |
| `read_message` | Чтение одного сообщения |
| `read_message_context` | Сообщение с контекстом |
| `read_recent` | Последние сообщения чата |
| `read_block_first_match` | Первое совпадение в блоке |
| `sync_chat` | Синхронизация чата |
| `download_media` | Скачивание медиа |
| `extract_media_text` | OCR извлечение текста |
| `resolve_username` | Получение chat_id по @username |

### Интеграция с Claude Code

Добавить в `.claude/mcp_servers.json`:

```json
{
  "telegram": {
    "command": "telegram-mcp"
  }
}
```

## Структура проекта

```
src/
├── telegram/     # Telegram API client (Telethon)
├── storage/      # Файловое хранилище сообщений
├── search/       # Полнотекстовый поиск
├── extraction/   # OCR (pypdf, pytesseract)
└── mcp/          # MCP server implementation

data/             # Создаётся при установке (в .gitignore)
├── chats.toml    # Whitelist чатов
├── chats/        # Синхронизированные сообщения
├── media/        # Временные медиа файлы
└── session.session  # Telegram session

specs/            # SDD спецификации
tests/            # Тесты
```

## Разработка

```bash
# Тесты
pytest tests/spec/ -v

# Линтер
ruff check src/

# Pre-commit hooks
pre-commit install
```

## Лицензия

MIT
