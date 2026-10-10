"""The HMM segmenter on hand-built pitch tracks with known answers."""

import numpy as np
import pytest

from clay_research.analysis.notes import SegmenterParams, _transitions, segment
from clay_research.datasets.common import PitchTrack, midi_to_hz

HOP = 0.01


def track(midi_frames):
    m = np.asarray(midi_frames, dtype=float)
    hz = np.where(np.isnan(m), 0.0, midi_to_hz(np.nan_to_num(m)))
    return PitchTrack(times=np.arange(len(m)) * HOP, frequencies_hz=hz)


def rest(n):
    return [np.nan] * n


def test_transition_rows_are_probabilities():
    t = _transitions(49, SegmenterParams())
    np.testing.assert_allclose(t.sum(axis=1), 1.0)
    assert (t >= 0).all()


def test_silence_gives_no_notes():
    assert segment(track(rest(200))) == []


def test_two_notes_separated_by_a_pitch_change():
    notes = segment(track(rest(20) + [60.0] * 50 + [64.0] * 50 + rest(20)))
    assert [round(n.midi) for n in notes] == [60, 64]
    assert notes[0].onset == pytest.approx(0.20, abs=0.03)
    assert notes[1].onset == pytest.approx(0.70, abs=0.05)
    assert notes[1].offset == pytest.approx(1.20, abs=0.03)


def test_vibrato_stays_one_note_with_center_pitch():
    t = np.arange(150) * HOP
    sung = list(62 + 0.5 * np.sin(2 * np.pi * 5.5 * t))  # ±50 cents vibrato
    notes = segment(track(rest(10) + sung + rest(10)))
    assert len(notes) == 1
    assert notes[0].midi == pytest.approx(62.0, abs=0.15)


def test_scoop_into_note_is_not_its_own_note_and_doesnt_drag_the_pitch():
    scoop = list(np.linspace(58.0, 62.0, 8))  # 80 ms slide up into D4
    notes = segment(track(rest(10) + scoop + [62.0] * 60 + rest(10)))
    assert len(notes) == 1
    assert notes[0].midi == pytest.approx(62.0, abs=0.1)


def test_short_blip_is_not_a_note():
    notes = segment(track(rest(50) + [70.0] * 3 + rest(50) + [60.0] * 40 + rest(10)))
    assert [round(n.midi) for n in notes] == [60]


def test_brief_dropout_inside_a_note_does_not_split_it():
    notes = segment(track(rest(10) + [65.0] * 40 + rest(2) + [65.0] * 40 + rest(10)))
    assert len(notes) == 1
