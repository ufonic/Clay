import numpy as np
import pytest

from clay_research.analysis.analyze import analyze, frame_count
from clay_research.harness.trackers import fcpe
from clay_research.model.note_model import ModelNote, NoteEdit, NoteModel
from clay_research.render.world import _warp_envelope, render

SR = 22050


def sung(midis, seconds_each=0.5, sr=SR, vibrato=0.0):
    """Harmonic 'voice': consecutive notes with short gaps, optional vibrato (semitones)."""
    out = []
    for m in midis:
        t = np.arange(int(sr * seconds_each)) / sr
        inst = 440 * 2 ** ((m + vibrato * np.sin(2 * np.pi * 5.5 * t) - 69) / 12)
        phase = 2 * np.pi * np.cumsum(inst) / sr
        tone = sum(0.25 / k * np.sin(k * phase) for k in range(1, 8))
        env = np.minimum(1, np.minimum(t, t[::-1]) / 0.02)
        out += [tone * env, np.zeros(int(0.1 * sr))]
    return np.concatenate(out).astype(np.float32)


def pitch_change(x, y, sr=SR):
    """Median frame-by-frame pitch difference (semitones) where both are voiced."""
    a, b = fcpe(x, sr), fcpe(y, sr)
    n = min(len(a.frequencies_hz), len(b.frequencies_hz))
    fa, fb = a.frequencies_hz[:n], b.frequencies_hz[:n]
    both = (fa > 0) & (fb > 0)
    return float(np.median(12 * np.log2(fb[both] / fa[both])))


def tiny_model(f0, notes):
    return NoteModel(
        sample_rate=SR,
        duration=len(f0) * 0.005,
        f0_midi=np.asarray(f0, float),
        rms_db=np.zeros(len(f0)),
        notes=tuple(notes),
    )


def test_json_round_trip_keeps_everything():
    f0 = [np.nan] * 10 + [60.1] * 50 + [np.nan] * 10
    m = tiny_model(f0, [ModelNote(0.05, 0.3, 60.0, NoteEdit(pitch_shift_st=2, gain_db=-3))])
    back = NoteModel.from_json(m.to_json())
    assert back.notes == m.notes
    np.testing.assert_allclose(back.f0_midi, m.f0_midi, equal_nan=True, atol=1e-4)
    with pytest.raises(ValueError):
        NoteModel.from_json('{"schema": "something else"}')


def test_edits_never_touch_the_analysis():
    f0 = [62.0 + 0.3 * np.sin(i / 3) for i in range(100)]
    m = tiny_model(f0, [ModelNote(0.0, 0.5, 62.0)])
    edited = m.with_edit(0, pitch_shift_st=1.0, drift_scale=0.0)
    np.testing.assert_array_equal(edited.f0_midi, m.f0_midi)  # analysis unchanged
    assert edited.reset_edits() == m or edited.reset_edits().notes == m.notes
    assert m.is_neutral() and not edited.is_neutral()


def test_target_pitch_shift_and_flatten():
    f0 = [62.0 + 0.4 * np.sin(i / 2) for i in range(200)]  # 1 s of wobbly D4
    m = tiny_model(f0, [ModelNote(0.0, 1.0, 62.0)])
    middle = slice(40, 160)
    np.testing.assert_allclose(m.target_f0_midi()[middle], np.asarray(f0)[middle])
    up = m.with_edit(0, pitch_shift_st=2.0).target_f0_midi()
    np.testing.assert_allclose(up[middle], np.asarray(f0)[middle] + 2.0)
    flat = m.with_edit(0, drift_scale=0.0).target_f0_midi()
    np.testing.assert_allclose(flat[middle], 62.0)


def test_edits_fade_in_at_note_edges_so_pitch_never_jumps():
    f0 = [60.0] * 200
    m = tiny_model(f0, [ModelNote(0.5, 1.0, 60.0, NoteEdit(pitch_shift_st=3.0))])
    target = m.target_f0_midi()
    assert np.max(np.abs(np.diff(target))) < 3.0 / 3  # spread over several frames


def test_voiced_gap_between_notes_moves_with_them():
    # Two notes with a 0.1 s voiced slide between them: a whole-vocal shift must cover it.
    f0 = list(np.linspace(60.0, 62.0, 200))
    m = tiny_model(f0, [ModelNote(0.0, 0.45, 60.0), ModelNote(0.55, 1.0, 62.0)])
    shift = m.with_all_edits(pitch_shift_st=2.0).target_f0_midi() - m.f0_midi
    np.testing.assert_allclose(shift[:190], 2.0)
    # Different edits on each side glide across the gap instead of jumping.
    glide = m.with_edit(0, pitch_shift_st=-1.0).with_edit(1, pitch_shift_st=1.0)
    assert np.max(np.abs(np.diff(glide.target_f0_midi() - m.f0_midi))) < 0.15


def test_long_gap_fades_edit_out():
    f0 = [60.0] * 400  # 2 s
    m = tiny_model(f0, [ModelNote(0.0, 0.5, 60.0), ModelNote(1.5, 2.0, 60.0)])
    shift = m.with_all_edits(pitch_shift_st=2.0).target_f0_midi() - m.f0_midi
    assert shift[200] == 0.0  # 1.0 s: middle of a 1 s gap, no edit


def test_formant_warp_moves_envelope_peak():
    bins = np.arange(513)
    sp = np.exp(-0.5 * ((bins - 100) / 10.0) ** 2)[None, :]
    up = _warp_envelope(sp, np.array([12.0]))  # one octave up
    assert np.argmax(up[0]) == pytest.approx(200, abs=2)


def test_analyze_frames_match_world_grid():
    x = sung([60, 64])
    m = analyze(x, SR)
    assert len(m.f0_midi) == frame_count(len(x), SR)
    assert [round(n.center_midi) for n in m.notes] == [60, 64]


@pytest.mark.parametrize("shift", [-2.0, -1.0, 1.0, 2.0])
def test_world_render_shifts_pitch_by_the_edit(shift):
    x = sung([57, 60], vibrato=0.3)
    m = analyze(x, SR)
    y = render(x, m.with_all_edits(pitch_shift_st=shift))
    assert len(y) == len(x)
    assert pitch_change(x, y) == pytest.approx(shift, abs=0.1)


def test_neutral_render_keeps_pitch():
    x = sung([62])
    y = render(x, analyze(x, SR))
    assert pitch_change(x, y) == pytest.approx(0.0, abs=0.05)
