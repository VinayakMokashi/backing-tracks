"""Offline smoke test: C-Am-F-G -> MIDI -> WAV. No network, no server.

Isolates audio-toolchain failures from scraping failures.
Run:  .venv\\Scripts\\python.exe scripts\\smoke_render.py
"""
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402

config.ensure_dirs()

import numpy as np  # noqa: E402  (installed with pretty_midi)

from backtrack.arrange import arrange  # noqa: E402
from backtrack.model import ChordEvent, RenderOptions, Section, Song, options_hash  # noqa: E402
from backtrack.render import render  # noqa: E402


def main() -> int:
    song = Song(
        id="_smoke",
        title="Smoke Test",
        sections=[
            Section(
                name="Loop",
                chords=[
                    ChordEvent("C", 0.0, 4.0),
                    ChordEvent("Am", 4.0, 4.0),
                    ChordEvent("F", 8.0, 4.0),
                    ChordEvent("G", 12.0, 4.0),
                ],
                bars=4,
                repeat=2,
            )
        ],
        bpm=96.0,
    )
    opts = RenderOptions()
    result = render(arrange(song, opts), song.id, options_hash(song, opts))

    with wave.open(str(result.wav_path)) as w:
        frames = w.readframes(w.getnframes())
        duration = w.getnframes() / w.getframerate()
    peak = int(np.abs(np.frombuffer(frames, dtype=np.int16)).max())

    print(f"MIDI: {result.midi_path}")
    print(f"WAV:  {result.wav_path}  ({duration:.1f}s, peak {peak}/32767)")
    if result.mp3_path:
        print(f"MP3:  {result.mp3_path}")
    print(f"Rendered in {result.seconds}s")

    if peak < 1000:
        print("FAIL: output is (near-)silent — check the SoundFont path.")
        return 1
    if peak >= 32767:
        print("WARN: output clipped — lower GAIN in config.py.")
    print("Smoke render OK — play the WAV to confirm it sounds right.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
