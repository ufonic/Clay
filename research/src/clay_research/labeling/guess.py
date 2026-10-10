"""First-guess note segmentation so the owner corrects notes instead of drawing them all.

Deliberately simple (Phase 1 builds the real HMM segmenter): take the pYIN pitch track,
split it wherever the voice stops or the pitch moves to a new semitone and stays there,
and give each piece the median pitch. Pieces shorter than MIN_NOTE_S are dropped.
"""

from __future__ import annotations

import numpy as np

from clay_research.datasets.common import Note, PitchTrack

MIN_NOTE_S = 0.06  # shorter blips are usually consonants or glitches
JUMP_SEMITONES = 0.7  # a pitch change this big that lasts ...
JUMP_HOLD_S = 0.05  # ... this long starts a new note


def hz_to_midi(hz: np.ndarray) -> np.ndarray:
    hz = np.asarray(hz, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        midi = 69.0 + 12.0 * np.log2(hz / 440.0)
    return np.where(hz > 0, midi, np.nan)


def _split_points(midi: np.ndarray, hop_s: float) -> list[int]:
    """Indices inside one voiced run where a new note starts."""
    hold = max(1, round(JUMP_HOLD_S / hop_s))
    splits, anchor = [], 0
    i = 1
    while i < len(midi):
        reference = np.median(midi[anchor:i])
        window = midi[i : i + hold]
        if len(window) == hold and np.all(np.abs(window - reference) > JUMP_SEMITONES):
            splits.append(i)
            anchor = i
            i += hold
        else:
            i += 1
    return splits


def guess_notes(track: PitchTrack) -> list[Note]:
    times = np.asarray(track.times, dtype=float)
    if len(times) < 2:
        return []
    hop_s = float(np.median(np.diff(times)))
    midi = hz_to_midi(track.frequencies_hz)
    voiced = np.isfinite(midi)

    notes: list[Note] = []
    i = 0
    while i < len(midi):
        if not voiced[i]:
            i += 1
            continue
        j = i
        while j < len(midi) and voiced[j]:
            j += 1
        run = midi[i:j]
        bounds = [0, *_split_points(run, hop_s), len(run)]
        for a, b in zip(bounds, bounds[1:], strict=False):
            onset = times[i + a]
            offset = times[i + b - 1] + hop_s
            if offset - onset >= MIN_NOTE_S:
                notes.append(
                    Note(
                        onset=float(onset),
                        offset=float(offset),
                        midi=float(np.round(np.median(run[a:b]))),
                    )
                )
        i = j
    return notes
