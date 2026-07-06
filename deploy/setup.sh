#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

command -v ffmpeg >/dev/null || { echo "Install ffmpeg first: sudo apt install ffmpeg"; exit 1; }

python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

[ -f config.json ] || { cp config.example.json config.json; echo "⚠️  Edit config.json before starting."; }
echo "✅ Done. Run with: .venv/bin/python -m whisper_bot"
