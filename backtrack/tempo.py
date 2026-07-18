"""BPM resolution chain: UG strummings -> GetSongBPM (best-effort) -> style default.

BPM is always quarter-note BPM. GetSongBPM is optional and never blocks: it is
skipped unless an API key is configured, and any failure falls through silently.
"""
from __future__ import annotations

import requests

import config

STYLE_DEFAULT_BPM = {
    "pop": 100.0,
    "folk": 104.0,
    "ballad": 72.0,
    "muted_pop": 100.0,
    "waltz": 90.0,
    "six_eight": 90.0,
}


def style_default(style: str) -> float:
    return STYLE_DEFAULT_BPM.get(style, 100.0)


def _getsongbpm_lookup(title: str, artist: str) -> float | None:
    if not config.GETSONGBPM_API_KEY or not title:
        return None
    lookup = f"song:{title}"
    if artist:
        lookup += f" artist:{artist}"
    try:
        resp = requests.get(
            "https://api.getsong.co/search/",
            params={"api_key": config.GETSONGBPM_API_KEY, "type": "both",
                    "lookup": lookup},
            headers={"User-Agent": config.USER_AGENT},
            timeout=config.GETSONGBPM_TIMEOUT_S,
        )
        results = resp.json().get("search")
        if isinstance(results, list) and results:
            tempo = results[0].get("tempo")
            if tempo:
                return float(tempo)
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return None
    return None


def resolve_bpm(ug_bpm: float | None, style: str,
                title: str = "", artist: str = "") -> float:
    """Pick a tempo: explicit UG value wins, then GetSongBPM, then style default."""
    if ug_bpm:
        return float(ug_bpm)
    looked_up = _getsongbpm_lookup(title, artist)
    if looked_up:
        return looked_up
    return style_default(style)
