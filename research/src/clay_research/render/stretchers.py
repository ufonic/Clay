"""Time stretchers to compare by ear (task 1.6).

Each takes mono audio and `ratio` = output length / input length (1.1 = 10% slower,
0.9 = 10% faster) and returns audio of length round(len(audio) * ratio), pitch unchanged.

- **Rubber Band R3** (pylibrb, GPLv2): phase vocoder; the industry standard in DAWs.
  Can soften sharp attacks; can sound slightly "smeared" or reverberant when slowed.
- **Signalsmith Stretch** (python-stretch, MIT): newer phase-vocoder design, aimed at
  musical material with fewer phasing artifacts. Same artifact family as Rubber Band.
- **WORLD frames**: Clay already rebuilds notes from WORLD's 5 ms frames, so stretching a
  note can mean playing those frames slower or faster. Pitch, voice shape and noise are
  interpolated between frames. Fits the note model best (each note stretched on its own);
  artifacts are WORLD's own (slight phasiness) plus possible "steppy" vibrato when slowed.
  Frames outside notes are rebuilt as noise (no pitch) to avoid the breath warble.
"""

from __future__ import annotations

import numpy as np

from .shifters import RB_BLOCK


def out_length(n: int, ratio: float) -> int:
    return int(round(n * ratio))


def _fit(y: np.ndarray, n: int) -> np.ndarray:
    y = np.asarray(y, dtype=np.float32)[:n]
    return np.pad(y, (0, n - len(y))) if len(y) < n else y


def rubberband(audio: np.ndarray, sr: int, ratio: float) -> np.ndarray:
    import pylibrb

    opts = pylibrb.Option.PROCESS_OFFLINE | pylibrb.Option.ENGINE_FINER
    rb = pylibrb.RubberBandStretcher(sr, 1, opts, ratio, 1.0)
    x = pylibrb.reorder_to_rb(np.asarray(audio, dtype=pylibrb.DType)[:, None], 0)
    rb.set_expected_input_duration(len(audio))
    rb.set_max_process_size(RB_BLOCK)
    rb.study(x, final=True)
    out = []
    for start in range(0, len(audio), RB_BLOCK):
        block = (
            x[..., start : start + RB_BLOCK]
            if pylibrb.SAMPLES_AXIS
            else x[start : start + RB_BLOCK]
        )
        rb.process(block, final=start + RB_BLOCK >= len(audio))
        chunk = rb.retrieve_available()
        if chunk.size:
            out.append(chunk)
    while not rb.is_done():
        chunk = rb.retrieve_available()
        if chunk.size:
            out.append(chunk)
    y = pylibrb.reorder_from_rb(np.concatenate(out, axis=pylibrb.SAMPLES_AXIS), [None, 1])
    return _fit(y[:, 0], out_length(len(audio), ratio))


def signalsmith(audio: np.ndarray, sr: int, ratio: float) -> np.ndarray:
    from python_stretch.Signalsmith import Stretch

    st = Stretch(0)
    st.preset(1, float(sr))
    st.setTimeFactor(1.0 / ratio)  # the binding's time factor is a speed
    y = st.process(np.asarray(audio, dtype=np.float32)[None, :])[0]
    return _fit(y, out_length(len(audio), ratio))


def world(audio: np.ndarray, sr: int, ratio: float, model=None) -> np.ndarray:
    import pyworld

    from clay_research.analysis.analyze import analyze

    from .world import _remove_sub_bass, world_parameters

    model = model if model is not None else analyze(audio, sr)
    f0, sp, ap = world_parameters(audio, model)
    f0 = np.where(model.note_span(), f0, 0.0)  # breaths -> noise, not a pitched warble
    n_src = len(f0)
    n_out = int(round(n_src * ratio))
    pos = np.minimum(np.arange(n_out) / ratio, n_src - 1)
    i0 = np.floor(pos).astype(int)
    i1 = np.minimum(i0 + 1, n_src - 1)
    frac = (pos - i0)[:, None]
    sp_o = np.exp((1 - frac) * np.log(sp[i0]) + frac * np.log(sp[i1]))
    ap_o = (1 - frac) * ap[i0] + frac * ap[i1]
    both = (f0[i0] > 0) & (f0[i1] > 0)
    f0_lin = np.exp(
        (1 - frac[:, 0]) * np.log(np.maximum(f0[i0], 1))
        + frac[:, 0] * np.log(np.maximum(f0[i1], 1))
    )
    f0_o = np.where(both, f0_lin, np.where(frac[:, 0] < 0.5, f0[i0], f0[i1]))
    y = pyworld.synthesize(
        np.ascontiguousarray(f0_o),
        np.ascontiguousarray(sp_o),
        np.ascontiguousarray(ap_o),
        sr,
        model.hop_s * 1000.0,
    )
    y = _remove_sub_bass(y, model)
    return _fit(y, out_length(len(audio), ratio))
