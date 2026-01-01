from __future__ import annotations

import re
from pyrogram import Client, filters
from pyrogram.types import Message

from .common import is_owner

PREM_RE = re.compile(r"^/premium(\d+)?(?:@\w+)?\s*(.*)$", re.IGNORECASE)
REM_RE = re.compile(r"^/(remove_premium|removepremium|remove)\s*(.*)$", re.IGNORECASE)


def premium_handler(app: Client) -> None:
    @app.on_message(filters.incoming & filters.text)
    async def _premium_commands(client: Client, message: Message):
        if not message.from_user or not message.text:
            return

        text = message.text.strip()

        # /premium ...
        m = PREM_RE.match(text)
        if m:
            if not is_owner(client, message.from_user.id):
                return

            tail_id = m.group(1) or ""
            rest = (m.group(2) or "").strip()

            parts = rest.split()
            user_id = None
            days = None

            if tail_id.isdigit():
                user_id = int(tail_id)

            if user_id is None and len(parts) >= 1 and parts[0].isdigit():
                user_id = int(parts[0])
                parts = parts[1:]

            if len(parts) >= 1 and parts[0].isdigit():
                days = int(parts[0])

            if not user_id or not days:
                await message.reply_text("Usage:\n/premium <user_id> <days>\nExample: /premium 123456 12", quote=True)
                return

            exp = await client.db.set_premium(user_id, days)  # type: ignore[attr-defined]
            await message.reply_text(f"✅ Premium set for {user_id} till {exp} (UTC)", quote=True)
            return

        # /remove premium ...
        m2 = REM_RE.match(text)
        if m2:
            if not is_owner(client, message.from_user.id):
                return

            rest = (m2.group(2) or "").strip()
            parts = rest.split()
            if not parts or not parts[0].isdigit():
                await message.reply_text("Usage:\n/remove_premium <user_id>\nExample: /remove_premium 123456", quote=True)
                return
            uid = int(parts[0])
            await client.db.remove_premium(uid)  # type: ignore[attr-defined]
            await message.reply_text(f"✅ Premium removed for {uid}", quote=True)
            return
