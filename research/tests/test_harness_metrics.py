"""Known-answer tests for the scoring metrics."""

import numpy as np
import pytest

from clay_research.datasets.common import Note, PitchTrack
from clay_research.harness import metrics


def track(freqs, hop=0.01):
    freqs = np.asarray(freqs, dtype=float)
    return PitchTrack(times=np.arange(len(freqs)) * hop, frequencies_hz=freqs)


def cents_up(hz, cents):
    return hz * 2 ** (cents / 1200)


def test_perfect_track_scores_perfectly():
    ref = track([0, 0, 220, 220, 220, 220, 0, 0])
    s = metrics.frame_scores(ref, ref)
    assert s.raw_pitch_accuracy == 1.0
    assert s.voicing_recall == 1.0
    assert s.voicing_false_alarm == 0.0
    assert s.cents_error_median == pytest.approx(0.0, abs=1e-6)


def test_raw_pitch_accuracy_uses_50_cent_tolerance():
    ref = track([220.0] * 4)
    # two frames 30 cents off (inside), two frames 70 cents off (outside)
    est = track([cents_up(220, 30)] * 2 + [cents_up(220, 70)] * 2)
    s = metrics.frame_scores(ref, est)
    assert s.raw_pitch_accuracy == pytest.approx(0.5)
    assert s.cents_error_median == pytest.approx(50.0, abs=0.5)  # median of 30,30,70,70


def test_voicing_errors():
    ref = track([0, 0, 220, 220])
    est = track([220, 0, 0, 220])  # one false alarm, one miss
    s = metrics.frame_scores(ref, est)
    assert s.voicing_recall == pytest.approx(0.5)
    assert s.voicing_false_alarm == pytest.approx(0.5)


def test_no_shared_voiced_frames_gives_nan_cents():
    s = metrics.frame_scores(track([220, 220]), track([0, 0]))
    assert np.isnan(s.cents_error_median)
    assert s.raw_pitch_accuracy == 0.0


def test_note_f1_onset_tolerance_and_offsets():
    ref = [Note(0.0, 0.5, 60), Note(0.5, 1.0, 62)]
    # first note onset 40 ms late (inside 50 ms), offset far off; second 60 ms late (outside)
    est = [Note(0.04, 0.9, 60), Note(0.56, 1.0, 62)]
    s = metrics.note_scores(ref, est)
    assert s.f1 == pytest.approx(0.5)
    assert s.precision == pytest.approx(0.5)
    assert s.f1_with_offsets == pytest.approx(0.0)


def test_note_pitch_tolerance():
    ref = [Note(0.0, 0.5, 60.0)]
    assert metrics.note_scores(ref, [Note(0.0, 0.5, 60.4)]).f1 == 1.0  # 40 cents
    assert metrics.note_scores(ref, [Note(0.0, 0.5, 60.6)]).f1 == 0.0  # 60 cents


def test_note_scores_handle_empty_estimates():
    assert metrics.note_scores([Note(0.0, 0.5, 60)], []).f1 == 0.0


@pytest.mark.parametrize(
    ("ref", "est", "strict", "acc1", "acc2"),
    [
        (120.0, 120.9, True, True, True),
        (120.0, 121.5, False, True, True),
        (120.0, 60.0, False, False, True),  # half tempo
        (120.0, 100.0, False, False, False),
    ],
)
def test_tempo(ref, est, strict, acc1, acc2):
    assert metrics.tempo_correct(ref, est) is strict
    assert metrics.tempo_accuracy1(ref, est) is acc1
    assert metrics.tempo_accuracy2(ref, est) is acc2


def test_key_scores():
    assert metrics.key_exact("C# minor", "Db minor")  # enharmonic
    assert not metrics.key_exact("C major", "A minor")
    assert metrics.key_weighted("C major", "G major") == pytest.approx(0.5)  # fifth
    assert metrics.key_weighted("C major", "A minor") == pytest.approx(0.3)  # relative
