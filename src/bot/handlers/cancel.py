from pyrogram import Client, filters
from pyrogram.types import Message

from ..task_manager import TASKS
from .common import ensure_force_sub, thread_id_of


def cancel_handler(app: Client) -> None:
    @app.on_message(filters.command("cancel") & filters.incoming)
    async def _cancel(client: Client, message: Message):
        if not await ensure_force_sub(client, message):
            return

        thread_id = thread_id_of(message)
        ok = await TASKS.cancel(message.chat.id, thread_id)

        if ok:
            await message.reply_text("✅ Ongoing task cancel kar diya.", quote=True)
        else:
            await message.reply_text("Koi running task nahi mila.", quote=True)
