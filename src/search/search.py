import re

from src.storage import Storage
from src.telegram.models import Message

from .models import BlockMatch

PREVIEW_WORDS = 10


class Search:
    """Поиск по локальному хранилищу сообщений."""

    def __init__(self, storage: Storage) -> None:
        """Инициализация с storage для доступа к файлам."""
        self._storage = storage

    async def search_blocks(
        self,
        keywords: list[str],
        *,
        chat_id: int | None = None,
        limit: int = 20,
        include_preview: bool = False,
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
        """
        if not keywords:
            return []

        results: list[BlockMatch] = []

        # Определяем чаты для поиска
        if chat_id is not None:
            chat_ids = [chat_id]
        else:
            configs = self._storage.list_chat_configs()
            chat_ids = [c.id for c in configs]

        for cid in chat_ids:
            blocks = await self._storage.list_blocks(cid)
            config = self._storage.get_chat_config(cid)
            chat_name = config.alias if config else str(cid)

            for block in blocks:
                messages = await self._storage.read_block(cid, block)
                if not messages:
                    continue

                # Подсчёт совпадений
                block_text = "\n".join(m.text for m in messages)
                keyword_counts = self._match_keywords(block_text, keywords)

                if not keyword_counts:
                    continue

                total = sum(keyword_counts.values())

                # Preview
                preview = None
                if include_preview:
                    for msg in messages:
                        if any(kw.lower() in msg.text.lower() for kw in keywords):
                            preview = self._extract_preview(msg.text, PREVIEW_WORDS)
                            break

                results.append(
                    BlockMatch(
                        chat_id=cid,
                        block=block,
                        chat_name=chat_name,
                        keyword_counts=keyword_counts,
                        total_matches=total,
                        preview=preview,
                    )
                )

                if len(results) >= limit:
                    break

            if len(results) >= limit:
                break

        # Сортировка по блоку (дате) DESC
        results.sort(key=lambda r: r.block, reverse=True)
        return results[:limit]

    async def find_first_match(
        self, chat_id: int, block: str, keywords: list[str]
    ) -> Message | None:
        """
        Найти первое сообщение с совпадением в блоке.

        Returns:
            Message с совпадением, None если ничего не найдено.
        """
        messages = await self._storage.read_block(chat_id, block)

        for msg in messages:
            if any(kw.lower() in msg.text.lower() for kw in keywords):
                return msg

        return None

    def filter_messages(
        self,
        messages: list[Message],
        *,
        keywords: list[str] | None = None,
        regex: str | None = None,
    ) -> list[Message]:
        """
        Фильтрация списка сообщений.

        Args:
            messages: входной список
            keywords: фильтр по ключевым словам (OR, case-insensitive)
            regex: фильтр по Python regex

        Returns:
            Отфильтрованный список. Пустой если ничего не совпало.
        """
        result = list(messages)

        if keywords:
            result = [
                m for m in result if any(kw.lower() in m.text.lower() for kw in keywords)
            ]

        if regex:
            pattern = re.compile(regex)
            result = [m for m in result if pattern.search(m.text)]

        return result

    def _match_keywords(self, text: str, keywords: list[str]) -> dict[str, int]:
        """
        Подсчёт совпадений keywords в тексте.

        Returns:
            {"keyword1": count1, "keyword2": count2, ...}
            Только keywords с count > 0.
        """
        text_lower = text.lower()
        counts = {}

        for kw in keywords:
            count = text_lower.count(kw.lower())
            if count > 0:
                counts[kw] = count

        return counts

    def _extract_preview(self, text: str, max_words: int = 10) -> str:
        """Извлечь первые N слов из текста."""
        words = text.split()[:max_words]
        return " ".join(words)
