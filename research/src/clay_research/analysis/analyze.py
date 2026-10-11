"""analyze(audio) -> NoteModel: the Phase 1 analysis pipeline (SPEC § 3–4).

FCPE pitch (owner's choice) -> HMM note segmenter -> 5 ms frame track + notes.
Stereo input is analysed as mid (L+R)/2 (SPEC decision 2).
"""

from __future__ import annotations

import librosa
import numpy as np

from clay_research.datasets.common import PitchTrack
from clay_research.harness.trackers import fcpe
from clay_research.model.note_model import HOP_S, ModelNote, NoteModel

from .notes import segment

ANALYSIS_VERSION = "1.1-fcpe-hmm-breathgate"
MAX_ZCR = 0.08  # zero-crossing rate above this = hiss (breath, "s"), not a sung tone
MAX_JUMP_ST = 1.5  # a pitch jump bigger than this between 5 ms frames breaks a run
MIN_RUN_S = 0.04  # voiced runs shorter than this are noise, not singing


def frame_count(num_samples: int, sample_rate: int, hop_s: float = HOP_S) -> int:
    """Number of frames on the 5 ms grid, matching WORLD's frame layout."""
    return int(num_samples / sample_rate / hop_s) + 1


def _to_grid(track: PitchTrack, n: int, hop_s: float) -> np.ndarray:
    """Tracker pitch (any hop) -> MIDI on the 5 ms grid. Interpolates in semitones between
    voiced neighbours only, so unvoiced gaps stay unvoiced."""
    t_src = np.asarray(track.times, dtype=float)
    hz = np.asarray(track.frequencies_hz, dtype=float)
    with np.errstate(divide="ignore"):
        midi = np.where(hz > 0, 69 + 12 * np.log2(np.where(hz > 0, hz, 1.0) / 440.0), np.nan)
    t = np.arange(n) * hop_s
    idx = np.clip(np.searchsorted(t_src, t) - 1, 0, len(t_src) - 2)
    left, right = midi[idx], midi[idx + 1]
    frac = np.clip((t - t_src[idx]) / np.maximum(t_src[idx + 1] - t_src[idx], 1e-9), 0, 1)
    # NaN if either neighbour is unvoiced: a voicing edge never gets an invented pitch.
    return left + frac * (right - left)


def breath_gate(mono: np.ndarray, sample_rate: int, f0_midi: np.ndarray) -> np.ndarray:
    """Unvoice frames that are breaths or noise, not singing (owner heard inhales rebuilt
    as a warbly "phaser" tone: WORLD makes even the noise of a voiced frame pitched).

    FCPE calls ~1/3 of vocadito's unvoiced frames voiced. Breaths among them are hissy
    (high zero-crossing rate; sung frames stay below ~0.05) and their pitch jumps around,
    so a frame stays voiced only if it is not hissy and belongs to a stable pitch run of
    at least MIN_RUN_S."""
    hop = max(1, int(round(HOP_S * sample_rate)))
    n = len(f0_midi)
    zcr = librosa.feature.zero_crossing_rate(mono, frame_length=8 * hop, hop_length=hop)[0]
    zcr = np.pad(zcr, (0, max(0, n - len(zcr))), mode="edge")[:n]
    voiced = np.isfinite(f0_midi) & (zcr <= MAX_ZCR)
    jumps = np.r_[False, np.abs(np.diff(np.nan_to_num(f0_midi))) > MAX_JUMP_ST]
    keep = voiced.copy()
    i = 0
    while i < n:
        if not voiced[i]:
            i += 1
            continue
        j = i + 1
        while j < n and voiced[j] and not jumps[j]:
            j += 1
        if (j - i) * HOP_S < MIN_RUN_S:
            keep[i:j] = False
        i = j
    return np.where(keep, f0_midi, np.nan)


def analyze(audio: np.ndarray, sample_rate: int, gate_breaths: bool = True) -> NoteModel:
    mono = audio.mean(axis=1) if audio.ndim == 2 else audio
    mono = np.asarray(mono, dtype=np.float32)
    track = fcpe(mono, sample_rate)
    notes = segment(track, mono, sample_rate)

    n = frame_count(len(mono), sample_rate)
    f0_midi = _to_grid(track, n, HOP_S)
    if gate_breaths:
        f0_midi = breath_gate(mono, sample_rate, f0_midi)
    hop = max(1, int(round(HOP_S * sample_rate)))
    rms = librosa.feature.rms(y=mono, frame_length=4 * hop, hop_length=hop)[0]
    rms = np.pad(rms, (0, max(0, n - len(rms))), mode="edge")[:n]
    rms_db = 20 * np.log10(np.maximum(rms, 1e-5))

    return NoteModel(
        sample_rate=sample_rate,
        duration=len(mono) / sample_rate,
        f0_midi=f0_midi,
        rms_db=rms_db,
        notes=tuple(ModelNote(n.onset, n.offset, n.midi) for n in notes),
        analysis_version=ANALYSIS_VERSION,
    )
