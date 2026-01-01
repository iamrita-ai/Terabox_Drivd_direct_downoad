import os
import threading
import asyncio
import traceback
from flask import Flask, jsonify

from src.logger import setup_logging
from src.bot.client import build_bot_app

BOT_STATUS = {"bot_ok": False, "error": None}


def run_bot() -> None:
    # Create an event loop for this thread (Python 3.11+)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def main():
        app = build_bot_app()

        try:
            await app.start()
            await app.db.ensure_indexes()  # type: ignore[attr-defined]
            me = await app.get_me()
            BOT_STATUS["bot_ok"] = True
            BOT_STATUS["error"] = None

            from pyrogram import idle
            await idle()
        except Exception:
            BOT_STATUS["bot_ok"] = False
            BOT_STATUS["error"] = traceback.format_exc()
            raise
        finally:
            try:
                await app.stop()
            except Exception:
                pass
            BOT_STATUS["bot_ok"] = False

    try:
        loop.run_until_complete(main())
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

    # Render health check should hit this (ALWAYS 200)
    @web.get("/healthz")
    def healthz():
        return jsonify(ok=True, web_ok=True)

    # Bot diagnostic (ALWAYS 200 so deploy doesn't fail)
    @web.get("/health")
    def health():
        return jsonify(ok=True, web_ok=True, **BOT_STATUS)

    return web


if __name__ == "__main__":
    setup_logging()

    t = threading.Thread(target=run_bot, daemon=True)
    t.start()

    port = int(os.getenv("PORT", "10000"))
    web = create_web()
    web.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
