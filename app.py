import os
import threading
import traceback
from flask import Flask, jsonify

from src.logger import setup_logging
from src.bot.client import build_bot_app

BOT_STATUS = {"bot_ok": False, "error": None, "indexes_ok": False}


def create_web() -> Flask:
    web = Flask(__name__)

    @web.get("/")
    def home():
        return jsonify(ok=True, service="serena-downloader-bot")

    # Render health check should hit this (always 200)
    @web.get("/healthz")
    def healthz():
        return jsonify(ok=True, web_ok=True)

    # Bot diagnostic (always 200)
    @web.get("/health")
    def health():
        return jsonify(ok=True, web_ok=True, **BOT_STATUS)

    return web


def run_web() -> None:
    port = int(os.getenv("PORT", "10000"))
    web = create_web()
    web.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


async def run_bot_async() -> None:
    from pyrogram import idle

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

        # IMPORTANT: idle must run in MAIN thread -> now it will
        await idle()

    except Exception:
        BOT_STATUS["bot_ok"] = False
        BOT_STATUS["error"] = traceback.format_exc()
        raise
    finally:
        BOT_STATUS["bot_ok"] = False
        try:
            await app.stop()
        except Exception:
            pass


if __name__ == "__main__":
    setup_logging()

    # Start Flask in background thread (Render port detection)
    threading.Thread(target=run_web, daemon=True).start()

    # Run bot in MAIN thread (signals work)
    import asyncio
    asyncio.run(run_bot_async())
