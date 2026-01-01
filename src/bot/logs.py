from __future__ import annotations

import textwrap
from pyrogram import Client


async def send_log(client: Client, text: str) -> None:
    try:
        await client.send_message(
            chat_id=client.cfg.LOG_CHANNEL_ID,  # type: ignore[attr-defined]
            text=textwrap.shorten(text, width=3900, placeholder="\n...\n(truncated)"),
            disable_web_page_preview=True,
        )
    except Exception:
        # Don't break main flow
        return
