import re
from datetime import UTC, datetime

from src.telegram.models import MediaType, Message

# Regex patterns
TIME_PATTERN = re.compile(r"^\[(\d{2}):(\d{2})\]")
SENDER_PATTERN = re.compile(r"^\[[\d:]+\]\s+@([^:]+):")
REPLY_PATTERN = re.compile(r"\[Reply #(\d+)\]")
FWD_PATTERN = re.compile(r"\[Fwd:\s*([^\]]+)\]")
MEDIA_PATTERN = re.compile(r"\[(Photo|Video|Document|Voice|Sticker)\]")


def format_message(msg: Message, block_date: datetime) -> str:
    """
    Форматирует Message в строку markdown.

    Args:
        msg: сообщение
        block_date: дата блока (для определения часа)

    Returns:
        "[HH:MM] @username: текст"
    """
    time_str = msg.date.strftime("%H:%M")
    parts = [f"[{time_str}] @{msg.sender_name}:"]

    # Reply
    if msg.reply_to_msg_id:
        parts.append(f"[Reply #{msg.reply_to_msg_id}]")

    # Forward
    if msg.forward_from:
        parts.append(f"[Fwd: {msg.forward_from}]")

    # Media
    if msg.media_type != MediaType.NONE:
        media_label = msg.media_type.value.capitalize()
        parts.append(f"[{media_label}]")

    # Text
    if msg.text:
        parts.append(msg.text)

    return " ".join(parts)


def parse_message_line(line: str, block_date: datetime) -> Message | None:
    """
    Парсит строку markdown обратно в Message.

    Args:
        line: строка формата "[HH:MM] @username: текст"
        block_date: дата блока для восстановления полной даты

    Returns:
        Message или None если строка не соответствует формату
    """
    line = line.strip()
    if not line or not line.startswith("["):
        return None

    # Parse time
    time_match = TIME_PATTERN.match(line)
    if not time_match:
        return None

    hour = int(time_match.group(1))
    minute = int(time_match.group(2))

    # Parse sender
    sender_match = SENDER_PATTERN.match(line)
    if not sender_match:
        return None

    sender_name = sender_match.group(1).strip()

    # Get content after sender
    content_start = sender_match.end()
    content = line[content_start:].strip()

    # Parse reply
    reply_to_msg_id = None
    reply_match = REPLY_PATTERN.search(content)
    if reply_match:
        reply_to_msg_id = int(reply_match.group(1))
        content = content.replace(reply_match.group(0), "").strip()

    # Parse forward
    forward_from = None
    fwd_match = FWD_PATTERN.search(content)
    if fwd_match:
        forward_from = fwd_match.group(1).strip()
        content = content.replace(fwd_match.group(0), "").strip()

    # Parse media
    media_type = MediaType.NONE
    media_match = MEDIA_PATTERN.search(content)
    if media_match:
        media_label = media_match.group(1).lower()
        media_type = MediaType(media_label)
        content = content.replace(media_match.group(0), "").strip()

    # Build datetime
    msg_date = block_date.replace(hour=hour, minute=minute, second=0, microsecond=0)

    return Message(
        id=0,  # ID не сохраняется в markdown, будет 0
        date=msg_date,
        sender_id=None,  # sender_id не сохраняется
        sender_name=sender_name,
        text=content,
        reply_to_msg_id=reply_to_msg_id,
        forward_from=forward_from,
        media_type=media_type,
    )


def format_block_header(block_date: datetime, chat_name: str) -> str:
    """Форматирует заголовок блока."""
    date_str = block_date.strftime("%Y-%m-%d")
    hour = block_date.hour
    return f"# {date_str} {hour:02d}:00-{hour+1:02d}:00 UTC | {chat_name}\n"


def parse_block_header(line: str) -> tuple[datetime, str] | None:
    """
    Парсит заголовок блока.

    Returns:
        (block_date, chat_name) или None
    """
    if not line.startswith("# "):
        return None

    # Format: "# 2024-01-15 14:00-15:00 UTC | Chat Name"
    pattern = re.compile(r"^# (\d{4}-\d{2}-\d{2}) (\d{2}):\d{2}-\d{2}:\d{2} UTC \| (.+)$")
    match = pattern.match(line.strip())
    if not match:
        return None

    date_str = match.group(1)
    hour = int(match.group(2))
    chat_name = match.group(3)

    block_date = datetime.strptime(date_str, "%Y-%m-%d").replace(
        hour=hour, tzinfo=UTC
    )
    return block_date, chat_name


def block_name_to_date(block: str) -> datetime:
    """
    Конвертирует имя блока в datetime.

    Args:
        block: "2024-01-15_14"

    Returns:
        datetime(2024, 1, 15, 14, 0, 0, tzinfo=UTC)
    """
    return datetime.strptime(block, "%Y-%m-%d_%H").replace(tzinfo=UTC)


def date_to_block_name(dt: datetime) -> str:
    """
    Конвертирует datetime в имя блока.

    Args:
        dt: datetime

    Returns:
        "2024-01-15_14"
    """
    return dt.strftime("%Y-%m-%d_%H")
