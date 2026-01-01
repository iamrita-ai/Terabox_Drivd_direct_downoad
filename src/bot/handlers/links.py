from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import List

from pyrogram import Client, filters
from pyrogram.types import Message

from .common import ensure_force_sub, thread_id_of
from ..task_manager import TASKS
from ..queue_runner import ensure_runner

URL_RE = re.compile(r"(https?://[^\s]+)", re.IGNORECASE)


def _extract_urls(text: str) -> List[str]:
    return [m.group(1).strip().strip(").,]}>\"'") for m in URL_RE.finditer(text or "")]


def _needs_mention_in_group(client: Client, msg: Message) -> bool:
    if msg.chat.type not in ("group", "supergroup"):
        return False

    # allow if reply to bot
    if msg.reply_to_message and msg.reply_to_message.from_user and msg.reply_to_message.from_user.is_bot:
        return False

    # allow if bot mentioned in text
    try:
        me = client.me or None
        username = (me.username if me else "") or ""
        if username and (f"@{username.lower()}" in (msg.text or "").lower()):
            return False
    except Exception:
        pass

    return True


def links_handler(app: Client) -> None:
    @app.on_message(filters.incoming & (filters.text | filters.document))
    async def _in(client: Client, message: Message):
        if not message.from_user:
            return

        if not await ensure_force_sub(client, message):
            return

        if _needs_mention_in_group(client, message):
            return

        urls: List[str] = []

        # 1) text urls
        if message.text:
            urls.extend(_extract_urls(message.text))

        # 2) .txt document with urls
        if message.document and message.document.file_name:
            name = message.document.file_name.lower()
            if name.endswith(".txt"):
                tmp_dir = tempfile.mkdtemp(prefix="txt_", dir="/tmp")
                try:
                    txt_path = await client.download_media(message, file_name=str(Path(tmp_dir) / "links.txt"))
                    if txt_path and Path(txt_path).exists():
                        content = Path(txt_path).read_text(errors="ignore")
                        urls.extend(_extract_urls(content))
                finally:
                    # cleanup txt dir
                    try:
                        for p in Path(tmp_dir).rglob("*"):
                            try:
                                p.unlink()
                            except Exception:
                                pass
                        Path(tmp_dir).rmdir()
                    except Exception:
                        pass

        # nothing found
        if not urls:
            return

        # store user
        await client.db.upsert_user(message.from_user.id, message.from_user.username)  # type: ignore[attr-defined]

        thread_id = thread_id_of(message)

        # enqueue as one job (with many urls)
        await TASKS.enqueue(
            message.chat.id,
            thread_id,
            {
                "chat_id": message.chat.id,
                "thread_id": thread_id,
                "origin_msg_id": message.id,
                "from_user_id": message.from_user.id,
                "from_username": message.from_user.username,
                "links": urls,
            },
        )

        await ensure_runner(client, message.chat.id, thread_id)

        await message.reply_text(
            f"✅ Added to queue.\nTotal links: {len(urls)}",
            quote=True,
        )
