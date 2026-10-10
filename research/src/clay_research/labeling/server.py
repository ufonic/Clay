"""Local note labeler: a small web server plus a piano-roll page in your browser.

Usage (from the repo root):
    uv run --project research python -m clay_research.labeling.server
then open http://127.0.0.1:8765 (it opens automatically).

Put your takes in data/owner_takes/ as .wav files first. Labels are saved to
research/labels/owner/<take>.json. The server only listens on this computer.
"""

from __future__ import annotations

import argparse
import json
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

import numpy as np
import soundfile as sf

from clay_research.datasets.common import Note, PitchTrack
from clay_research.harness.trackers import pyin

from . import store
from .guess import guess_notes, hz_to_midi

STATIC = Path(__file__).parent / "static"
_pitch_lock = threading.Lock()


def load_mono(take: str) -> tuple[np.ndarray, int]:
    audio, sr = sf.read(
        store.audio_dir() / f"{store.check_name(take)}.wav", dtype="float32", always_2d=True
    )
    return audio.mean(axis=1), sr


def pitch_track(take: str) -> PitchTrack:
    """pYIN track for a take, cached next to the audio (pYIN takes a while on long takes)."""
    cache = store.audio_dir() / ".cache" / f"{store.check_name(take)}.pitch.npz"
    wav = store.audio_dir() / f"{take}.wav"
    with _pitch_lock:
        if cache.exists() and cache.stat().st_mtime >= wav.stat().st_mtime:
            data = np.load(cache)
            return PitchTrack(times=data["times"], frequencies_hz=data["hz"])
        audio, sr = load_mono(take)
        track = pyin(audio, sr)
        cache.parent.mkdir(parents=True, exist_ok=True)
        np.savez(cache, times=track.times, hz=track.frequencies_hz)
        return track


def take_payload(take: str) -> dict:
    wav = store.audio_dir() / f"{store.check_name(take)}.wav"
    if not wav.exists():
        raise FileNotFoundError(f"no take named {take!r} in {store.audio_dir()}")
    info = sf.info(wav)
    track = pitch_track(take)
    saved = store.load_labels(take)
    notes, verified, source = (
        (saved[0], saved[1], "saved") if saved else (guess_notes(track), False, "guess")
    )
    midi = hz_to_midi(track.frequencies_hz)
    return {
        "take": take,
        "duration": info.frames / info.samplerate,
        "pitch": {
            "times": [round(float(t), 4) for t in track.times],
            "midi": [None if not np.isfinite(m) else round(float(m), 3) for m in midi],
        },
        "notes": [{"onset": n.onset, "offset": n.offset, "midi": n.midi} for n in notes],
        "verified": verified,
        "source": source,
    }


def takes_payload() -> list[dict]:
    out = []
    for take in store.take_names():
        saved = store.load_labels(take)
        status = "none" if saved is None else ("verified" if saved[1] else "draft")
        out.append({"take": take, "status": status})
    return out


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # keep the console quiet
        pass

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, status: int = HTTPStatus.OK) -> None:
        self._send(status, json.dumps(obj).encode(), "application/json")

    def _error(self, status: int, message: str) -> None:
        self._json({"error": message}, status)

    def do_GET(self):  # noqa: N802 (http.server naming)
        path = unquote(urlparse(self.path).path)
        try:
            if path in ("/", "/index.html"):
                self._send(
                    HTTPStatus.OK, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8"
                )
            elif path == "/api/takes":
                self._json(takes_payload())
            elif path.startswith("/api/take/"):
                self._json(take_payload(path.removeprefix("/api/take/")))
            elif path.startswith("/audio/") and path.endswith(".wav"):
                take = store.check_name(path.removeprefix("/audio/").removesuffix(".wav"))
                self._send(
                    HTTPStatus.OK, (store.audio_dir() / f"{take}.wav").read_bytes(), "audio/wav"
                )
            else:
                self._error(HTTPStatus.NOT_FOUND, "not found")
        except FileNotFoundError as e:
            self._error(HTTPStatus.NOT_FOUND, str(e))
        except ValueError as e:
            self._error(HTTPStatus.BAD_REQUEST, str(e))

    def do_POST(self):  # noqa: N802
        path = unquote(urlparse(self.path).path)
        if not (path.startswith("/api/take/") and path.endswith("/notes")):
            return self._error(HTTPStatus.NOT_FOUND, "not found")
        try:
            take = store.check_name(path.removeprefix("/api/take/").removesuffix("/notes"))
            if not (store.audio_dir() / f"{take}.wav").exists():
                raise ValueError(f"no audio for take {take!r}")
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            notes = [
                Note(float(n["onset"]), float(n["offset"]), float(n["midi"])) for n in body["notes"]
            ]
            saved = store.save_labels(take, notes, bool(body.get("verified", False)))
            self._json({"saved": str(saved), "notes": len(notes)})
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
            self._error(HTTPStatus.BAD_REQUEST, str(e))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Label notes in the owner's takes.")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--no-browser", action="store_true")
    args = p.parse_args(argv)

    takes = store.take_names()
    print(f"Takes in {store.audio_dir()}: {len(takes)}")
    if not takes:
        print("  (none yet: copy your .wav takes there, then reload the page)")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}"
    print(f"Labeler running at {url}  (Ctrl+C to stop)")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
