from __future__ import annotations

from pyrogram import Client, filters
from pyrogram.types import Message

from .common import is_owner


def _parse_premium(text: str) -> tuple[int | None, int | None]:
    """
    Supports:
      /premium <user_id> <days>
      /premium<user_id> <days>
      /premium@Bot <user_id> <days>
      /premium<user_id>@Bot <days>
    Returns (user_id, days)
    """
    t = (text or "").strip()
    if not t.startswith("/"):
        return None, None

    first, *rest = t.split()
    first = first[1:]  # remove leading '/'

    # remove @Bot suffix
    first = first.split("@", 1)[0]

    if not first.lower().startswith("premium"):
        return None, None

    suffix = first[len("premium"):]  # may contain user_id digits
    args = []
    if suffix:
        args.append(suffix)
    args.extend(rest)

    if len(args) >= 2 and args[0].isdigit() and args[1].isdigit():
        return int(args[0]), int(args[1])

    return None, None


def _parse_remove(text: str) -> int | None:
    """
    Supports:
      /remove_premium <user_id>
      /remov_premium <user_id>
      /removepremium <user_id>
      /remove premium<user_id>
      /remove premium <user_id>
      /remove<user_id>
    Returns user_id
    """
    t = (text or "").strip()
    if not t.startswith("/"):
        return None

    parts = t.split()
    cmd = parts[0][1:]  # remove '/'
    cmd = cmd.split("@", 1)[0].lower()

    rest = parts[1:]

    # allow "/remove premium123" or "/remove premium 123"
    if cmd == "remove" and rest:
        head = rest[0]
        if head.lower().startswith("premium"):
            # premium123 -> 123
            suffix = head[len("premium"):]
            rest = ([suffix] if suffix else []) + rest[1:]

    # allow "/remove123"
    if cmd.startswith("remove") and cmd not in {"remove", "remove_premium", "remov_premium", "removepremium"}:
        suffix = cmd[len("remove"):]
        if suffix.isdigit():
            return int(suffix)

    if cmd not in {"remove", "remove_premium", "remov_premium", "removepremium"}:
        return None

    if rest and rest[0].isdigit():
        return int(rest[0])

    return None


def premium_handler(app: Client) -> None:
    @app.on_message(filters.incoming & filters.text & filters.regex(r"(?i)^/premium"))
    async def _premium(client: Client, message: Message):
        if not message.from_user or not message.text:
            return

        if not is_owner(client, message.from_user.id):
            await message.reply_text("❌ Not authorized (Owner only).", quote=True)
            return

        uid, days = _parse_premium(message.text)

        # allow reply mode: reply to a user's message and send "/premium 12"
        if (uid is None or days is None) and message.reply_to_message and message.reply_to_message.from_user:
            # try parse only days from message
            parts = message.text.split()
            if len(parts) >= 2 and parts[1].isdigit():
                uid = message.reply_to_message.from_user.id
                days = int(parts[1])

        if uid is None or days is None:
            await message.reply_text(
                "Usage:\n"
                "/premium <user_id> <days>\n"
                "or\n"
                "/premium<user_id> <days>\n"
                "or reply to user: /premium <days>\n\n"
                "Example: /premium 123456789 12",
                quote=True,
            )
            return

        exp = await client.db.set_premium(uid, days)  # type: ignore[attr-defined]
        await message.reply_text(f"✅ Premium set for {uid} till {exp} (UTC)", quote=True)

    @app.on_message(filters.incoming & filters.text & filters.regex(r"(?i)^/(remove_premium|remov_premium|removepremium|remove)"))
    async def _remove_premium(client: Client, message: Message):
        if not message.from_user or not message.text:
            return

        if not is_owner(client, message.from_user.id):
            await message.reply_text("❌ Not authorized (Owner only).", quote=True)
            return

        uid = _parse_remove(message.text)

        # allow reply mode: reply to user and send "/remove_premium"
        if uid is None and message.reply_to_message and message.reply_to_message.from_user:
            uid = message.reply_to_message.from_user.id

        if uid is None:
            await message.reply_text(
                "Usage:\n"
                "/remove_premium <user_id>\n"
                "or\n"
                "/remove premium<user_id>\n"
                "or reply to user: /remove_premium\n\n"
                "Example: /remove_premium 123456789",
                quote=True,
            )
            return

        await client.db.remove_premium(uid)  # type: ignore[attr-defined]
        await message.reply_text(f"✅ Premium removed for {uid}", quote=True)
