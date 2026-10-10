"""The note model: the single source of truth (CLAUDE.md § 2; task 1.4).

Two parts, kept separate on purpose:
- **analysis**: what was sung (frame pitch every 5 ms, loudness, the notes). Computed once
  from the audio, never changed by editing.
- **edits**: one small set of parameters per note (pitch shift, drift amount, formant
  shift, gain). Editing only ever changes these numbers; audio is always rendered from
  analysis + edits, so "undo everything" is just "reset the edits".

Serialized as JSON (schema below) so the C++ engine (Phase 2) reads and writes the same
files. Frame arrays use null for "unvoiced". Times are seconds; pitches are fractional
MIDI note numbers (60.0 = middle C, 60.5 = 50 cents sharp).

    {"schema": "clay.note_model", "version": 1,
     "sample_rate": 44100, "duration": 12.3, "analysis_version": "1.0",
     "frames": {"hop_s": 0.005, "f0_midi": [null, 57.02, ...], "rms_db": [-80.0, ...]},
     "notes": [{"onset": 0.52, "offset": 0.91, "center_midi": 62.0,
                "edit": {"pitch_shift_st": 0.0, "drift_scale": 1.0,
                         "formant_shift_st": 0.0, "gain_db": 0.0}}, ...]}
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

import numpy as np

SCHEMA = "clay.note_model"
VERSION = 1
HOP_S = 0.005  # SPEC decision 1: 5 ms frames
TRANSITION_S = 0.03  # edits fade in/out over 30 ms at note edges so pitch never jumps


@dataclass(frozen=True)
class NoteEdit:
    pitch_shift_st: float = 0.0  # move the whole note, semitones
    drift_scale: float = 1.0  # 1 = keep the singer's wobble/vibrato; 0 = flatten to center
    formant_shift_st: float = 0.0  # change voice character without changing pitch
    gain_db: float = 0.0

    def is_neutral(self) -> bool:
        return self == NoteEdit()


@dataclass(frozen=True)
class ModelNote:
    onset: float
    offset: float
    center_midi: float
    edit: NoteEdit = field(default_factory=NoteEdit)


@dataclass(frozen=True)
class NoteModel:
    sample_rate: int
    duration: float
    f0_midi: np.ndarray  # per 5 ms frame, NaN = unvoiced
    rms_db: np.ndarray
    notes: tuple[ModelNote, ...]
    analysis_version: str = "1.0"
    hop_s: float = HOP_S

    @property
    def times(self) -> np.ndarray:
        return np.arange(len(self.f0_midi)) * self.hop_s

    # --- editing (returns a new model; analysis is never touched) ---
    def with_edit(self, index: int, **changes: float) -> NoteModel:
        notes = list(self.notes)
        notes[index] = replace(notes[index], edit=replace(notes[index].edit, **changes))
        return replace(self, notes=tuple(notes))

    def with_all_edits(self, **changes: float) -> NoteModel:
        return replace(
            self, notes=tuple(replace(n, edit=replace(n.edit, **changes)) for n in self.notes)
        )

    def reset_edits(self) -> NoteModel:
        return replace(self, notes=tuple(replace(n, edit=NoteEdit()) for n in self.notes))

    # --- what to render ---
    def _edit_curves(self) -> dict[str, np.ndarray]:
        """Per-frame edit amounts, faded over TRANSITION_S at each note edge."""
        t = self.times
        curves = {k: np.zeros(len(t)) for k in ("pitch", "formant", "gain", "flatten", "weight")}
        fade = max(TRANSITION_S, self.hop_s)
        for n in self.notes:
            # Trapezoid: 0 before onset - fade/2, 1 inside, 0 after offset + fade/2.
            w = np.clip(
                np.minimum(t - (n.onset - fade / 2), (n.offset + fade / 2) - t) / fade, 0.0, 1.0
            )
            e = n.edit
            curves["pitch"] += w * e.pitch_shift_st
            curves["formant"] += w * e.formant_shift_st
            curves["gain"] += w * e.gain_db
            curves["flatten"] += w * (1.0 - e.drift_scale)
            curves["weight"] += w
        return curves

    def target_f0_midi(self) -> np.ndarray:
        """The pitch to render per frame: each note's center + shift, plus its drift scaled."""
        curves = self._edit_curves()
        f0 = self.f0_midi.copy()
        center = np.full(len(f0), np.nan)
        for n in self.notes:
            inside = (self.times >= n.onset) & (self.times < n.offset)
            center[inside] = n.center_midi
        # Outside notes (transitions) flattening has nothing to pull toward; keep the pitch.
        drift = np.where(np.isfinite(center), f0 - center, 0.0)
        return f0 + curves["pitch"] - curves["flatten"] * drift

    def formant_shift_st(self) -> np.ndarray:
        return self._edit_curves()["formant"]

    def gain_db(self) -> np.ndarray:
        return self._edit_curves()["gain"]

    def is_neutral(self) -> bool:
        return all(n.edit.is_neutral() for n in self.notes)

    # --- JSON ---
    def to_json(self) -> str:
        def arr(a: np.ndarray) -> list:
            return [None if not np.isfinite(v) else round(float(v), 4) for v in a]

        return json.dumps(
            {
                "schema": SCHEMA,
                "version": VERSION,
                "sample_rate": self.sample_rate,
                "duration": round(self.duration, 6),
                "analysis_version": self.analysis_version,
                "frames": {
                    "hop_s": self.hop_s,
                    "f0_midi": arr(self.f0_midi),
                    "rms_db": arr(self.rms_db),
                },
                # Notes keep full precision so save/load round-trips exactly.
                "notes": [
                    {
                        "onset": float(n.onset),
                        "offset": float(n.offset),
                        "center_midi": float(n.center_midi),
                        "edit": asdict(n.edit),
                    }
                    for n in self.notes
                ],
            }
        )

    @classmethod
    def from_json(cls, text: str) -> NoteModel:
        d = json.loads(text)
        if d.get("schema") != SCHEMA:
            raise ValueError("not a Clay note model")
        if d.get("version") != VERSION:
            raise ValueError(f"unsupported note model version {d.get('version')}")

        def arr(xs: list) -> np.ndarray:
            return np.array([np.nan if v is None else v for v in xs], dtype=float)

        return cls(
            sample_rate=int(d["sample_rate"]),
            duration=float(d["duration"]),
            f0_midi=arr(d["frames"]["f0_midi"]),
            rms_db=arr(d["frames"]["rms_db"]),
            notes=tuple(
                ModelNote(n["onset"], n["offset"], n["center_midi"], NoteEdit(**n["edit"]))
                for n in d["notes"]
            ),
            analysis_version=d.get("analysis_version", "1.0"),
            hop_s=float(d["frames"]["hop_s"]),
        )

    def save(self, path: Path) -> None:
        path.write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> NoteModel:
        return cls.from_json(path.read_text(encoding="utf-8"))
