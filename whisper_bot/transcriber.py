"""Runs ffmpeg + whisper-cli as subprocesses and streams segments out."""
from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import AsyncIterator

from .config import WhisperConfig

# whisper-cli stdout lines look like: [00:00:00.000 --> 00:00:04.500]   text
_TS = re.compile(r"^\[\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}\]\s*")

class TranscriptionError(Exception):
    """User-presentable transcription failure."""

async def to_wav(cfg: WhisperConfig, src: Path) -> Path:
    """whisper.cpp wants 16 kHz mono WAV; Telegram sends ogg/opus, mp3, m4a..."""
    dst = src.with_suffix(".wav")
    proc = await asyncio.create_subprocess_exec(
        cfg.ffmpeg_path, "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src), "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(dst),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, err = await asyncio.wait_for(proc.communicate(), timeout=300)
    except asyncio.TimeoutError:
        proc.kill()
        raise TranscriptionError("Audio conversion timed out.")
    if proc.returncode != 0:
        raise TranscriptionError(
            f"ffmpeg could not decode this file:\n{err.decode(errors='replace')[-400:]}"
        )
    return dst

async def stream_segments(
    cfg: WhisperConfig, wav: Path, model_path: str, language: str
) -> AsyncIterator[str]:
    """Yield transcription segments as whisper-cli emits them (real-time)."""
    proc = await asyncio.create_subprocess_exec(
        cfg.cli_path,
        "-m", model_path,
        "-l", language,
        "-t", str(cfg.threads),
        "-f", str(wav),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    assert proc.stdout is not None and proc.stderr is not None
    stderr_task = asyncio.create_task(proc.stderr.read())
    try:
        while True:
            try:
                raw = await asyncio.wait_for(
                    proc.stdout.readline(), timeout=cfg.timeout_seconds
                )
            except asyncio.TimeoutError:
                raise TranscriptionError("Transcription timed out.")
            if not raw:
                break
            line = raw.decode(errors="replace").strip()
            match = _TS.match(line)
            if match and line[match.end():].strip():
                yield line[match.end():].strip()

        return_code = await proc.wait()
        if return_code != 0:
            stderr = (await stderr_task).decode(errors="replace")
            raise TranscriptionError(
                f"whisper-cli exited with code {return_code}:\n{stderr[-400:]}"
            )
    finally:
        if proc.returncode is None:
            proc.kill()
        if not stderr_task.done():
            stderr_task.cancel()