# Search

Narrative-Hash: acb4a6c0919079d382dffd318e2fea15
Status: committed

## Dependencies

- `re` — regex поиск
- `storage` — доступ к блокам и сообщениям

## State

```python
class Search:
    _storage: Storage
```

## Models

```python
class BlockMatch(BaseModel):
    chat_id: int
    block: str  # "2024-01-15_14"
    chat_name: str
    keyword_counts: dict[str, int]  # {"clickhouse": 3, "merge": 1}
    total_matches: int
    preview: str | None  # первые 10 слов первого совпавшего сообщения
```

## Methods

```python
class Search:
    def __init__(self, storage: Storage) -> None:
        """Инициализация с storage для доступа к файлам."""

    async def search_blocks(
        self,
        keywords: list[str],
        *,
        chat_id: int | None = None,
        limit: int = 20,
        include_preview: bool = False
    ) -> list[BlockMatch]:
        """
        Поиск блоков содержащих ключевые слова.

        Args:
            keywords: список ключевых слов (case-insensitive)
            chat_id: ограничить поиск одним чатом (None = все чаты)
            limit: максимум блоков в результате
            include_preview: включать preview первого совпадения

        Returns:
            Список BlockMatch, отсортированный по дате DESC (свежие первыми).

        Логика:
            - OR между keywords: блок попадает если содержит хотя бы одно слово
            - Подсчёт: сколько раз каждое слово встречается в блоке
            - Preview: первые 10 слов первого сообщения с совпадением
        """

    async def find_first_match(
        self,
        chat_id: int,
        block: str,
        keywords: list[str]
    ) -> Message | None:
        """
        Найти первое сообщение с совпадением в блоке.

        Returns:
            Message с совпадением, None если ничего не найдено.
        """

    def filter_messages(
        self,
        messages: list[Message],
        *,
        keywords: list[str] | None = None,
        regex: str | None = None
    ) -> list[Message]:
        """
        Фильтрация списка сообщений.

        Args:
            messages: входной список
            keywords: фильтр по ключевым словам (OR, case-insensitive)
            regex: фильтр по Python regex

        Returns:
            Отфильтрованный список. Пустой если ничего не совпало.

        Note:
            Если оба фильтра указаны — применяются последовательно (AND).
        """

    def _match_keywords(self, text: str, keywords: list[str]) -> dict[str, int]:
        """
        Подсчёт совпадений keywords в тексте.

        Returns:
            {"keyword1": count1, "keyword2": count2, ...}
            Только keywords с count > 0.
        """

    def _extract_preview(self, text: str, max_words: int = 10) -> str:
        """Извлечь первые N слов из текста."""
```

## Invariants

1. Поиск case-insensitive (lowercase comparison)
2. Keywords комбинируются через OR
3. Результаты всегда отсортированы по дате блока DESC
4. `limit` ограничивает количество результатов, не количество проверенных блоков
5. Preview содержит максимум 10 слов
6. Regex использует синтаксис Python `re` module
7. Пустой список keywords возвращает пустой результат
8. `filter_messages` не модифицирует входной список

## Formulas

```python
# Проверка совпадения keyword
def matches(text: str, keyword: str) -> bool:
    return keyword.lower() in text.lower()

# Подсчёт совпадений
def count_matches(text: str, keyword: str) -> int:
    return text.lower().count(keyword.lower())

# Preview extraction
def extract_preview(text: str, max_words: int = 10) -> str:
    words = text.split()[:max_words]
    return " ".join(words)
```

## Test Cases

### TC1: Поиск по одному keyword

```
GIVEN: блок содержит "clickhouse" 3 раза
WHEN: results = await search.search_blocks(["clickhouse"])
THEN:
  - len(results) >= 1
  - results[0].keyword_counts["clickhouse"] == 3
  - results[0].total_matches == 3
```

### TC2: Поиск по нескольким keywords (OR)

```
GIVEN: блок содержит "clickhouse" 2 раза, "merge" 1 раз
WHEN: results = await search.search_blocks(["clickhouse", "merge"])
THEN:
  - results[0].keyword_counts == {"clickhouse": 2, "merge": 1}
  - results[0].total_matches == 3
```

### TC3: Case-insensitive

```
GIVEN: блок содержит "ClickHouse"
WHEN: results = await search.search_blocks(["clickhouse"])
THEN: len(results) >= 1
```

### TC4: Сортировка по дате

```
GIVEN: 3 блока с совпадениями: 2024-01-15_14, 2024-01-16_10, 2024-01-15_16
WHEN: results = await search.search_blocks(["keyword"])
THEN: [r.block for r in results] == ["2024-01-16_10", "2024-01-15_16", "2024-01-15_14"]
```

### TC5: Лимит результатов

```
GIVEN: 50 блоков с совпадениями
WHEN: results = await search.search_blocks(["keyword"], limit=10)
THEN: len(results) == 10
```

### TC6: Фильтр по chat_id

```
GIVEN: совпадения в чатах 111 и 222
WHEN: results = await search.search_blocks(["keyword"], chat_id=111)
THEN: all(r.chat_id == 111 for r in results)
```

### TC7: Preview включён

```
GIVEN: первое совпадение в сообщении "Вчера обсуждали clickhouse и его особенности работы с данными"
WHEN: results = await search.search_blocks(["clickhouse"], include_preview=True)
THEN: results[0].preview == "Вчера обсуждали clickhouse и его особенности работы с данными"
```

### TC8: Preview выключен

```
GIVEN: include_preview=False (default)
WHEN: results = await search.search_blocks(["keyword"])
THEN: results[0].preview is None
```

### TC9: find_first_match

```
GIVEN: блок с 5 сообщениями, 3-е содержит keyword
WHEN: msg = await search.find_first_match(chat_id, block, ["keyword"])
THEN: msg is not None and "keyword" in msg.text.lower()
```

### TC10: filter_messages с keywords

```
GIVEN: 10 сообщений, 3 содержат "test"
WHEN: filtered = search.filter_messages(messages, keywords=["test"])
THEN: len(filtered) == 3
```

### TC11: filter_messages с regex

```
GIVEN: сообщения с "v1.0", "v2.0", "version"
WHEN: filtered = search.filter_messages(messages, regex=r"v\d+\.\d+")
THEN: len(filtered) == 2  # v1.0 и v2.0
```

### TC12: Пустые keywords

```
GIVEN: keywords = []
WHEN: results = await search.search_blocks([])
THEN: results == []
```

### TC13: Нет совпадений

```
GIVEN: ни один блок не содержит keyword
WHEN: results = await search.search_blocks(["nonexistent"])
THEN: results == []
```

## File Structure

```
src/search/
├── __init__.py
├── search.py      # Search class
└── models.py      # BlockMatch
```
