# Search

## Intent

Модуль поиска по локальному хранилищу сообщений. Работает исключительно с файлами из storage — никогда напрямую с Telegram API.

Основная задача — помочь Claude быстро найти релевантную информацию в истории чатов, минимизируя расход токенов. Поиск двухэтапный: сначала находим блоки с совпадениями (легковесная операция), затем Claude читает только нужные блоки целиком.

Поиск case-insensitive (ILIKE-style). Несколько ключевых слов комбинируются через OR — блок попадает в результат если содержит хотя бы одно слово. Результаты сортируются по свежести: самые новые блоки первыми.

Опционально поддерживается фильтрация по regex (Python re синтаксис) для более точного поиска внутри уже прочитанных сообщений

## Clarifications

### Алгоритм поиска

Q1: Как искать по файлам?
- Простой grep по markdown файлам (достаточно для начала)
- Или сразу делать индекс (whoosh/tantivy)?

Предлагаю начать с grep — проще, быстрее реализовать. Индекс добавим когда понадобится скорость.

A1: Пока только grep

### Формат результата search_blocks

Q2: Что возвращать для каждого блока?
```python
@dataclass
class BlockMatch:
    chat_id: int
    block: str  # "2024-01-15_14"
    chat_name: str
    keyword_counts: dict[str, int]  # {"clickhouse": 3, "merge": 1}
    total_matches: int
```
Достаточно? Нужна ли preview (первые N символов контекста)?

A2: Ок. ДОбавь флаг нужно ли превью. И дефолтное значение для количества первых слов сообщения по которому есть хотя бы 1 кейворд

Q2.1: Сколько слов в preview по умолчанию? Предлагаю 10-15 слов.

A2.1: 10. Если будет мало - потом скажешь и расширим

### Regex поддержка

Q3: В read_recent есть опциональный regex фильтр. Какой синтаксис?
- Python re (стандартный)
- Упрощённый (только *, ?)

Предлагаю Python re — гибче, Claude умеет писать регулярки.

A3: Python re

### Комбинация keywords

Q4: Как комбинировать несколько keywords?
- OR (любое слово) — больше результатов
- AND (все слова) — точнее

Предлагаю OR по умолчанию, но показывать сколько keywords matched.

A4: Ок

### API Search класса

Q5: Предлагаю интерфейс:
```python
class Search:
    def __init__(self, storage: Storage)

    def search_blocks(
        self,
        keywords: list[str],
        chat_id: int | None = None,
        limit: int = 20
    ) -> list[BlockMatch]

    def find_first_match(
        self,
        chat_id: int,
        block: str,
        keywords: list[str]
    ) -> Message | None

    def filter_messages(
        self,
        messages: list[Message],
        keywords: list[str] | None = None,
        regex: str | None = None
    ) -> list[Message]
```

Что добавить/изменить?

A5: Это тех спека

Status: approved
