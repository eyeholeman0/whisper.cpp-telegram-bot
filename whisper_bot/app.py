import logging

from telegram import BotCommand, Update
from telegram.ext import (
    AIORateLimiter,
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from .config import Config, load_config
from .handlers import audio, commands, settings
from .settings_store import SettingsStore
from .worker import TranscriptionWorker

log = logging.getLogger(__name__)

async def _post_init(app: Application) -> None:
    app.bot_data["worker"].start()
    await app.bot.set_my_commands(
        [
            BotCommand("start", "What this bot does"),
            BotCommand("settings", "Choose language & model"),
        ]
    )

async def _post_shutdown(app: Application) -> None:
    await app.bot_data["worker"].stop()

async def _on_error(update: object, context) -> None:
    log.error("Unhandled error", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "❌ Something went wrong. Please try again."
            )
        except Exception:
            pass

def build_app(cfg: Config) -> Application:
    app = (
        ApplicationBuilder()
        .token(cfg.bot_token)
        .rate_limiter(AIORateLimiter())
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )
    app.bot_data["config"] = cfg
    app.bot_data["settings"] = SettingsStore(cfg.settings_file, list(cfg.whisper.models))
    app.bot_data["worker"] = TranscriptionWorker(cfg)

    allowed = filters.User(user_id=list(cfg.allowed_user_ids))
    app.add_handler(CommandHandler("start", commands.start, filters=allowed))
    app.add_handler(CommandHandler("settings", settings.settings_command, filters=allowed))
    app.add_handler(CallbackQueryHandler(settings.settings_callback, pattern=r"^set:"))
    app.add_handler(
        MessageHandler(
            allowed & (filters.VOICE | filters.AUDIO | filters.Document.AUDIO),
            audio.handle_audio,
        )
    )
    app.add_handler(MessageHandler(~allowed, commands.unauthorized))
    app.add_error_handler(_on_error)
    return app

def main() -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    cfg = load_config()
    build_app(cfg).run_polling(allowed_updates=Update.ALL_TYPES)
