import numpy as np
import pytest
from test_note_model_and_render import SR, pitch_change, sung

from clay_research.harness.trackers import fcpe
from clay_research.render import stretchers


def first_onset(y):
    t = fcpe(y, SR)
    return float(t.times[np.argmax(t.frequencies_hz > 0)])


def last_offset(y):
    t = fcpe(y, SR)
    voiced = np.nonzero(t.frequencies_hz > 0)[0]
    return float(t.times[voiced[-1]])


@pytest.mark.parametrize("method", ["rubberband", "signalsmith", "world"])
@pytest.mark.parametrize("ratio", [0.9, 1.1])
def test_stretch_changes_length_not_pitch(method, ratio):
    pad = np.zeros(int(0.3 * SR), np.float32)
    x = np.concatenate([pad, sung([57, 60, 64], vibrato=0.2)])
    y = getattr(stretchers, method)(x, SR, ratio)
    assert len(y) == stretchers.out_length(len(x), ratio)
    # Timing scales with the ratio: the last sung moment lands at ratio x its old time.
    assert last_offset(y) == pytest.approx(ratio * last_offset(x), abs=0.03)
    assert first_onset(y) == pytest.approx(ratio * first_onset(x), abs=0.03)
    # Pitch unchanged: compare the middle of the first note.
    a = x[int(0.4 * SR) : int(0.7 * SR)]
    b = y[int(0.4 * ratio * SR) : int(0.7 * ratio * SR)]
    assert pitch_change(a, b) == pytest.approx(0.0, abs=0.1)


@pytest.mark.parametrize("method", ["rubberband", "signalsmith"])
def test_stretch_handles_long_audio(method):
    x = np.tile(sung([60, 62]), 25)  # longer than Rubber Band's per-call limit
    y = getattr(stretchers, method)(x, SR, 1.1)
    tail = slice(len(y) - SR * 5, len(y))
    assert np.sqrt(np.mean(y[tail] ** 2)) > 0.5 * np.sqrt(np.mean(x[-SR * 5 :] ** 2))
