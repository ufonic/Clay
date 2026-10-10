"""Every tracker must find a known pitch, report silence as unvoiced, and get frame times
right (a timing offset would quietly ruin every note-onset score)."""

import numpy as np
import pytest

from clay_research.harness.trackers import TRACKERS


def tone(sr, hz=220.0, seconds=1.5, on=(0.5, 1.0)):
    """Silence, then a slightly vibrato-free harmonic tone from on[0] to on[1], then silence."""
    t = np.arange(int(sr * seconds)) / sr
    x = sum(0.3 / k * np.sin(2 * np.pi * hz * k * t) for k in (1, 2, 3))
    return np.where((t >= on[0]) & (t < on[1]), x, 0.0).astype(np.float32)


@pytest.mark.parametrize("name", sorted(TRACKERS))
@pytest.mark.parametrize("sr", [16000, 44100])
def test_tracker_finds_pitch_and_timing(name, sr):
    track = TRACKERS[name](tone(sr), sr)
    times, f0 = np.asarray(track.times), np.asarray(track.frequencies_hz)
    assert np.all(np.diff(times) > 0)

    middle = (times > 0.6) & (times < 0.9)
    assert np.mean(f0[middle] > 0) > 0.9, "tone should be voiced"
    cents = 1200 * np.log2(f0[middle & (f0 > 0)] / 220.0)
    assert np.median(np.abs(cents)) < 20

    silent = (times < 0.4) | (times > 1.1)
    assert np.mean(f0[silent] > 0) < 0.1, "silence should be unvoiced"

    voiced_times = times[f0 > 0]
    assert voiced_times.min() == pytest.approx(0.5, abs=0.04)
    assert voiced_times.max() == pytest.approx(1.0, abs=0.04)
