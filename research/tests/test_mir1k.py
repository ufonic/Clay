import numpy as np
import pytest
import soundfile as sf

from clay_research.datasets import mir1k
from clay_research.datasets.common import data_root, midi_to_hz


def make_clip(root, clip_id="Ani_1_01", seconds=1.0, voiced_midi=57.0):
    """Fake MIR-1K clip: accompaniment noise left, A3 tone right, labels for the first half."""
    (root / "Wavfile").mkdir(parents=True, exist_ok=True)
    (root / "PitchLabel").mkdir(parents=True, exist_ok=True)
    sr = mir1k.SAMPLE_RATE
    n = int(sr * seconds)
    t = np.arange(n) / sr
    voice = 0.2 * np.sin(2 * np.pi * float(midi_to_hz(np.array(voiced_midi))) * t)
    accomp = 0.05 * np.random.default_rng(0).standard_normal(n)
    sf.write(root / "Wavfile" / f"{clip_id}.wav", np.stack([accomp, voice], axis=1), sr)
    n_frames = (n - mir1k.FRAME_LENGTH) // mir1k.HOP_LENGTH + 1
    labels = np.zeros(n_frames)
    labels[: n_frames // 2] = voiced_midi
    np.savetxt(root / "PitchLabel" / f"{clip_id}.pv", labels, fmt="%g")
    return n, n_frames


def test_frame_times_are_centres_on_20ms_hop():
    np.testing.assert_allclose(mir1k.frame_times(3), [0.02, 0.04, 0.06])


def test_load_voice_channel_and_pitch(tmp_path):
    n, n_frames = make_clip(tmp_path)

    clip = mir1k.load("Ani_1_01", tmp_path)

    assert clip.sample_rate == 16000
    assert clip.audio.shape == (n,)
    assert clip.audio.dtype == np.float32
    assert clip.metadata == {"singer": "Ani", "channel": "voice"}
    # the right channel is the clean tone, so its peak is ~0.2
    assert 0.19 < np.abs(clip.audio).max() < 0.21
    assert len(clip.pitch.times) == n_frames
    assert clip.pitch.voiced.sum() == n_frames // 2
    np.testing.assert_allclose(clip.pitch.frequencies_hz[0], 220.0, rtol=1e-6)


def test_channels(tmp_path):
    make_clip(tmp_path)
    accomp = mir1k.load("Ani_1_01", tmp_path, channel="accompaniment").audio
    voice = mir1k.load("Ani_1_01", tmp_path, channel="voice").audio
    mix = mir1k.load("Ani_1_01", tmp_path, channel="mix").audio
    np.testing.assert_allclose(mix, (accomp + voice) / 2, atol=1e-4)


def test_clip_ids(tmp_path):
    make_clip(tmp_path, "Ani_1_02")
    make_clip(tmp_path, "Ani_1_01")
    assert mir1k.clip_ids(tmp_path) == ["Ani_1_01", "Ani_1_02"]


@pytest.mark.skipif(
    not (data_root() / "mir1k" / ".complete").exists(), reason="MIR-1K not downloaded"
)
def test_real_dataset_framing_matches_audio_length():
    ids = mir1k.clip_ids()
    assert len(ids) == 1000
    for cid in ids[::100]:
        clip = mir1k.load(cid)
        expected = (len(clip.audio) - mir1k.FRAME_LENGTH) // mir1k.HOP_LENGTH + 1
        assert len(clip.pitch.times) == expected
