"""Per-user preferences (language / model), persisted as JSON."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

LANGUAGES = ("fa", "en", "auto")

@dataclass
class UserSettings:
    language: str
    model: str

class SettingsStore:
    def __init__(self, file: Path, model_keys: list[str]) -> None:
        self._file = file
        self._model_keys = model_keys
        self._default_model = model_keys[0]
        self._data: dict[str, dict] = {}
        if file.exists():
            self._data = json.loads(file.read_text(encoding="utf-8"))

    def get(self, user_id: int) -> UserSettings:
        raw = self._data.get(str(user_id), {})
        settings = UserSettings(
            language=raw.get("language", "fa"),
            model=raw.get("model", self._default_model),
        )
        if settings.language not in LANGUAGES:
            settings.language = "fa"
        if settings.model not in self._model_keys:
            settings.model = self._default_model
        return settings

    def set(
        self,
        user_id: int,
        *,
        language: str | None = None,
        model: str | None = None,
    ) -> UserSettings:
        settings = self.get(user_id)
        if language is not None:
            settings.language = language
        if model is not None:
            settings.model = model
        self._data[str(user_id)] = asdict(settings)
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._file.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return settings