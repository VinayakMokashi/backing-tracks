"""All disk persistence: fetch cache, song JSONs, and outbound-fetch throttle.

Render-output pruning lands in M6.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path

import config

from .model import Song, song_from_dict, song_to_dict


def _atomic_write(path: Path, text: str) -> None:
    """Write via temp file + os.replace so readers never see a torn file."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)

_fetch_lock = threading.Lock()
_last_fetch = 0.0


def throttle() -> None:
    """Global politeness limit: at most one outbound fetch per second."""
    global _last_fetch
    with _fetch_lock:
        wait = config.FETCH_MIN_INTERVAL_S - (time.monotonic() - _last_fetch)
        if wait > 0:
            time.sleep(wait)
        _last_fetch = time.monotonic()


def _cache_path(url: str):
    return config.CACHE_DIR / (hashlib.sha1(url.encode("utf-8")).hexdigest() + ".json")


def cache_get(url: str) -> dict | None:
    p = _cache_path(url)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        p.unlink(missing_ok=True)  # corrupt entry -> cache miss; refetch overwrites
        return None


def cache_put(url: str, payload: dict) -> None:
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _atomic_write(_cache_path(url), json.dumps(payload, ensure_ascii=False))


def save_song(song: Song) -> None:
    config.SONGS_DIR.mkdir(parents=True, exist_ok=True)
    path = config.SONGS_DIR / f"{song.id}.json"
    _atomic_write(path, json.dumps(song_to_dict(song), ensure_ascii=False, indent=2))


def load_song(song_id: str) -> Song | None:
    path = config.SONGS_DIR / f"{song_id}.json"
    if not path.exists():
        return None
    try:
        return song_from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, KeyError, OSError):
        return None


def list_songs() -> list[dict]:
    out = []
    for path in sorted(config.SONGS_DIR.glob("*.json")):
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
            out.append(
                {"id": d["id"], "title": d["title"], "artist": d.get("artist", ""),
                 "key": d.get("key", "C")}
            )
        except (json.JSONDecodeError, KeyError, OSError):
            continue  # one bad file must not take down the whole library
    return out
