from __future__ import annotations

from typing import Dict, Optional

from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
)

from .common import ensure_force_sub


PENDING: Dict[int, str] = {}  # user_id -> action


def _menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Set Chat Id", callback_data="st_chat"),
                InlineKeyboardButton("Set Title", callback_data="st_title"),
            ],
            [
                InlineKeyboardButton("Set Thumbnail", callback_data="st_thumb"),
                InlineKeyboardButton("Setting Reset", callback_data="st_reset"),
            ],
        ]
    )


async def _is_premium(client: Client, user_id: int) -> bool:
    return await client.db.is_premium(user_id)  # type: ignore[attr-defined]


def settings_handler(app: Client) -> None:
    @app.on_message(filters.command("setting") & filters.incoming)
    async def _setting(client: Client, message: Message):
        if not message.from_user:
            return
        if not await ensure_force_sub(client, message):
            return

        if not await _is_premium(client, message.from_user.id):
            await message.reply_text("❌ Free users can't use /setting.\nPremium required.", quote=True)
            return

        await message.reply_text("Settings:", reply_markup=_menu(), quote=True)

    @app.on_callback_query(filters.regex(r"^st_"))
    async def _setting_cb(client: Client, cq: CallbackQuery):
        if not cq.from_user:
            return

        uid = cq.from_user.id
        if not await _is_premium(client, uid):
            await cq.answer("Premium required", show_alert=True)
            return

        data = cq.data

        if data == "st_chat":
            PENDING[uid] = "chat"
            await cq.message.reply_text("Send target Chat ID (example: -1001234567890).", quote=True)
            await cq.answer()
            return

        if data == "st_title":
            PENDING[uid] = "title"
            await cq.message.reply_text("Send title (zip/title label).", quote=True)
            await cq.answer()
            return

        if data == "st_thumb":
            PENDING[uid] = "thumb"
            await cq.message.reply_text("Send a PHOTO (thumbnail) now.", quote=True)
            await cq.answer()
            return

        if data == "st_reset":
            await client.db.reset_settings(uid)  # type: ignore[attr-defined]
            PENDING.pop(uid, None)
            await cq.message.reply_text("✅ Settings reset.", quote=True)
            await cq.answer()
            return

        await cq.answer()

    @app.on_message(filters.incoming)
    async def _setting_input(client: Client, message: Message):
        if not message.from_user:
            return

        uid = message.from_user.id
        action: Optional[str] = PENDING.get(uid)
        if not action:
            return

        if not await _is_premium(client, uid):
            PENDING.pop(uid, None)
            return

        if action == "chat":
            if not message.text or not message.text.strip().lstrip("-").isdigit():
                await message.reply_text("Invalid Chat ID. Example: -1001234567890", quote=True)
                return
            chat_id = int(message.text.strip())
            await client.db.set_setting(uid, "target_chat_id", chat_id)  # type: ignore[attr-defined]
            PENDING.pop(uid, None)
            await message.reply_text(f"✅ Target Chat ID set: {chat_id}", quote=True)
            return

        if action == "title":
            if not message.text or not message.text.strip():
                await message.reply_text("Send a non-empty title.", quote=True)
                return
            title = message.text.strip()[:64]
            await client.db.set_setting(uid, "title", title)  # type: ignore[attr-defined]
            PENDING.pop(uid, None)
            await message.reply_text(f"✅ Title set: {title}", quote=True)
            return

        if action == "thumb":
            fid = None
            if message.photo:
                fid = message.photo.file_id
            elif message.document and (message.document.mime_type or "").startswith("image/"):
                fid = message.document.file_id

            if not fid:
                await message.reply_text("Please send a PHOTO (image).", quote=True)
                return

            await client.db.set_setting(uid, "thumb_file_id", fid)  # type: ignore[attr-defined]
            PENDING.pop(uid, None)
            await message.reply_text("✅ Thumbnail saved.", quote=True)
            return
