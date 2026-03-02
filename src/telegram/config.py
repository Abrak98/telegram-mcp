import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel


def _default_session_path() -> Path:
    """Session stored in ~/.config/telegram-mcp/ for security."""
    config_dir = Path.home() / ".config" / "telegram-mcp"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_dir.chmod(0o700)
    return config_dir / "session"


class TelegramConfig(BaseModel):
    api_id: int
    api_hash: str
    phone: str
    session_path: Path = Path.home() / ".config" / "telegram-mcp" / "session"

    @classmethod
    def from_env(cls, env_path: Path | None = None) -> "TelegramConfig":
        if env_path:
            load_dotenv(env_path)
        else:
            load_dotenv()

        api_id = os.getenv("TELEGRAM_API_ID")
        api_hash = os.getenv("TELEGRAM_API_HASH")
        phone = os.getenv("TELEGRAM_PHONE")

        if not api_id:
            raise ValueError("TELEGRAM_API_ID not found in environment")
        if not api_hash:
            raise ValueError("TELEGRAM_API_HASH not found in environment")
        if not phone:
            raise ValueError("TELEGRAM_PHONE not found in environment")

        default_session = Path.home() / ".config" / "telegram-mcp" / "session"
        session_path = os.getenv("TELEGRAM_SESSION_PATH", str(default_session))

        return cls(
            api_id=int(api_id),
            api_hash=api_hash,
            phone=phone,
            session_path=Path(session_path),
        )
