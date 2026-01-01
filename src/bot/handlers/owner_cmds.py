from __future__ import annotations

import asyncio
from typing import Optional, Tuple

from pyrogram import Client, filters
from pyrogram.types import Message

from .common import is_owner


def _cmd_base(text: str) -> str:
    head = (text or "").strip().split(maxsplit=1)[0]
    if not head.startswith("/"):
        return ""
    c = head[1:]
    c = c.split("@", 1)[0]  # remove @BotUsername
    return c.lower().strip()


def _parse_premium(text: str) -> Tuple[Optional[int], Optional[int]]:
    """
    Supports:
      /premium <user_id> <days>
      /premium<user_id> <days>
      reply to user: /premium <days>
    """
    t = (text or "").strip()
    parts = t.split()
    if not parts:
        return None, None

    base = _cmd_base(t)
    if not base.startswith("premium"):
        return None, None

    suffix = base[len("premium"):]  # maybe digits
    args = parts[1:]  # remaining words after command

    uid = int(suffix) if suffix.isdigit() else None

    if uid is None and len(args) >= 1 and args[0].isdigit():
        uid = int(args[0])
        args = args[1:]

    days = int(args[0]) if len(args) >= 1 and args[0].isdigit() else None
    return uid, days


def _parse_remove(text: str) -> Optional[int]:
    """
    Supports:
      /remove_premium <user_id>
      /remov_premium <user_id>
      /removepremium <user_id>
      /remove premium<user_id>
      /remove premium <user_id>
      /remove<user_id>
    """
    t = (text or "").strip()
    parts = t.split()
    if not parts:
        return None

    base = _cmd_base(t)

    # /remove123
    if base.startswith("remove") and base not in {"remove", "remove_premium", "remov_premium", "removepremium"}:
        suf = base[len("remove"):]
        if suf.isdigit():
            return int(suf)

    if base in {"remove_premium", "remov_premium", "removepremium"}:
        if len(parts) >= 2 and parts[1].isdigit():
            return int(parts[1])
        return None

    if base == "remove":
        if len(parts) >= 2:
            x = parts[1].lower()
            # "premium123" or "premium"
            if x.startswith("premium"):
                suf = x[len("premium"):]
                if suf.isdigit():
                    return int(suf)
                if len(parts) >= 3 and parts[2].isdigit():
                    return int(parts[2])
            # "/remove 123"
            if parts[1].isdigit():
                return int(parts[1])
        return None

    return None


def owner_cmds_handler(app: Client) -> None:
    @app.on_message(filters.incoming & filters.text)
    async def _owner_cmds(client: Client, message: Message):
        if not message.from_user or not message.text:
            return

        text = message.text.strip()
        if not text.startswith("/"):
            return

        base = _cmd_base(text)

        # ----- PREMIUM -----
        if base.startswith("premium"):
            if not is_owner(client, message.from_user.id):
                await message.reply_text("❌ Not authorized (Owner only).", quote=True)
                return

            uid, days = _parse_premium(text)

            # reply-mode: reply to user and do "/premium 12"
            if (uid is None or days is None) and message.reply_to_message and message.reply_to_message.from_user:
                parts = text.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    uid = message.reply_to_message.from_user.id
                    days = int(parts[1])

            if uid is None or days is None:
                await message.reply_text(
                    "Usage:\n"
                    "/premium <user_id> <days>\n"
                    "or: /premium<user_id> <days>\n"
                    "Reply mode: reply to user -> /premium <days>\n\n"
                    "Example: /premium 123456789 12",
                    quote=True,
                )
                return

            exp = await client.db.set_premium(uid, days)  # type: ignore[attr-defined]
            await message.reply_text(f"✅ Premium set for {uid} till {exp} (UTC)", quote=True)
            return

        # ----- REMOVE PREMIUM -----
        if base in {"remove", "remove_premium", "remov_premium", "removepremium"} or base.startswith("remove"):
            if not is_owner(client, message.from_user.id):
                await message.reply_text("❌ Not authorized (Owner only).", quote=True)
                return

            uid = _parse_remove(text)

            # reply-mode: reply to user and do "/remove_premium"
            if uid is None and message.reply_to_message and message.reply_to_message.from_user:
                uid = message.reply_to_message.from_user.id

            if uid is None:
                await message.reply_text(
                    "Usage:\n"
                    "/remove_premium <user_id>\n"
                    "or: /remove premium<user_id>\n"
                    "Reply mode: reply to user -> /remove_premium\n\n"
                    "Example: /remove_premium 123456789",
                    quote=True,
                )
                return

            await client.db.remove_premium(uid)  # type: ignore[attr-defined]
            await message.reply_text(f"✅ Premium removed for {uid}", quote=True)
            return

        # ----- BROADCAST -----
        if base == "broadcast":
            if not is_owner(client, message.from_user.id):
                await message.reply_text("❌ Not authorized (Owner only).", quote=True)
                return

            user_ids = await client.db.all_user_ids()  # type: ignore[attr-defined]
            if not user_ids:
                await message.reply_text("No users in database yet.", quote=True)
                return

            ok = 0
            fail = 0

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
                parts = text.split(maxsplit=1)
                if len(parts) < 2:
                    await message.reply_text("Reply to a message OR use:\n/broadcast <text>", quote=True)
                    return
                msg_text = parts[1]

                for uid in user_ids:
                    try:
                        await client.send_message(uid, msg_text)
                        ok += 1
                    except Exception:
                        fail += 1
                    await asyncio.sleep(0.05)

            await message.reply_text(f"✅ Broadcast done.\nSuccess: {ok}\nFailed: {fail}", quote=True)
            return
