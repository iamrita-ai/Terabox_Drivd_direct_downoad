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

    # Attach config/db
    app.cfg = cfg  # type: ignore[attr-defined]
    app.db = db    # type: ignore[attr-defined]

    # Register handlers
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

    return app
