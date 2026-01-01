import logging
from typing import Optional

from pyrogram import Client
from pyrogram.errors import UserNotParticipant, ChatAdminRequired
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

log = logging.getLogger("handlers.common")


def is_owner(app: Client, user_id: int) -> bool:
    return user_id in app.cfg.OWNER_IDS  # type: ignore[attr-defined]


async def ensure_force_sub(app: Client, msg: Message) -> bool:
    """
    Returns True if user can proceed, else sends join prompt and returns False.
    """
    channel = app.cfg.FORCE_SUB_CHANNEL  # type: ignore[attr-defined]
    if not channel:
        return True

    user = msg.from_user
    if not user:
        return False

    try:
        member = await app.get_chat_member(channel, user.id)
        # member.status can be "member/administrator/creator"
        return True
    except UserNotParticipant:
        buttons = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Force sub channel", url=f"https://t.me/{channel.lstrip('@')}")],
                [InlineKeyboardButton("Owner contact", url=app.cfg.OWNER_CONTACT_URL)],  # type: ignore[attr-defined]
            ]
        )
        await msg.reply_text(
            f"Use karne se pehle channel join karo: {channel}\n\n"
            "Join karke /start dobara bhejo.",
            reply_markup=buttons,
            quote=True,
        )
        return False
    except ChatAdminRequired:
        # If bot can't check membership, don't block usage.
        log.warning("ChatAdminRequired while checking force-sub; allowing access.")
        return True
    except Exception as e:
        log.exception("Force-sub check failed: %r", e)
        return True


async def try_pin(app: Client, chat_id: int, message_id: int) -> None:
    try:
        await app.pin_chat_message(chat_id, message_id, disable_notification=True)
    except Exception:
        # Ignore: bot may not have pin rights in groups
        return


def thread_id_of(msg: Message) -> Optional[int]:
    # For topics: message_thread_id exists in groups with topics
    return getattr(msg, "message_thread_id", None)
