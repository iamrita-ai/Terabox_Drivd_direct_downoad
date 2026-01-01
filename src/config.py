import os
from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class Config:
    # Telegram
    API_ID: int
    API_HASH: str
    BOT_TOKEN: str

    # Mongo
    MONGO_URI: str
    DB_NAME: str = "serena_bot"

    # Fixed owners (as requested)
    OWNER_IDS: Tuple[int, int] = (1598576202, 6518065496)

    # Fixed log channel (as requested)
    LOG_CHANNEL_ID: int = -1003286415377

    # Force-sub channel (as requested)
    FORCE_SUB_CHANNEL: str = os.getenv("FORCE_SUB_CHANNEL", "@serenaunzipbot")

    # Start UI
    START_PIC: str | None = os.getenv("START_PIC")  # URL or Telegram file_id
    OWNER_CONTACT_URL: str = os.getenv("OWNER_CONTACT_URL", "https://t.me/technicalserena")
    OWNER_CONTACT_USERNAME: str = os.getenv("OWNER_CONTACT_USERNAME", "@Xioqui_xin")

    # Progress update interval (avoid flood)
    PROGRESS_EDIT_EVERY_SEC: int = int(os.getenv("PROGRESS_EDIT_EVERY_SEC", "8"))

    # Limits (you said keep in config.py to change later)
    FREE_DAILY_TASK_LIMIT: int = int(os.getenv("FREE_DAILY_TASK_LIMIT", "5"))
    FREE_MAX_SIZE_MB: int = int(os.getenv("FREE_MAX_SIZE_MB", "200"))
    PREMIUM_MAX_SIZE_MB: int = int(os.getenv("PREMIUM_MAX_SIZE_MB", "4096"))  # 4GB


def load_config() -> Config:
    api_id_raw = os.getenv("API_ID", "").strip()
    api_hash = os.getenv("API_HASH", "").strip()
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    mongo_uri = os.getenv("MONGO_URI", "").strip()

    if not api_id_raw or not api_hash or not bot_token or not mongo_uri:
        raise RuntimeError(
            "Missing env vars. Required: API_ID, API_HASH, BOT_TOKEN, MONGO_URI"
        )

    return Config(
        API_ID=int(api_id_raw),
        API_HASH=api_hash,
        BOT_TOKEN=bot_token,
        MONGO_URI=mongo_uri,
    )
