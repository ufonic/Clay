# Note model: SPEC

The single source of truth (CLAUDE.md § 2). Python: `clay_research.model.note_model`.
C++: `clay::model::NoteModel` (`engine/include/clay/engine/NoteModel.h`). Both read and
write the same file and must agree on every derived curve (parity tests).

## 1. Contents

**Analysis** (computed once from the audio, never changed by editing)
- `f0_midi[t]`: pitch every 5 ms as fractional MIDI (60.0 = middle C); empty = unvoiced
- `rms_db[t]`: loudness every 5 ms
- notes: `onset`, `offset` (seconds), `center_midi` (the note's home pitch)
- `sample_rate`, `duration`, `analysis_version`

**Edits** (one set per note; the only thing editing changes)
- `pitch_shift_st`: move the note, semitones
- `drift_scale`: 1 = keep the singer's wobble/vibrato, 0 = flatten to center
- `formant_shift_st`: change voice character without changing pitch
- `gain_db`

Fields from the analysis SPEC that version 1 does not have yet (`voiced_prob`, per-note
envelope, sibilance, transitions) arrive with the tools that need them, in a new version.

## 2. File format: `clay.note_model` version 1 (JSON)

```json
{"schema": "clay.note_model", "version": 1,
 "sample_rate": 44100, "duration": 12.3, "analysis_version": "1.0-fcpe-hmm",
 "frames": {"hop_s": 0.005, "f0_midi": [null, 57.02, ...], "rms_db": [-80.0, ...]},
 "notes": [{"onset": 0.52, "offset": 0.91, "center_midi": 62.0,
            "edit": {"pitch_shift_st": 0.0, "drift_scale": 1.0,
                     "formant_shift_st": 0.0, "gain_db": 0.0}}]}
```

- Frame values are rounded to 4 decimals; `null` = unvoiced. Notes keep full precision.
- A reader rejects a file whose `schema` or `version` differs. Changing the format bumps
  `version`.

## 3. Derived curves (what the renderer uses)

- **Edit curves** (pitch, formant, gain, flatten = 1 − drift_scale): each note's edit holds
  from onset to offset. A gap of up to 0.3 s between two notes glides from one note's edit
  to the next, so slides and scoops move with the notes. Before the first note, after the
  last, and across longer gaps, the edit fades to zero over 30 ms.
- **Target pitch** = analysed pitch + pitch curve − flatten × (pitch − center), where
  center is the note under the frame (none outside notes, so nothing is flattened there).
- **Note span**: frames inside a note, within 30 ms of one, or in a bridged gap. The
  renderer rebuilds only these and keeps the original audio elsewhere (breaths, noise).

## 4. Parity

Fixtures in `engine/tests/fixtures/note_model/` (made by
`python -m clay_research.parity.note_model_fixtures`): a 12 s real vocal (vocadito, CC BY
4.0, numbers only) with varied edits, an edge-case set, and an empty model. C++ must
match Python's curves within 1e-9 and read/write files with identical values.
