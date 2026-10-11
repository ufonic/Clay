"""Alternative pitch shifters to compare against WORLD by ear (owner heard WORLD's notes as
"a little phasey" when shifted, 2026-10-11).

Each takes mono audio and a constant shift in semitones and returns audio of the same
length, formants preserved where the library can:

- **WORLD** (current): rebuilds every pitch cycle from an envelope + noise model. Clean
  control, but a slightly hollow/phasey "vocoder" tone on held notes.
- **Rubber Band R3** (pylibrb, GPLv2): a phase vocoder (FFT frames whose phases are kept
  consistent) with formant preservation. Used in many DAWs. Can smear sharp attacks.
- **PSOLA** (Praat via parselmouth, GPLv3): cuts the recording into single pitch cycles
  and re-spaces them closer (up) or further apart (down). The cycles are the real
  waveform, so the tone stays natural and formants stay put by construction; can get
  rough or "doubled" on breathy or creaky voice where cycles are hard to find.
- **Signalsmith Stretch** (python-stretch, MIT): a newer phase-vocoder design. This
  Python binding has **no formant preservation**, so +2 st sounds a bit smaller/brighter
  than the others for that reason alone.
"""

from __future__ import annotations

import numpy as np


def world(audio: np.ndarray, sr: int, semitones: float, model=None) -> np.ndarray:
    from clay_research.analysis.analyze import analyze

    from .world import render

    model = model if model is not None else analyze(audio, sr)
    return render(audio, model.with_all_edits(pitch_shift_st=semitones))


def rubberband(audio: np.ndarray, sr: int, semitones: float) -> np.ndarray:
    import pylibrb

    opts = (
        pylibrb.Option.PROCESS_OFFLINE
        | pylibrb.Option.ENGINE_FINER
        | pylibrb.Option.FORMANT_PRESERVED
    )
    rb = pylibrb.RubberBandStretcher(sr, 1, opts, 1.0, 2.0 ** (semitones / 12.0))
    x = pylibrb.reorder_to_rb(np.asarray(audio, dtype=pylibrb.DType)[:, None], 0)
    rb.set_expected_input_duration(len(audio))
    rb.study(x, final=True)
    rb.process(x, final=True)
    out = []
    while not rb.is_done():
        chunk = rb.retrieve_available()
        if chunk.size:
            out.append(chunk)
    y = pylibrb.reorder_from_rb(np.concatenate(out, axis=pylibrb.SAMPLES_AXIS), [None, 1])
    return _fit(y[:, 0], len(audio))


def psola(audio: np.ndarray, sr: int, semitones: float) -> np.ndarray:
    import parselmouth
    from parselmouth.praat import call

    snd = parselmouth.Sound(np.asarray(audio, dtype=np.float64), sampling_frequency=sr)
    manip = call(snd, "To Manipulation", 0.01, 60, 1000)
    tier = call(manip, "Extract pitch tier")
    call(tier, "Multiply frequencies", snd.xmin, snd.xmax, 2.0 ** (semitones / 12.0))
    call([tier, manip], "Replace pitch tier")
    out = call(manip, "Get resynthesis (overlap-add)")
    return _fit(out.values[0], len(audio))


def signalsmith(audio: np.ndarray, sr: int, semitones: float) -> np.ndarray:
    from python_stretch.Signalsmith import Stretch

    st = Stretch(0)  # fixed seed: deterministic output
    st.preset(1, float(sr))
    st.setTransposeSemitones(semitones)
    y = st.process(np.asarray(audio, dtype=np.float32)[None, :])[0]
    return _fit(y, len(audio))


def _fit(y: np.ndarray, n: int) -> np.ndarray:
    y = np.asarray(y, dtype=np.float32)[:n]
    return np.pad(y, (0, n - len(y))) if len(y) < n else y


def alignment_lag(reference: np.ndarray, y: np.ndarray, sr: int, max_s: float = 0.2) -> int:
    """Lag in samples of y behind reference, from the loudness envelopes (waveforms can't
    be compared directly once the pitch has changed). Positive = y is late."""
    hop = max(1, sr // 1000)  # 1 ms envelope

    def env(x):
        n = len(x) // hop
        return np.sqrt(np.mean(x[: n * hop].reshape(n, hop) ** 2, axis=1))

    a, b = env(reference), env(y)
    m = int(max_s * 1000)
    lags = range(-m, m + 1)
    scores = [
        np.dot(a[max(0, -k) : len(a) - max(0, k)], b[max(0, k) : len(b) - max(0, -k)]) for k in lags
    ]
    return int(list(lags)[int(np.argmax(scores))] * hop)
