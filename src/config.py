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

    # Fixed owners
    OWNER_IDS: Tuple[int, int] = (1598576202, 6518065496)

    # Fixed log channel
    LOG_CHANNEL_ID: int = -1003286415377

    # Force-sub
    FORCE_SUB_CHANNEL: str = os.getenv("FORCE_SUB_CHANNEL", "@serenaunzipbot")

    # Start UI
    START_PIC: str | None = os.getenv("START_PIC")  # URL or Telegram file_id
    OWNER_CONTACT_URL: str = os.getenv("OWNER_CONTACT_URL", "https://t.me/technicalserena")
    OWNER_CONTACT_USERNAME: str = os.getenv("OWNER_CONTACT_USERNAME", "@Xioqui_xin")

    # Progress update interval
    PROGRESS_EDIT_EVERY_SEC: int = int(os.getenv("PROGRESS_EDIT_EVERY_SEC", "8"))

    # Limits (changeable)
    FREE_DAILY_TASK_LIMIT: int = int(os.getenv("FREE_DAILY_TASK_LIMIT", "5"))
    FREE_MAX_SIZE_MB: int = int(os.getenv("FREE_MAX_SIZE_MB", "200"))
    PREMIUM_MAX_SIZE_MB: int = int(os.getenv("PREMIUM_MAX_SIZE_MB", "4096"))  # 4GB

    # Free speed limit for DIRECT downloads (MB/s). (gdrive/terabox may not obey fully)
    FREE_MAX_RATE_MBPS: float = float(os.getenv("FREE_MAX_RATE_MBPS", "1.0"))

    # PDF thumb override (URL or Telegram file_id)
    PDF_THUMB: str | None = os.getenv("PDF_THUMB")

    # Video streaming improvement: remux non-mp4 videos to mp4 (no re-encode)
    REMUX_TO_MP4: bool = os.getenv("REMUX_TO_MP4", "1").strip() not in {"0", "false", "False"}


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
