"""Spec tests for Search module."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.search import Search
from src.storage import Storage
from src.telegram.models import MediaType, Message


@pytest.fixture
def storage(tmp_path: Path) -> Storage:
    """Create a storage with test data."""
    data_path = tmp_path / "data"
    data_path.mkdir()

    config_content = """
[group.test1]
id = 111
depth_months = 3
description = "Test Chat 1"

[group.test2]
id = 222
depth_months = 3
description = "Test Chat 2"
"""
    (data_path / "chats.toml").write_text(config_content)
    return Storage(data_path)


@pytest.fixture
def search(storage: Storage) -> Search:
    return Search(storage)


def make_message(
    id: int,
    text: str,
    date: datetime,
    sender: str = "user",
) -> Message:
    return Message(
        id=id,
        date=date,
        sender_id=100,
        sender_name=sender,
        text=text,
        reply_to_msg_id=None,
        forward_from=None,
        media_type=MediaType.NONE,
    )


class TestSearchBlocks:
    """Tests for search_blocks."""

    @pytest.mark.asyncio
    async def test_search_single_keyword(self, storage: Storage, search: Search) -> None:
        """TC1: Поиск по одному keyword."""
        date = datetime(2024, 1, 15, 14, 0, tzinfo=UTC)
        messages = [
            make_message(1, "clickhouse is great", date.replace(minute=5)),
            make_message(2, "clickhouse performance", date.replace(minute=10)),
            make_message(3, "clickhouse rocks", date.replace(minute=15)),
        ]
        await storage.write_messages(111, "Test Chat 1", messages)

        results = await search.search_blocks(["clickhouse"])

        assert len(results) >= 1
        assert results[0].keyword_counts["clickhouse"] == 3
        assert results[0].total_matches == 3

    @pytest.mark.asyncio
    async def test_search_multiple_keywords_or(
        self, storage: Storage, search: Search
    ) -> None:
        """TC2: Поиск по нескольким keywords (OR)."""
        date = datetime(2024, 1, 15, 14, 0, tzinfo=UTC)
        messages = [
            make_message(1, "clickhouse clickhouse", date.replace(minute=5)),
            make_message(2, "merge tree", date.replace(minute=10)),
        ]
        await storage.write_messages(111, "Test Chat 1", messages)

        results = await search.search_blocks(["clickhouse", "merge"])

        assert len(results) >= 1
        assert results[0].keyword_counts == {"clickhouse": 2, "merge": 1}
        assert results[0].total_matches == 3

    @pytest.mark.asyncio
    async def test_search_case_insensitive(
        self, storage: Storage, search: Search
    ) -> None:
        """TC3: Case-insensitive."""
        date = datetime(2024, 1, 15, 14, 0, tzinfo=UTC)
        messages = [make_message(1, "ClickHouse is Great", date)]
        await storage.write_messages(111, "Test Chat 1", messages)

        results = await search.search_blocks(["clickhouse"])

        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_search_sorted_by_date(
        self, storage: Storage, search: Search
    ) -> None:
        """TC4: Сортировка по дате."""
        # Create messages in different blocks
        dates = [
            datetime(2024, 1, 15, 14, 0, tzinfo=UTC),
            datetime(2024, 1, 16, 10, 0, tzinfo=UTC),
            datetime(2024, 1, 15, 16, 0, tzinfo=UTC),
        ]
        for i, date in enumerate(dates):
            msg = make_message(i, "keyword here", date)
            await storage.write_messages(111, "Test", [msg])

        results = await search.search_blocks(["keyword"])

        blocks = [r.block for r in results]
        assert blocks == ["2024-01-16_10", "2024-01-15_16", "2024-01-15_14"]

    @pytest.mark.asyncio
    async def test_search_limit(self, storage: Storage, search: Search) -> None:
        """TC5: Лимит результатов."""
        # Create many blocks
        for i in range(50):
            date = datetime(2024, 1, 15 + i // 24, i % 24, 0, tzinfo=UTC)
            msg = make_message(i, "keyword", date)
            await storage.write_messages(111, "Test", [msg])

        results = await search.search_blocks(["keyword"], limit=10)

        assert len(results) == 10

    @pytest.mark.asyncio
    async def test_search_filter_by_chat_id(
        self, storage: Storage, search: Search
    ) -> None:
        """TC6: Фильтр по chat_id."""
        date = datetime(2024, 1, 15, 14, 0, tzinfo=UTC)

        # Messages in two chats
        await storage.write_messages(111, "Chat1", [make_message(1, "keyword", date)])
        await storage.write_messages(
            222, "Chat2", [make_message(2, "keyword", date.replace(minute=5))]
        )

        results = await search.search_blocks(["keyword"], chat_id=111)

        assert all(r.chat_id == 111 for r in results)

    @pytest.mark.asyncio
    async def test_search_with_preview(
        self, storage: Storage, search: Search
    ) -> None:
        """TC7: Preview включён."""
        date = datetime(2024, 1, 15, 14, 0, tzinfo=UTC)
        messages = [
            make_message(
                1,
                "Вчера обсуждали clickhouse и его особенности работы с данными",
                date,
            )
        ]
        await storage.write_messages(111, "Test", messages)

        results = await search.search_blocks(["clickhouse"], include_preview=True)

        assert len(results) >= 1
        assert results[0].preview is not None
        assert "clickhouse" in results[0].preview

    @pytest.mark.asyncio
    async def test_search_without_preview(
        self, storage: Storage, search: Search
    ) -> None:
        """TC8: Preview выключен."""
        date = datetime(2024, 1, 15, 14, 0, tzinfo=UTC)
        await storage.write_messages(111, "Test", [make_message(1, "keyword", date)])

        results = await search.search_blocks(["keyword"])

        assert results[0].preview is None

    @pytest.mark.asyncio
    async def test_search_empty_keywords(
        self, storage: Storage, search: Search
    ) -> None:
        """TC12: Пустые keywords."""
        results = await search.search_blocks([])
        assert results == []

    @pytest.mark.asyncio
    async def test_search_no_matches(self, storage: Storage, search: Search) -> None:
        """TC13: Нет совпадений."""
        date = datetime(2024, 1, 15, 14, 0, tzinfo=UTC)
        await storage.write_messages(111, "Test", [make_message(1, "hello world", date)])

        results = await search.search_blocks(["nonexistent"])

        assert results == []


class TestFindFirstMatch:
    """Tests for find_first_match."""

    @pytest.mark.asyncio
    async def test_find_first_match(self, storage: Storage, search: Search) -> None:
        """TC9: find_first_match."""
        date = datetime(2024, 1, 15, 14, 0, tzinfo=UTC)
        messages = [
            make_message(1, "no match here", date.replace(minute=5)),
            make_message(2, "no match either", date.replace(minute=10)),
            make_message(3, "keyword found", date.replace(minute=15)),
            make_message(4, "keyword again", date.replace(minute=20)),
        ]
        await storage.write_messages(111, "Test", messages)

        msg = await search.find_first_match(111, "2024-01-15_14", ["keyword"])

        assert msg is not None
        assert "keyword" in msg.text.lower()


class TestFilterMessages:
    """Tests for filter_messages."""

    def test_filter_with_keywords(self, search: Search) -> None:
        """TC10: filter_messages с keywords."""
        date = datetime(2024, 1, 15, 14, 0, tzinfo=UTC)
        messages = [
            make_message(1, "test message", date),
            make_message(2, "another one", date),
            make_message(3, "test again", date),
            make_message(4, "TEST uppercase", date),
        ]

        filtered = search.filter_messages(messages, keywords=["test"])

        assert len(filtered) == 3

    def test_filter_with_regex(self, search: Search) -> None:
        """TC11: filter_messages с regex."""
        date = datetime(2024, 1, 15, 14, 0, tzinfo=UTC)
        messages = [
            make_message(1, "version v1.0", date),
            make_message(2, "version v2.0", date),
            make_message(3, "just version text", date),
        ]

        filtered = search.filter_messages(messages, regex=r"v\d+\.\d+")

        assert len(filtered) == 2

    def test_filter_with_both(self, search: Search) -> None:
        """filter_messages с keywords и regex (AND)."""
        date = datetime(2024, 1, 15, 14, 0, tzinfo=UTC)
        messages = [
            make_message(1, "test v1.0", date),
            make_message(2, "test message", date),
            make_message(3, "just v2.0", date),
        ]

        filtered = search.filter_messages(
            messages, keywords=["test"], regex=r"v\d+\.\d+"
        )

        assert len(filtered) == 1
        assert "test" in filtered[0].text
        assert "v1.0" in filtered[0].text
