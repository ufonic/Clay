import numpy as np
import pytest
from test_note_model_and_render import SR, pitch_change, sung

from clay_research.render import shifters


@pytest.mark.parametrize("method", ["rubberband", "psola", "signalsmith"])
@pytest.mark.parametrize("shift", [-2.0, 2.0])
def test_shifter_moves_pitch_and_keeps_timing(method, shift):
    x = sung([57, 60, 64], vibrato=0.3)
    y = getattr(shifters, method)(x, SR, shift)
    assert len(y) == len(x)
    assert pitch_change(x, y) == pytest.approx(shift, abs=0.1)
    assert abs(shifters.alignment_lag(x, y, SR)) < 0.01 * SR  # within 10 ms


@pytest.mark.parametrize("method", ["rubberband", "psola", "signalsmith"])
def test_shifter_handles_long_audio(method):
    # Longer than Rubber Band's 2**19-sample process() limit: output must not go silent.
    x = np.tile(sung([60, 62]), 25)  # ~30 s at 22.05 kHz
    assert len(x) > 2**19
    y = getattr(shifters, method)(x, SR, 2.0)
    tail = slice(len(x) - SR * 5, len(x))
    assert np.sqrt(np.mean(y[tail] ** 2)) > 0.5 * np.sqrt(np.mean(x[tail] ** 2))
