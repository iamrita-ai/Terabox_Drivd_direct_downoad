from __future__ import annotations

import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message

from .common import is_owner


def broadcast_handler(app: Client) -> None:
    @app.on_message(filters.command("broadcast") & filters.incoming)
    async def _broadcast(client: Client, message: Message):
        if not message.from_user or not is_owner(client, message.from_user.id):
            return

        user_ids = await client.db.all_user_ids()  # type: ignore[attr-defined]
        if not user_ids:
            await message.reply_text("No users in database.", quote=True)
            return

        ok = 0
        fail = 0

        # If reply: copy the replied message to all users
        if message.reply_to_message:
            src_chat = message.chat.id
            src_msg_id = message.reply_to_message.id

            for uid in user_ids:
                try:
                    await client.copy_message(chat_id=uid, from_chat_id=src_chat, message_id=src_msg_id)
                    ok += 1
                except Exception:
                    fail += 1
                await asyncio.sleep(0.05)

        else:
            # else: use text after command
            parts = message.text.split(maxsplit=1)
            if len(parts) < 2:
                await message.reply_text("Reply to a message or use:\n/broadcast <text>", quote=True)
                return
            text = parts[1]

            for uid in user_ids:
                try:
                    await client.send_message(uid, text)
                    ok += 1
                except Exception:
                    fail += 1
                await asyncio.sleep(0.05)

        await message.reply_text(f"✅ Broadcast done.\nSuccess: {ok}\nFailed: {fail}", quote=True)
