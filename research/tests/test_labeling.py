import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import numpy as np
import pytest
import soundfile as sf

from clay_research.datasets import owner_takes
from clay_research.datasets.common import Note, PitchTrack, midi_to_hz
from clay_research.labeling import server, store
from clay_research.labeling.guess import guess_notes

HOP = 0.01


def track_from_midi(midi_frames):
    midi = np.asarray(midi_frames, dtype=float)
    hz = np.where(np.isnan(midi), 0.0, midi_to_hz(np.nan_to_num(midi)))
    return PitchTrack(times=np.arange(len(midi)) * HOP, frequencies_hz=hz)


def test_guess_splits_on_silence_and_pitch_jumps():
    gap = [np.nan] * 10
    frames = [60.1] * 30 + [62.0] * 30 + gap + [64.0] * 20 + [np.nan] * 3 + [70.0] * 3
    notes = guess_notes(track_from_midi(frames))
    assert [n.midi for n in notes] == [60, 62, 64]  # the 30 ms blip at 70 is dropped
    assert notes[0].onset == pytest.approx(0.0)
    assert notes[1].onset == pytest.approx(0.30, abs=HOP)
    assert notes[2].onset == pytest.approx(0.70, abs=HOP)
    assert notes[2].offset == pytest.approx(0.90, abs=HOP)


def test_guess_ignores_vibrato():
    t = np.arange(100) * HOP
    frames = 67 + 0.4 * np.sin(2 * np.pi * 5.5 * t)  # ±40 cents vibrato stays one note
    assert [n.midi for n in guess_notes(track_from_midi(frames))] == [67]


def test_labels_roundtrip_sorted(tmp_path):
    notes = [Note(1.0, 1.5, 64), Note(0.2, 0.8, 62.5)]
    store.save_labels("verse", notes, verified=True, labels_dir=tmp_path)
    loaded, verified = store.load_labels("verse", tmp_path)
    assert verified
    assert loaded == [Note(0.2, 0.8, 62.5), Note(1.0, 1.5, 64.0)]


@pytest.mark.parametrize("bad", [Note(0.5, 0.4, 60), Note(-0.1, 0.4, 60), Note(0.0, 0.4, 200)])
def test_save_rejects_bad_notes(tmp_path, bad):
    with pytest.raises(ValueError):
        store.save_labels("x", [bad], verified=False, labels_dir=tmp_path)


@pytest.mark.parametrize("name", ["../secret", "a/b", "..", "x\\y"])
def test_take_names_cannot_escape(name):
    with pytest.raises(ValueError):
        store.check_name(name)


@pytest.fixture
def takes(tmp_path, monkeypatch):
    """A data dir with one take (a 1 s A3 tone) and an empty labels dir."""
    audio_dir = tmp_path / "owner_takes"
    audio_dir.mkdir()
    sr = 16000
    t = np.arange(sr) / sr
    sf.write(audio_dir / "verse.wav", 0.3 * np.sin(2 * np.pi * 220 * t), sr)
    monkeypatch.setenv("CLAY_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(store, "LABELS_DIR", tmp_path / "labels")
    return tmp_path


@pytest.fixture
def base_url(takes):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def get(url):
    with urllib.request.urlopen(url) as r:
        return r.status, r.read()


def post(url, payload):
    req = urllib.request.Request(
        url,
        json.dumps(payload).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        return r.status, json.loads(r.read())


def test_server_lists_guesses_and_saves(base_url, takes):
    status, body = get(f"{base_url}/")
    assert status == 200 and b"Clay Note Labeler" in body

    assert json.loads(get(f"{base_url}/api/takes")[1]) == [{"take": "verse", "status": "none"}]

    take = json.loads(get(f"{base_url}/api/take/verse")[1])
    assert take["source"] == "guess"
    assert take["duration"] == pytest.approx(1.0)
    assert [round(n["midi"]) for n in take["notes"]] == [57]  # A3

    status, saved = post(
        f"{base_url}/api/take/verse/notes",
        {"notes": [{"onset": 0.0, "offset": 0.9, "midi": 57}], "verified": True},
    )
    assert status == 200 and saved["notes"] == 1
    assert json.loads(get(f"{base_url}/api/takes")[1])[0]["status"] == "verified"
    assert json.loads(get(f"{base_url}/api/take/verse")[1])["source"] == "saved"

    assert get(f"{base_url}/audio/verse.wav")[1][:4] == b"RIFF"


@pytest.mark.parametrize(
    ("path", "code"),
    [
        ("/audio/..%2F..%2Fsecret.wav", 400),
        ("/api/take/..%2Fx", 400),
        ("/api/take/missing", 404),
        ("/audio/missing.wav", 404),
    ],
)
def test_server_rejects_bad_paths(base_url, path, code):
    with pytest.raises(urllib.error.HTTPError) as err:
        get(base_url + path)
    assert err.value.code == code


def test_server_rejects_invalid_notes(base_url):
    with pytest.raises(urllib.error.HTTPError) as err:
        post(
            f"{base_url}/api/take/verse/notes",
            {"notes": [{"onset": 1.0, "offset": 0.5, "midi": 60}]},
        )
    assert err.value.code == 400


def test_owner_takes_only_returns_verified(takes):
    assert owner_takes.clip_ids() == []
    store.save_labels("verse", [Note(0.0, 0.9, 57)], verified=False)
    assert owner_takes.clip_ids() == []
    store.save_labels("verse", [Note(0.0, 0.9, 57)], verified=True)
    assert owner_takes.clip_ids() == ["verse"]
    clip = owner_takes.load("verse")
    assert clip.notes == (Note(0.0, 0.9, 57.0),)
    assert clip.sample_rate == 16000
