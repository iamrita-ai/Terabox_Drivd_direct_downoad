from pyrogram import Client, filters
from pyrogram.types import Message

from .common import ensure_force_sub


def help_handler(app: Client) -> None:
    @app.on_message(filters.command("help") & filters.incoming)
    async def _help(client: Client, message: Message):
        if not await ensure_force_sub(client, message):
            return

        text = (
            "Help / Guide\n\n"
            "Send karo:\n"
            "• Direct downloadable links\n"
            "• Google Drive links\n"
            "• Multiple links ek saath (queue)\n"
            "• .txt file with links (Part-2)\n\n"
            "Commands:\n"
            "/start - intro\n"
            "/help - guide\n"
            "/cancel - running task cancel\n\n"
            "Limits (Config.py):\n"
            "• Free: 5 tasks/day, max 200MB, low speed (Part-3 enforce)\n"
            "• Premium: unlimited, max 4GB, high speed (Part-3 enforce)\n"
        )
        await message.reply_text(text, quote=True)
