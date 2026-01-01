from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from .common import ensure_force_sub, try_pin


def start_handler(app: Client) -> None:
    @app.on_message(filters.command("start") & filters.incoming)
    async def _start(client: Client, message: Message):
        user = message.from_user
        if not user:
            return

        # Save user basic info
        await client.db.upsert_user(user.id, user.username)  # type: ignore[attr-defined]

        if not await ensure_force_sub(client, message):
            return

        intro = (
            "Hi! Main Serena Downloader Bot hoon.\n\n"
            "• Google Drive / Direct links (Part-2 me full)\n"
            "• Queue system (multiple links)\n"
            "• Progress + ETA (8 sec interval)\n"
            "• Groups + Topics support\n\n"
            f"Owner: {client.cfg.OWNER_CONTACT_USERNAME}\n"  # type: ignore[attr-defined]
        )

        buttons = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Force sub channel", url="https://t.me/serenaunzipbot")],
                [InlineKeyboardButton("Owner contact", url=client.cfg.OWNER_CONTACT_URL)],  # type: ignore[attr-defined]
            ]
        )

        start_pic = client.cfg.START_PIC  # type: ignore[attr-defined]
        sent = None

        if start_pic:
            try:
                sent = await message.reply_photo(
                    photo=start_pic,
                    caption=intro,
                    reply_markup=buttons,
                    quote=True,
                )
            except Exception:
                sent = await message.reply_text(intro, reply_markup=buttons, quote=True)
        else:
            sent = await message.reply_text(intro, reply_markup=buttons, quote=True)

        # Try pin the start message (DM/group)
        if sent:
            await try_pin(client, sent.chat.id, sent.id)
