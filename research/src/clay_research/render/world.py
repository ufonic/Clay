"""Render audio from a note model with the WORLD vocoder (task 1.5).

Plain-language version: WORLD splits a voice into three ingredients every 5 ms:
- the **pitch** (F0): how fast the vocal folds vibrate;
- the **spectral envelope**: the shape of the throat and mouth, which makes the vowel
  and the singer's character (the formants);
- the **aperiodicity**: how breathy/noisy each frequency band is.
It can rebuild the sound from those ingredients. To change pitch we hand it a new F0 but
the *same* envelope, so the voice keeps its character instead of sounding like a
chipmunk. A formant shift stretches the envelope along the frequency axis on purpose.

What to listen for: a slightly "buzzy" or "phasey" quality on held notes, roughness on
very breathy or creaky passages, and smeared consonants. Those are WORLD's typical
artifacts; the owner judges whether they're acceptable at ±2 semitones (Phase 1 gate).
"""

from __future__ import annotations

import numpy as np
import pyworld

from clay_research.datasets.common import midi_to_hz
from clay_research.model.note_model import NoteModel


def _warp_envelope(sp: np.ndarray, shift_st: np.ndarray) -> np.ndarray:
    """Move formants up (shift > 0) or down per frame by stretching the envelope."""
    if not np.any(shift_st):
        return sp
    bins = np.arange(sp.shape[1], dtype=float)
    out = sp.copy()
    for i in np.nonzero(shift_st)[0]:
        factor = 2.0 ** (shift_st[i] / 12.0)
        out[i] = np.interp(bins / factor, bins, sp[i], right=sp[i, -1])
    return out


def world_parameters(audio: np.ndarray, model: NoteModel) -> tuple[np.ndarray, ...]:
    """WORLD's three ingredients for one channel, using the model's analysed pitch."""
    x = np.ascontiguousarray(audio, dtype=np.float64)
    fs = model.sample_rate
    t = model.times
    f0 = np.where(np.isfinite(model.f0_midi), midi_to_hz(np.nan_to_num(model.f0_midi)), 0.0)
    sp = pyworld.cheaptrick(x, f0, t, fs)
    ap = pyworld.d4c(x, f0, t, fs)
    return f0, sp, ap


def render(audio: np.ndarray, model: NoteModel) -> np.ndarray:
    """Audio for the model's edits. Mono or (samples, channels); each channel is rebuilt
    with the same edits (SPEC decision 2)."""
    if audio.ndim == 2:
        return np.stack([render(audio[:, c], model) for c in range(audio.shape[1])], axis=1)
    f0, sp, ap = world_parameters(audio, model)
    target = model.target_f0_midi()
    f0_out = np.where((f0 > 0) & np.isfinite(target), midi_to_hz(np.nan_to_num(target)), 0.0)
    sp_out = _warp_envelope(sp, model.formant_shift_st())
    sp_out = sp_out * (10.0 ** (model.gain_db() / 10.0))[:, None]  # envelope is power
    y = pyworld.synthesize(f0_out, sp_out, ap, model.sample_rate, model.hop_s * 1000.0)
    y = y[: len(audio)]
    if len(y) < len(audio):
        y = np.pad(y, (0, len(audio) - len(y)))
    return y.astype(np.float32)
