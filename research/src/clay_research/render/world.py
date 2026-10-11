"""Render audio from a note model with the WORLD vocoder (task 1.5).

Plain-language version: WORLD splits a voice into three ingredients every 5 ms:
- the **pitch** (F0): how fast the vocal folds vibrate;
- the **spectral envelope**: the shape of the throat and mouth, which makes the vowel
  and the singer's character (the formants);
- the **aperiodicity**: how breathy/noisy each frequency band is.
It can rebuild the sound from those ingredients. To change pitch we hand it a new F0 but
the *same* envelope, so the voice keeps its character instead of sounding like a
chipmunk. A formant shift stretches the envelope along the frequency axis on purpose.

Only the notes are rebuilt. Breaths and noise between phrases stay the original
recording (crossfaded), because WORLD turns them into a warbly "phaser" tone.

What to listen for: a slightly "buzzy" or "phasey" quality on held notes, roughness on
very breathy or creaky passages, and smeared consonants. Those are WORLD's typical
artifacts; the owner judges whether they're acceptable at ±2 semitones (Phase 1 gate).
"""

from __future__ import annotations

import numpy as np
import pyworld
import scipy.signal

from clay_research.datasets.common import midi_to_hz
from clay_research.model.note_model import NoteModel

SUB_BASS_MAX_HZ = 70.0
SPLICE_FADE_S = 0.02  # crossfade between rebuilt notes and original breaths


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
    """WORLD's three ingredients for one channel, using the model's analysed pitch.

    (Tried 2026-10-11 and removed: WORLD's StoneMask pitch refinement. It wandered up to
    3 semitones inside held notes, and the owner heard glitches on long notes.)"""
    x = np.ascontiguousarray(audio, dtype=np.float64)
    fs = model.sample_rate
    t = model.times
    f0 = np.where(np.isfinite(model.f0_midi), midi_to_hz(np.nan_to_num(model.f0_midi)), 0.0)
    sp = pyworld.cheaptrick(x, f0, t, fs)
    ap = pyworld.d4c(x, f0, t, fs)
    return f0, sp, ap


def _remove_sub_bass(y: np.ndarray, model: NoteModel) -> np.ndarray:
    """High-pass below the singer's lowest note. WORLD adds rumble below 70 Hz (owner heard
    sub-bass; measured up to 10 dB more than the original on female vocals). Cutoff is
    0.6 x the lowest sung pitch, capped at 70 Hz, so no real voice content is touched."""
    voiced = model.f0_midi[np.isfinite(model.f0_midi)]
    lowest = float(midi_to_hz(np.percentile(voiced, 2))) if voiced.size else 100.0
    cutoff = min(SUB_BASS_MAX_HZ, 0.6 * lowest)
    sos = scipy.signal.butter(4, cutoff, "highpass", fs=model.sample_rate, output="sos")
    return scipy.signal.sosfiltfilt(sos, y)


def _per_sample(frames: np.ndarray, model: NoteModel, n: int) -> np.ndarray:
    return np.interp(np.arange(n) / model.sample_rate, model.times, frames)


def resynth_weight(model: NoteModel, n: int) -> np.ndarray:
    """Per sample: 1 = use WORLD's rebuild, 0 = use the original recording. WORLD is only
    needed where notes are (that's where edits happen); breaths and noise between phrases
    stay original (owner heard WORLD turn them into a "phaser" warble on every clip).
    Switches crossfade over SPLICE_FADE_S."""
    span = model.note_span().astype(float)
    k = max(1, int(round(SPLICE_FADE_S / model.hop_s)))
    smooth = np.convolve(span, np.ones(k) / k, mode="same")
    return np.clip(_per_sample(smooth, model, n), 0.0, 1.0)


def render(audio: np.ndarray, model: NoteModel, high_pass: bool = True) -> np.ndarray:
    """Audio for the model's edits. Mono or (samples, channels); each channel is rebuilt
    with the same edits (SPEC decision 2)."""
    if audio.ndim == 2:
        return np.stack(
            [render(audio[:, c], model, high_pass) for c in range(audio.shape[1])], axis=1
        )
    original = np.asarray(audio, dtype=np.float64)
    f0, sp, ap = world_parameters(original, model)
    target = model.target_f0_midi()
    f0_out = np.where((f0 > 0) & np.isfinite(target), midi_to_hz(np.nan_to_num(target)), 0.0)
    gain_db = model.gain_db()
    sp_out = _warp_envelope(sp, model.formant_shift_st())
    sp_out = sp_out * (10.0 ** (gain_db / 10.0))[:, None]  # envelope is power
    y = pyworld.synthesize(f0_out, sp_out, ap, model.sample_rate, model.hop_s * 1000.0)
    y = y[: len(original)]
    if len(y) < len(original):
        y = np.pad(y, (0, len(original) - len(y)))
    if high_pass:
        y = _remove_sub_bass(y, model)

    n = len(original)
    w = resynth_weight(model, n)
    # WORLD's rebuild comes out ~1.5 dB hot; match it to the original where notes are
    # unedited in gain, so splices into the original audio don't jump in level.
    ref = (w > 0.99) & (np.abs(_per_sample(gain_db, model, n)) < 1e-6)
    if np.any(ref):
        y *= np.sqrt(np.mean(original[ref] ** 2) / max(np.mean(y[ref] ** 2), 1e-20))
    kept = original * 10.0 ** (_per_sample(gain_db, model, n) / 20.0)
    return (w * y + (1.0 - w) * kept).astype(np.float32)
