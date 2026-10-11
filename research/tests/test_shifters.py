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
