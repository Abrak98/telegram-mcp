from pathlib import Path

import tomli

from .models import ChatConfig


def load_chat_configs(config_path: Path) -> dict[int, ChatConfig]:
    """
    Загрузка конфигурации чатов из chats.toml.

    Returns:
        dict[chat_id, ChatConfig]
    """
    if not config_path.exists():
        return {}

    with open(config_path, "rb") as f:
        data = tomli.load(f)

    configs: dict[int, ChatConfig] = {}

    for chat_type, chats in data.items():
        for alias, chat_data in chats.items():
            config = ChatConfig(
                id=chat_data["id"],
                alias=alias,
                type=chat_type,
                depth_months=chat_data.get("depth_months", 3),
                description=chat_data.get("description", ""),
            )
            configs[config.id] = config

    return configs
