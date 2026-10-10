import json

import numpy as np
import pytest
import soundfile as sf

from clay_research.datasets import vocadito
from clay_research.datasets.common import data_root
from clay_research.harness import score
from clay_research.harness.metrics import note_scores


def make_track(root, clip_id="7", midi=57.0, seconds=1.0, sr=44100):
    """Fake vocadito track: a steady tone for the first 0.6 s, labelled identically by A1/A2."""
    for sub in ("Audio", "Annotations/F0", "Annotations/Notes"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    hz = 440 * 2 ** ((midi - 69) / 12)
    t = np.arange(int(sr * seconds)) / sr
    audio = np.where(t < 0.6, 0.3 * np.sin(2 * np.pi * hz * t), 0.0)
    sf.write(root / "Audio" / f"vocadito_{clip_id}.wav", audio, sr)
    times = np.arange(0, seconds, 0.01)
    np.savetxt(
        root / "Annotations" / "F0" / f"vocadito_{clip_id}_f0.csv",
        np.column_stack([times, np.where(times < 0.6, hz, 0.0)]),
        delimiter=",",
    )
    for a in vocadito.ANNOTATORS:
        np.savetxt(
            root / "Annotations" / "Notes" / f"vocadito_{clip_id}_notes{a}.csv",
            [[0.0, hz, 0.6]],
            delimiter=",",
        )


def test_loader_reads_audio_f0_and_both_annotators(tmp_path):
    make_track(tmp_path, "7")
    make_track(tmp_path, "12")
    assert vocadito.clip_ids(tmp_path) == ["7", "12"]  # numeric order
    clip = vocadito.load("7", tmp_path)
    assert clip.sample_rate == 44100 and clip.audio.ndim == 1
    assert clip.notes[0].midi == pytest.approx(57.0)
    assert clip.notes[0].offset == pytest.approx(0.6)
    assert vocadito.load_notes("7", "A2", tmp_path)[0].onset == 0.0
    assert clip.pitch.voiced.sum() == 60
    with pytest.raises(ValueError):
        vocadito.load_notes("7", "A3", tmp_path)


def test_harness_scores_notes_against_each_annotator(tmp_path, monkeypatch):
    make_track(tmp_path / "vocadito", "1")
    monkeypatch.setenv("CLAY_DATA_DIR", str(tmp_path))
    out = tmp_path / "reports"
    assert score.main(["--dataset", "vocadito", "--jobs", "1", "--out", str(out)]) == 0
    summary = json.loads((out / "vocadito_pyin.json").read_text())["summary"]
    assert summary["note_f1_a1"] == 1.0  # one clean tone: the guesser finds the one note
    assert summary["note_f1_mean"] == 1.0
    assert "raw_pitch_accuracy" in summary


@pytest.mark.skipif(
    not (data_root() / "vocadito" / ".complete").exists(), reason="vocadito not downloaded"
)
def test_real_human_agreement_matches_the_gate_constant():
    ids = vocadito.clip_ids()
    assert len(ids) == 40
    f1 = np.mean(
        [note_scores(vocadito.load_notes(i, "A1"), vocadito.load_notes(i, "A2")).f1 for i in ids]
    )
    assert f1 == pytest.approx(vocadito.HUMAN_AGREEMENT_F1, abs=0.0005)
