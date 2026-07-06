import logging
import uuid
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

log = logging.getLogger(__name__)

# Standard Bot API refuses to serve files > 20 MB to bots.
BOT_API_DOWNLOAD_LIMIT = 20 * 1024 * 1024

def _pick_audio(message):
    if message.voice:
        return message.voice, ".ogg"
    if message.audio:
        suffix = Path(message.audio.file_name or "").suffix or ".mp3"
        return message.audio, suffix
    if message.document and (message.document.mime_type or "").startswith("audio/"):
        suffix = Path(message.document.file_name or "").suffix or ".bin"
        return message.document, suffix
    return None, ""

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = context.bot_data["config"]
    store = context.bot_data["settings"]
    worker = context.bot_data["worker"]
    message = update.effective_message

    audio, suffix = _pick_audio(message)
    if audio is None:
        await message.reply_text("🤔 I can only transcribe voice messages and audio files.")
        return

    if audio.file_size and audio.file_size > BOT_API_DOWNLOAD_LIMIT:
        await message.reply_text(
            "❌ This file is over 20 MB. Telegram's Bot API doesn't let bots "
            "download files that large — try splitting it or compressing it."
        )
        return

    status = await message.reply_text("⬇️ Downloading…")
    config.work_dir.mkdir(parents=True, exist_ok=True)
    path = config.work_dir / f"{uuid.uuid4().hex}{suffix}"
    try:
        tg_file = await audio.get_file()
        await tg_file.download_to_drive(custom_path=path)
    except Exception:
        log.exception("Download failed")
        await status.edit_text("❌ Download failed. Please send the file again.")
        path.unlink(missing_ok=True)
        return

    settings = store.get(update.effective_user.id)
    _, position = worker.enqueue(
        audio_path=path,
        language=settings.language,
        model_key=settings.model,
        model_path=config.whisper.models[settings.model],
        status_message=status,
    )
    if position > 1:
        await status.edit_text(
            f"⏳ In queue — position {position}. One job runs at a time; "
            "I'll start yours automatically."
        )
