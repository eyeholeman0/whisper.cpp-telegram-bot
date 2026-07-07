# 🎙 Whisper Telegram Bot

A self-hosted Telegram bot that transcribes voice messages and audio files
using [whisper.cpp](https://github.com/ggml-org/whisper.cpp) — fully local,
no cloud APIs, no per-minute fees.

Send a voice note, watch the transcription **stream into the reply in
real time** as Whisper decodes it.

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

## ✨ Features

- **100% local transcription** — audio never leaves your server
- **Live streaming replies** — the message updates as segments are decoded,
  rendered with Telegram's smooth streaming animation
- **FIFO job queue** — one transcription at a time (CPU-friendly), with live
  queue-position updates for waiting jobs
- **⚙️ `/settings` menu** — switch language (`fa` / `en` / `auto`) and Whisper
  model from an inline keyboard; preferences persist across restarts
- **Multiple input types** — voice messages, music/audio files, and audio
  documents (`ogg`, `mp3`, `m4a`, `wav`, ...)
- **Private by default** — responds only to whitelisted Telegram user IDs
- **Friendly error handling** — clear messages for oversized files, undecodable
  audio, timeouts, and crashes
- **Easy deployment** — single JSON config, setup script, and systemd unit

## 📸 How it looks

```

You:  🎤 (voice message, 2:14)

Bot:  ⏳ In queue — position 2. One job runs at a time.

Bot:  🎙 Transcribing… (model: large-v3-turbo · language: fa)

Bot:  سلام، در این جلسه قرار است در مورد… ▌   ← streams live

Bot:  (final full transcription as a normal text message)

```

## 🧩 Requirements

| Dependency | Notes |
|---|---|
| Python 3.10+ | with `python3-venv` |
| [whisper.cpp](https://github.com/ggml-org/whisper.cpp) | built `whisper-cli` binary |
| A GGML Whisper model | e.g. `ggml-large-v3-turbo.bin` |
| `ffmpeg` | converts Telegram's ogg/opus to 16 kHz WAV |
| A Telegram bot token | free, from [@BotFather](https://t.me/BotFather) |

### Building whisper.cpp (if you haven't already)

```

git clone https://github.com/ggml-org/whisper.cpp

cd whisper.cpp

cmake -B build && cmake --build build -j --config Release

sh ./models/download-ggml-model.sh large-v3-turbo

sh ./models/download-ggml-model.sh large-v3-q5_0

```

## 🚀 Quick start

```

git clone https://github.com/eyeholemano/whisper.cpp-telegram-bot

cd whisper.cpp-telegram-bot

sudo apt install ffmpeg python3-venv   # system deps

bash deploy/[setup.sh](http://setup.sh)                    # creates venv + installs Python deps

cp config.example.json config.json

nano config.json                        # see Configuration below

.venv/bin/python -m whisper_bot

```

Then open your bot in Telegram, hit **Start**, and send a voice message.

> **Getting your Telegram user ID:** message [@userinfobot](https://t.me/userinfobot)
> and put the numeric ID in `allowed_user_ids`. The bot ignores everyone else.

## ⚙️ Configuration

All secrets and machine-specific paths live in `config.json`
(**gitignored** — never commit it). `config.example.json` is the template:

```

{

"telegram": {

"bot_token": "123456:PASTE-YOUR-BOTFATHER-TOKEN"

},

"access": {

"allowed_user_ids": [111111111]

},

"whisper": {

"cli_path": "/path/to/whisper.cpp/build/bin/whisper-cli",

"ffmpeg_path": "ffmpeg",

"threads": 4,

"timeout_seconds": 1800,

"models": {

"large-v3-turbo": "/path/to/models/ggml-large-v3-turbo.bin",

"large-v3-q5_0": "/path/to/models/ggml-large-v3-q5_0.bin"

}

},

"paths": {

"work_dir": "data/tmp",

"settings_file": "data/settings.json"

}

}

```

| Key | Description |
|---|---|
| `telegram.bot_token` | Bot token from @BotFather |
| `access.allowed_user_ids` | Telegram user IDs allowed to use the bot |
| `whisper.cli_path` | Path to the built `whisper-cli` binary |
| `whisper.models` | Any number of models: `"menu label": "/path/to/model.bin"` — all appear in `/settings` |
| `whisper.threads` | `-t` passed to whisper-cli |
| `whisper.timeout_seconds` | Kill a stuck transcription after this long |
| `paths.work_dir` | Temp dir for downloaded/converted audio (auto-cleaned per job) |
| `paths.settings_file` | Where per-user preferences are stored |

Paths and model files are **validated at startup** — a bad path fails loudly
immediately, not mid-job.

## 💬 Usage

| Command / action | Result |
|---|---|
| `/start` | Short intro |
| `/settings` | Inline menu: language (🇮🇷 fa / 🇬🇧 en / 🌐 auto) + model |
| Send voice / audio / audio file | Queued and transcribed; result streams into the reply |

Notes:

- Transcriptions longer than 4,096 characters continue in follow-up messages
  (Telegram's message limit). No `.txt` files are ever sent.
- The standard Bot API won't let bots download files **larger than 20 MB**;
  the bot tells you when a file exceeds this. (Workaround: self-host
  [telegram-bot-api](https://github.com/tdlib/telegram-bot-api).)

## 🖥 Running as a service (systemd)

```

# adjust User= and paths in the unit file first

sudo cp deploy/whisper-bot.service /etc/systemd/system/

sudo systemctl daemon-reload

sudo systemctl enable --now whisper-bot

journalctl -u whisper-bot -f     # follow logs

```

The bot restarts automatically on failure.

## 📦 Deploying to another machine

The code is fully portable — everything machine-specific is in `config.json`:

```

rsync -av --exclude .venv --exclude config.json ./ newserver:~/apps/whisper.cpp-telegram-bot/

ssh newserver

cd ~/apps/whisper.cpp-telegram-bot

bash deploy/setup.sh

nano config.json               # paths for that machine

sudo cp deploy/whisper-bot.service /etc/systemd/system/

sudo systemctl enable --now whisper-bot

```

## 🔧 Troubleshooting

| Symptom | Fix |
|---|---|
| `config.json not found` | `cp config.example.json config.json` and fill it in |
| `whisper-cli not found` / `Model not found` | Fix the paths in `config.json` |
| `ffmpeg could not decode this file` | Install ffmpeg: `sudo apt install ffmpeg` |
| Bot never replies | Your user ID isn't in `allowed_user_ids` |
| "File is over 20 MB" | Bot API download limit — split/compress, or self-host the Bot API server |
| Slow transcription | Use the `q5_0` quantized model in `/settings`, or raise `threads` |

Logs: `journalctl -u whisper-bot -f` (service) or stdout (manual run).

## 🔐 Privacy

- Audio files are stored only temporarily in `work_dir` and **deleted after
  every job** (success or failure).
- Transcription happens entirely on your hardware. The only external calls
  are to Telegram's Bot API for messages.

## 🤝 Contributing

Issues and PRs are welcome. For larger changes, please open an issue first to
discuss the approach. Keep the code dependency-light — the only runtime
dependency is `python-telegram-bot`.

## 📄 License

This project is licensed under the **GNU General Public License v3.0** —
see [LICENSE](LICENSE) for details.

Whisper models and [whisper.cpp](https://github.com/ggml-org/whisper.cpp) are
licensed under their own terms (MIT).