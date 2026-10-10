"""Scoring metrics. Definitions match docs/ROADMAP.md § "Metric definitions"."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass

import mir_eval
import numpy as np

from clay_research.datasets.common import Note, PitchTrack, midi_to_hz

# Tolerances from the roadmap; change only with owner approval.
PITCH_TOLERANCE_CENTS = 50.0
ONSET_TOLERANCE_S = 0.05
OFFSET_RATIO = 0.2
TEMPO_TOLERANCE_BPM = 1.0


@dataclass(frozen=True)
class FrameScores:
    """Frame-level pitch tracking scores for one clip."""

    raw_pitch_accuracy: float  # share of ref-voiced frames within 50 cents
    voicing_recall: float
    voicing_false_alarm: float
    cents_error_median: float  # over frames voiced in both ref and est; nan if none
    cents_error_p95: float
    n_ref_voiced: int
    n_both_voiced: int

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


def frame_scores(ref: PitchTrack, est: PitchTrack) -> FrameScores:
    """Compare an estimated pitch track to a reference (est is resampled to ref's times)."""
    ref_v, ref_c, est_v, est_c = mir_eval.melody.to_cent_voicing(
        ref.times, ref.frequencies_hz, est.times, est.frequencies_hz
    )
    rpa = mir_eval.melody.raw_pitch_accuracy(
        ref_v, ref_c, est_v, est_c, cent_tolerance=PITCH_TOLERANCE_CENTS
    )
    recall, false_alarm = mir_eval.melody.voicing_measures(ref_v, est_v)
    both = (ref_v > 0) & (est_v > 0)
    errors = np.abs(ref_c[both] - est_c[both])
    return FrameScores(
        raw_pitch_accuracy=float(rpa),
        voicing_recall=float(recall),
        voicing_false_alarm=float(false_alarm),
        cents_error_median=float(np.median(errors)) if errors.size else float("nan"),
        cents_error_p95=float(np.percentile(errors, 95)) if errors.size else float("nan"),
        n_ref_voiced=int((ref_v > 0).sum()),
        n_both_voiced=int(both.sum()),
    )


@dataclass(frozen=True)
class NoteScores:
    """Note transcription scores for one clip."""

    f1: float  # onset-only: the gate metric
    precision: float
    recall: float
    f1_with_offsets: float  # informational

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


def _note_arrays(notes: Sequence[Note]) -> tuple[np.ndarray, np.ndarray]:
    if not notes:
        return np.zeros((0, 2)), np.zeros(0)
    intervals = np.array([[n.onset, n.offset] for n in notes], dtype=float)
    pitches = midi_to_hz(np.array([n.midi for n in notes], dtype=float))
    return intervals, pitches


def note_scores(ref: Sequence[Note], est: Sequence[Note]) -> NoteScores:
    ref_i, ref_p = _note_arrays(ref)
    est_i, est_p = _note_arrays(est)
    p, r, f, _ = mir_eval.transcription.precision_recall_f1_overlap(
        ref_i,
        ref_p,
        est_i,
        est_p,
        onset_tolerance=ONSET_TOLERANCE_S,
        pitch_tolerance=PITCH_TOLERANCE_CENTS,
        offset_ratio=None,
    )
    _, _, f_off, _ = mir_eval.transcription.precision_recall_f1_overlap(
        ref_i,
        ref_p,
        est_i,
        est_p,
        onset_tolerance=ONSET_TOLERANCE_S,
        pitch_tolerance=PITCH_TOLERANCE_CENTS,
        offset_ratio=OFFSET_RATIO,
    )
    return NoteScores(
        f1=float(f), precision=float(p), recall=float(r), f1_with_offsets=float(f_off)
    )


def tempo_correct(ref_bpm: float, est_bpm: float) -> bool:
    """Strict tempo check: within ±1 BPM; double/half tempo counts as wrong."""
    return abs(est_bpm - ref_bpm) <= TEMPO_TOLERANCE_BPM


def tempo_accuracy1(ref_bpm: float, est_bpm: float) -> bool:
    """Published-style Accuracy1: within ±4%."""
    return abs(est_bpm - ref_bpm) <= 0.04 * ref_bpm


def tempo_accuracy2(ref_bpm: float, est_bpm: float) -> bool:
    """Published-style Accuracy2: within ±4% of ref × {1, 2, 3, 1/2, 1/3}."""
    return any(tempo_accuracy1(ref_bpm * k, est_bpm) for k in (1, 2, 3, 1 / 2, 1 / 3))


def key_exact(ref_key: str, est_key: str) -> bool:
    """Exact tonic + mode match, e.g. 'C# minor'. Enharmonic spellings count as equal."""
    return mir_eval.key.weighted_score(ref_key, est_key) == 1.0


def key_weighted(ref_key: str, est_key: str) -> float:
    """MIREX weighted key score (fifth 0.5, relative 0.3, parallel 0.2)."""
    return float(mir_eval.key.weighted_score(ref_key, est_key))
