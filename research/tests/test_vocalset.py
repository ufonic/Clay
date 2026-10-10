import numpy as np
import pytest
import soundfile as sf

from clay_research.datasets import vocalset
from clay_research.datasets.common import data_root


def write_tone(path, sr=44100, seconds=0.1, channels=1):
    path.parent.mkdir(parents=True, exist_ok=True)
    t = np.arange(int(sr * seconds)) / sr
    tone = (0.1 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    sf.write(path, np.stack([tone] * channels, axis=1) if channels > 1 else tone, sr)


def test_clip_ids_and_labels(tmp_path):
    write_tone(tmp_path / "female1/scales/vibrato/f1_scales_vibrato_a.wav")
    write_tone(tmp_path / "male3/excerpts/spoken/m3_caro_spoken.wav")
    (tmp_path / "female1/scales/vibrato/._f1_scales_vibrato_a.wav").write_bytes(b"junk")

    ids = vocalset.clip_ids(tmp_path)

    assert ids == [
        "female1/scales/vibrato/f1_scales_vibrato_a",
        "male3/excerpts/spoken/m3_caro_spoken",
    ]
    assert vocalset.labels_from_id(ids[0]) == {
        "singer": "female1",
        "context": "scales",
        "technique": "vibrato",
        "vowel": "a",
    }
    assert "vowel" not in vocalset.labels_from_id(ids[1])


def test_load_returns_mono_float32(tmp_path):
    write_tone(tmp_path / "female2/long_tones/messa/f2_long_messa_e.wav", channels=2)

    clip = vocalset.load("female2/long_tones/messa/f2_long_messa_e", tmp_path)

    assert clip.dataset == "vocalset"
    assert clip.sample_rate == 44100
    assert clip.audio.dtype == np.float32
    assert clip.audio.ndim == 1
    assert abs(clip.duration - 0.1) < 1e-3
    assert clip.metadata["technique"] == "messa"
    assert clip.pitch is None


@pytest.mark.skipif(
    not (data_root() / "vocalset" / ".complete").exists(), reason="VocalSet not downloaded"
)
def test_real_dataset_has_all_clips():
    ids = vocalset.clip_ids()
    assert len(ids) == 3613  # unique clips in data_by_singer, VocalSet 1.2
    assert len({vocalset.labels_from_id(i)["singer"] for i in ids}) == 20
    clip = vocalset.load(ids[0])
    assert clip.sample_rate == 44100
    assert clip.duration > 0.5
