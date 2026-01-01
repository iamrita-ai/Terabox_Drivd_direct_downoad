from pyrogram import Client, filters
from pyrogram.types import Message

from .common import ensure_force_sub


def help_handler(app: Client) -> None:
    @app.on_message(filters.command("help") & filters.incoming)
    async def _help(client: Client, message: Message):
        if not await ensure_force_sub(client, message):
            return

        text = (
            "Serena Downloader Bot — Help\n\n"
            "Bot kya karta hai?\n"
            "• Google Drive / TeraBox / Direct links se files download karke Telegram par send karta hai.\n"
            "• Multiple links ek sath bhejoge to queue me 1-by-1 process hoga.\n"
            "• Downloading + Uploading progress bar + ETA show hota hai (8 sec interval).\n"
            "• Video files playable mode me send hoti hain (streaming supported).\n"
            "• Video/Photo/Audio/PDF ka thumbnail generate hota hai.\n"
            "• Folder/multiple files mile to ZIP banake send hota hai.\n\n"
            "Use kaise kare?\n"
            "1) Single link:\n"
            "   https://example.com/file.mp4\n\n"
            "2) Multiple links (same message):\n"
            "   https://...\n"
            "   https://...\n\n"
            "3) .txt file:\n"
            "   Links wali .txt file send karo (andar URLs). Bot links nikal ke queue me chalayega.\n\n"
            "Groups / Topics:\n"
            "• Group me bot ko reply karke link bhejo OR @botusername mention karke bhejo.\n"
            "• Topics me reply-chain se same topic me hi files jayengi.\n\n"
            "Commands:\n"
            "/start   - Introduction\n"
            "/help    - Ye guide\n"
            "/cancel  - Ongoing task cancel\n"
            "/setting - (Premium only) target chat/title/thumbnail/reset\n\n"
            "Limits:\n"
            f"• Free: {client.cfg.FREE_DAILY_TASK_LIMIT} tasks/day, max {client.cfg.FREE_MAX_SIZE_MB} MB, low speed\n"
            f"• Premium: Unlimited/day, max {client.cfg.PREMIUM_MAX_SIZE_MB} MB, high speed\n\n"
            "Owner Commands (Owner only):\n"
            "• /premium <user_id> <days>\n"
            "  Example: /premium 123456789 12\n"
            "  Also: /premium123456789 12\n"
            "  Reply mode: reply to user -> /premium 12\n\n"
            "• /remove_premium <user_id>\n"
            "  Example: /remove_premium 123456789\n"
            "  Also: /remove premium123456789\n"
            "  Reply mode: reply to user -> /remove_premium\n\n"
            "• /broadcast\n"
            "  Reply to any message -> /broadcast\n"
            "  Or: /broadcast Your text here\n\n"
            "Note (Broadcast):\n"
            "• Bot sirf un users ko DM kar sakta hai jinhone bot ko /start kiya ho.\n"
        )

        await message.reply_text(text, quote=True)
