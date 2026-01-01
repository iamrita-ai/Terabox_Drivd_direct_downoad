import os
import threading
import asyncio
import traceback
from flask import Flask, jsonify

from src.logger import setup_logging
from src.bot.client import build_bot_app

BOT_STATUS = {"ok": False, "error": None}


def run_bot() -> None:
    # Create an event loop for this thread (Python 3.11+)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def main():
        app = build_bot_app()

        await app.start()
        try:
            await app.db.ensure_indexes()  # type: ignore[attr-defined]
            me = await app.get_me()
            BOT_STATUS["ok"] = True
            BOT_STATUS["error"] = None
            # Keep running
            from pyrogram import idle
            await idle()
        finally:
            BOT_STATUS["ok"] = False
            await app.stop()

    try:
        loop.run_until_complete(main())
    except Exception:
        BOT_STATUS["ok"] = False
        BOT_STATUS["error"] = traceback.format_exc()
        raise
    finally:
        try:
            loop.close()
        except Exception:
            pass


def create_web() -> Flask:
    web = Flask(__name__)

    @web.get("/")
    def home():
        return jsonify(ok=True, service="serena-downloader-bot")

    @web.get("/health")
    def health():
        if not BOT_STATUS["ok"]:
            return jsonify(ok=False, bot_ok=False, error=BOT_STATUS["error"]), 500
        return jsonify(ok=True, bot_ok=True)

    return web


if __name__ == "__main__":
    setup_logging()

    t = threading.Thread(target=run_bot, daemon=True)
    t.start()

    port = int(os.getenv("PORT", "10000"))
    web = create_web()
    web.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
