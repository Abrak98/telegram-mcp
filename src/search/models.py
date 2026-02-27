from pydantic import BaseModel


class BlockMatch(BaseModel):
    """Результат поиска — блок с совпадениями."""

    chat_id: int
    block: str  # "2024-01-15_14"
    chat_name: str
    keyword_counts: dict[str, int]  # {"clickhouse": 3, "merge": 1}
    total_matches: int
    preview: str | None = None  # первые 10 слов первого совпавшего сообщения
