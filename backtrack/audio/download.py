"""Download a YouTube (or other) video's audio track to WAV via yt-dlp+ffmpeg."""
from __future__ import annotations

import os
from pathlib import Path

import config


class DownloadError(Exception):
    def __init__(self, message: str, hint: str = ""):
        super().__init__(message)
        self.message = message
        self.hint = hint


def _ffmpeg_dir() -> str | None:
    exe = config.FFMPEG_EXE
    if exe and (os.sep in exe or exe.lower().endswith(".exe")):
        return str(Path(exe).parent)
    return None  # on PATH


def download_audio(url: str, out_dir: Path, basename: str = "source") -> tuple[Path, str]:
    """Download best audio for `url` and extract it to <out_dir>/<basename>.wav.

    Returns (wav_path, video_title). Personal-use tool: the caller supplies the
    link; nothing is redistributed.
    """
    import yt_dlp

    out_dir.mkdir(parents=True, exist_ok=True)
    wav = out_dir / f"{basename}.wav"
    for stale in out_dir.glob(f"{basename}.*"):
        stale.unlink(missing_ok=True)

    opts = {
        "format": "bestaudio/best",
        "outtmpl": str(out_dir / f"{basename}.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "wav",
        }],
    }
    ff = _ffmpeg_dir()
    if ff:
        opts["ffmpeg_location"] = ff
    if config.COOKIES_FILE and Path(config.COOKIES_FILE).exists():
        opts["cookiefile"] = str(config.COOKIES_FILE)
    elif config.COOKIES_FROM_BROWSER:
        opts["cookiesfrombrowser"] = (config.COOKIES_FROM_BROWSER,)

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except Exception as exc:  # noqa: BLE001 — yt-dlp raises many types
        text = str(exc).lower()
        needs_login = any(w in text for w in
                          ("login", "log in", "private", "rate-limit", "rate limit",
                           "cookies", "empty media response", "restricted"))
        is_instagram = "instagram.com" in url.lower()
        if needs_login or is_instagram:
            hint = ("Instagram usually needs you logged in. Open config.py, set "
                    "COOKIES_FROM_BROWSER to the browser you're logged into "
                    "Instagram in (e.g. \"chrome\"), and try again.")
        else:
            hint = "Check the link is a valid, playable video URL."
        raise DownloadError(f"Could not download audio: {exc}", hint) from exc

    if not wav.exists():
        raise DownloadError("Audio extraction produced no WAV file.",
                            "The video audio may be unavailable in a usable format.")
    return wav, (info or {}).get("title", "")
