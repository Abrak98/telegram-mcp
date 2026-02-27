import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel


class TelegramConfig(BaseModel):
    api_id: int
    api_hash: str
    phone: str
    session_path: Path = Path("data/session")

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

        session_path = os.getenv("TELEGRAM_SESSION_PATH", "data/session")

        return cls(
            api_id=int(api_id),
            api_hash=api_hash,
            phone=phone,
            session_path=Path(session_path),
        )
