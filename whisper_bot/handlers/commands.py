from telegram import Update
from telegram.ext import ContextTypes

WELCOME = (
    "👋 Send me a voice message or an audio file and I'll transcribe it with whisper.cpp.\n\n"
    "• /settings — choose language (fa / en / auto) and model\n"
    "• Jobs run one at a time — I'll tell you your position in the queue.\n"
    "• The transcription streams into the reply as it's generated."
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(WELCOME)

async def unauthorized(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message:
        await update.effective_message.reply_text("⛔ Sorry, this is a private bot.")
