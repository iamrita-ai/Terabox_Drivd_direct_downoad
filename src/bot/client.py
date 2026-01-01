import logging
from pyrogram import Client

from src.config import load_config
from src.db import Database

log = logging.getLogger("bot")


def build_bot_app() -> Client:
    cfg = load_config()
    db = Database(cfg)

    app = Client(
        name="serena_bot",
        api_id=cfg.API_ID,
        api_hash=cfg.API_HASH,
        bot_token=cfg.BOT_TOKEN,
        in_memory=True,
        workers=50,
    )

    app.cfg = cfg  # type: ignore[attr-defined]
    app.db = db    # type: ignore[attr-defined]

    from .handlers.start import start_handler
    from .handlers.help import help_handler
    from .handlers.cancel import cancel_handler
    from .handlers.links import links_handler
    from .handlers.premium import premium_handler
    from .handlers.broadcast import broadcast_handler
    from .handlers.settings import settings_handler

    start_handler(app)
    help_handler(app)
    cancel_handler(app)
    links_handler(app)
    premium_handler(app)
    broadcast_handler(app)
    settings_handler(app)

    @app.on_start()
    async def _on_start(_: Client):
        log.info("Bot starting...")
        await app.db.ensure_indexes()  # type: ignore[attr-defined]
        me = await app.get_me()
        log.info("Logged in as @%s", me.username)
        log.info("Mongo indexes ensured.")

    @app.on_stop()
    async def _on_stop(_: Client):
        log.info("Bot stopped.")

    return app
