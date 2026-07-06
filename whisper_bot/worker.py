"""Single-worker FIFO queue: exactly one transcription at a time."""
from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass
from itertools import count
from pathlib import Path

from telegram import Message
from telegram.error import BadRequest, RetryAfter, TelegramError

from .config import Config
from .transcriber import TranscriptionError, stream_segments, to_wav

log = logging.getLogger(__name__)

TG_MESSAGE_LIMIT = 4096
EDIT_INTERVAL = 2.5  # seconds between streaming edits (stays under rate limits)

@dataclass
class Job:
    id: int
    audio_path: Path
    language: str
    model_key: str
    model_path: str
    status_message: Message

class TranscriptionWorker:
    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg
        self._queue: asyncio.Queue[Job] = asyncio.Queue()
        self._pending: list[Job] = []
        self._current: Job | None = None
        self._ids = count(1)
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="transcription-worker")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    def enqueue(
        self,
        *,
        audio_path: Path,
        language: str,
        model_key: str,
        model_path: str,
        status_message: Message,
    ) -> tuple[Job, int]:
        """Returns (job, position). Position 1 means it starts immediately."""
        job = Job(
            id=next(self._ids),
            audio_path=audio_path,
            language=language,
            model_key=model_key,
            model_path=model_path,
            status_message=status_message,
        )
        self._pending.append(job)
        self._queue.put_nowait(job)
        position = len(self._pending) + (1 if self._current else 0)
        return job, position

    # -- internals ---------------------------------------------------------

    async def _run(self) -> None:
        while True:
            job = await self._queue.get()
            self._pending.remove(job)
            self._current = job
            await self._refresh_queue_positions()
            try:
                await self._process(job)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Job %s crashed", job.id)
                await self._safe_edit(
                    job.status_message,
                    "❌ Unexpected internal error. Check the server logs.",
                )
            finally:
                self._current = None
                self._queue.task_done()

    async def _process(self, job: Job) -> None:
        msg = job.status_message
        await self._safe_edit(
            msg, f"🎙 Transcribing… (model: {job.model_key} · language: {job.language})"
        )
        wav: Path | None = None
        try:
            try:
                wav = await to_wav(self._cfg.whisper, job.audio_path)
            except TranscriptionError as e:
                await self._safe_edit(msg, f"❌ Could not read this audio.\n{e}")
                return

            text = ""
            last_edit = 0.0
            try:
                async for segment in stream_segments(
                    self._cfg.whisper, wav, job.model_path, job.language
                ):
                    text = f"{text} {segment}".strip()
                    now = asyncio.get_running_loop().time()
                    if now - last_edit >= EDIT_INTERVAL:
                        last_edit = now
                        await self._safe_edit(msg, self._clip(text) + " ▌")
            except TranscriptionError as e:
                await self._safe_edit(msg, f"❌ Transcription failed.\n{e}")
                return

            if not text:
                await self._safe_edit(msg, "🤷 I couldn't detect any speech in that audio.")
                return
            await self._send_final(msg, text)
        finally:
            job.audio_path.unlink(missing_ok=True)
            if wav is not None:
                wav.unlink(missing_ok=True)

    async def _send_final(self, msg: Message, text: str) -> None:
        chunks = [
            text[i : i + TG_MESSAGE_LIMIT]
            for i in range(0, len(text), TG_MESSAGE_LIMIT)
        ]
        await self._safe_edit(msg, chunks[0])
        for chunk in chunks[1:]:
            await msg.chat.send_message(chunk)

    async def _refresh_queue_positions(self) -> None:
        for position, job in enumerate(self._pending, start=2):
            await self._safe_edit(
                job.status_message,
                f"⏳ In queue — position {position}. One job runs at a time.",
            )

    @staticmethod
    def _clip(text: str, limit: int = TG_MESSAGE_LIMIT - 100) -> str:
        return text if len(text) <= limit else "…" + text[-limit:]

    async def _safe_edit(self, msg: Message, text: str) -> None:
        try:
            await msg.edit_text(text)
        except RetryAfter as e:
            await asyncio.sleep(e.retry_after + 0.5)
            with contextlib.suppress(TelegramError):
                await msg.edit_text(text)
        except BadRequest as e:
            if "not modified" not in str(e).lower():
                log.warning("Edit failed: %s", e)
        except TelegramError as e:
            log.warning("Edit failed: %s", e)