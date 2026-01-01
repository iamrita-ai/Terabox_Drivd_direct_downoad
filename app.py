import os
import threading
import asyncio
import traceback
from flask import Flask, jsonify

from src.logger import setup_logging
from src.bot.client import build_bot_app

BOT_STATUS = {"bot_ok": False, "error": None, "indexes_ok": False}


def run_bot() -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def main():
        app = build_bot_app()
        try:
            await app.start()

            BOT_STATUS["bot_ok"] = True
            BOT_STATUS["error"] = None

            # indexes should not kill bot
            try:
                await app.db.ensure_indexes()  # type: ignore[attr-defined]
                BOT_STATUS["indexes_ok"] = True
            except Exception:
                BOT_STATUS["indexes_ok"] = False
                BOT_STATUS["error"] = "ensure_indexes failed:\n" + traceback.format_exc()

            from pyrogram import idle
            await idle()

        finally:
            BOT_STATUS["bot_ok"] = False
            try:
                await app.stop()
            except Exception:
                pass

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

    @web.get("/healthz")
    def healthz():
        return jsonify(ok=True, web_ok=True)

    @web.get("/health")
    def health():
        return jsonify(ok=True, web_ok=True, **BOT_STATUS)

    return web


if __name__ == "__main__":
    setup_logging()
    threading.Thread(target=run_bot, daemon=True).start()

    port = int(os.getenv("PORT", "10000"))
    create_web().run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
