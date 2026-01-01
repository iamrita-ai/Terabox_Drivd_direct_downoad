import os
import threading
from flask import Flask, jsonify

from src.logger import setup_logging
from src.bot.client import build_bot_app


def run_bot() -> None:
    """
    Runs Pyrogram bot in a dedicated thread so Flask can bind to $PORT
    (Render 'no ports detected' fix).
    """
    app = build_bot_app()
    # Client.run() is blocking; safe inside this thread.
    app.run()


def create_web() -> Flask:
    web = Flask(__name__)

    @web.get("/")
    def home():
        return jsonify(
            ok=True,
            service="serena-downloader-bot",
            note="Web is only for Render port detection. Bot runs in background thread.",
        )

    @web.get("/health")
    def health():
        return jsonify(ok=True)

    return web


if __name__ == "__main__":
    setup_logging()

    # Start bot thread
    t = threading.Thread(target=run_bot, daemon=True)
    t.start()

    # Start Flask web
    port = int(os.getenv("PORT", "10000"))
    web = create_web()
    web.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
