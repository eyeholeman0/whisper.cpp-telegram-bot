"""Typed access to config.json. No secrets live in code."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

class ConfigError(RuntimeError):
    pass

@dataclass(frozen=True)
class WhisperConfig:
    cli_path: str
    ffmpeg_path: str
    models: dict[str, str]  # model key -> path to .bin
    threads: int
    timeout_seconds: int

@dataclass(frozen=True)
class Config:
    bot_token: str
    allowed_user_ids: frozenset[int]
    whisper: WhisperConfig
    work_dir: Path
    settings_file: Path

def load_config(path: str | Path = "config.json") -> Config:
    p = Path(path)
    if not p.exists():
        raise ConfigError(
            f"{p} not found. Copy config.example.json to config.json and fill it in."
        )
    raw = json.loads(p.read_text(encoding="utf-8"))
    try:
        w = raw["whisper"]
        cfg = Config(
            bot_token=raw["telegram"]["bot_token"],
            allowed_user_ids=frozenset(raw["access"]["allowed_user_ids"]),
            whisper=WhisperConfig(
                cli_path=w["cli_path"],
                ffmpeg_path=w.get("ffmpeg_path", "ffmpeg"),
                models=dict(w["models"]),
                threads=int(w.get("threads", 4)),
                timeout_seconds=int(w.get("timeout_seconds", 1800)),
            ),
            work_dir=Path(raw["paths"]["work_dir"]),
            settings_file=Path(raw["paths"]["settings_file"]),
        )
    except (KeyError, TypeError) as e:
        raise ConfigError(f"Invalid or missing key in config.json: {e}") from e

    if not Path(cfg.whisper.cli_path).exists():
        raise ConfigError(f"whisper-cli not found at {cfg.whisper.cli_path}")
    for key, model_path in cfg.whisper.models.items():
        if not Path(model_path).exists():
            raise ConfigError(f"Model '{key}' not found at {model_path}")
    if not cfg.allowed_user_ids:
        raise ConfigError("allowed_user_ids must contain at least one Telegram user id")
    return cfg