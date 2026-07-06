from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from ..settings_store import LANGUAGES, SettingsStore

LANG_LABELS = {"fa": "🇮🇷 فارسی", "en": "🇬🇧 English", "auto": "🌐 Auto"}

def _mark(label: str, active: bool) -> str:
    return f"✅ {label}" if active else label

def _keyboard(store: SettingsStore, model_keys: list[str], user_id: int) -> InlineKeyboardMarkup:
    s = store.get(user_id)
    language_row = [
        InlineKeyboardButton(
            _mark(LANG_LABELS[lang], s.language == lang), callback_data=f"set:lang:{lang}"
        )
        for lang in LANGUAGES
    ]
    model_rows = [
        [InlineKeyboardButton(_mark(f"🧠 {key}", s.model == key), callback_data=f"set:model:{key}")]
        for key in model_keys
    ]
    done_row = [InlineKeyboardButton("Done ✔️", callback_data="set:close")]
    return InlineKeyboardMarkup([language_row, *model_rows, done_row])

def _text(store: SettingsStore, user_id: int) -> str:
    s = store.get(user_id)
    return (
        "⚙️ Settings\n\n"
        f"Language: {LANG_LABELS[s.language]}\n"
        f"Model: {s.model}"
    )

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    store: SettingsStore = context.bot_data["settings"]
    model_keys = list(context.bot_data["config"].whisper.models)
    user_id = update.effective_user.id
    await update.effective_message.reply_text(
        _text(store, user_id), reply_markup=_keyboard(store, model_keys, user_id)
    )

async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    config = context.bot_data["config"]
    store: SettingsStore = context.bot_data["settings"]
    user_id = query.from_user.id

    if user_id not in config.allowed_user_ids:
        await query.answer("Not allowed", show_alert=True)
        return

    _, kind, *rest = query.data.split(":", 2)
    if kind == "close":
        await query.answer("Saved ✔️")
        await query.edit_message_text(_text(store, user_id))
        return

    value = rest[0]
    if kind == "lang":
        store.set(user_id, language=value)
        await query.answer(f"Language → {value}")
    elif kind == "model":
        store.set(user_id, model=value)
        await query.answer(f"Model → {value}")

    try:
        await query.edit_message_text(
            _text(store, user_id),
            reply_markup=_keyboard(store, list(config.whisper.models), user_id),
        )
    except BadRequest as e:
        if "not modified" not in str(e).lower():
            raise
