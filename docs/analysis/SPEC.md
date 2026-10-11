# Analysis module: SPEC

**Status:** approved by the owner 2026-10-10 (task 0.11) · **Phases:** prototype in Phase 1 (Python), port in Phase 2 (C++)

## 1. What it does

Analysis listens to a recorded clip once, offline, and writes down what was sung: the pitch at every moment, where each note starts and ends, what note it was, and what the voice sounded like during it. Everything the editor shows (blobs, pitch curves, amplitude) and everything resynthesis needs comes from this one result. It never changes audio (CLAUDE.md invariant).

```
audio clip ──► F0 tracker ──► note segmenter ──► per-note features ──► AnalysisResult ──► cache on disk
               (pitch every     (where notes       (center pitch, drift,
                5 ms + voiced?)   start/stop)        loudness, formants, sibilance)
```

## 2. Inputs

| Input | Rule |
|---|---|
| Audio | Mono or stereo, 44.1–96 kHz, float. Any length up to 20 minutes. |
| Stereo | Analysed as the **mid** signal (L+R)/2; the result applies to both channels. Resynthesis later processes each channel with the same edits. |
| Mode | `melodic` (Phases 1–4). `percussive` / `universal` arrive in Phase 5. |
| Settings | Optional pitch range hint (default C2–C6, 65–1047 Hz). |

## 3. Output: `AnalysisResult`

All times are seconds from the clip start; pitches are fractional MIDI note numbers (60.0 = middle C, 60.5 = 50 cents sharp) because that is what the editor draws and what cents maths needs.

**Frame track** (one value every **5 ms**)
- `f0_midi[t]`: pitch, or empty when unvoiced
- `voiced_prob[t]`: 0–1 confidence that someone is singing a pitch here
- `rms_db[t]`: loudness

**Notes** (the blobs), each with:

| Field | Meaning |
|---|---|
| `onset`, `offset` | Start and end, seconds |
| `center_midi` | The note's "home" pitch: amplitude-weighted median of F0 over the note's stable middle (transitions at each end excluded). This is what the pitch tool moves. |
| `drift_cents[t]` | F0 minus center, in cents, for every frame of the note (includes vibrato, scoops, wobble). Phase 4 splits it into vibrato + slow drift. |
| `gain_db` | Overall note level |
| `envelope` | Spectral envelope (the formants) sampled every 10 ms: used to keep the voice's character when shifting pitch |
| `sibilance` | Share of the note's energy in unvoiced high-frequency noise (the "s"/"sh"); the edit control comes in Phase 4 |
| `transition_in`, `transition_out` | Length of the pitch glide into/out of the note |

Plus `analysis_version`, `sample_rate`, `duration`, and the settings used.

## 4. How (Phase 1 plan; final choices need the owner's ear)

1. **F0 tracking.** Baseline **pYIN** (already scored: RPA 0.964 on MIR-1K). Candidates **CREPE** and **FCPE** (neural; usually better on breathy or noisy takes). Pitch is tracked on a 16 kHz copy of the audio (what the neural models expect); features below use full-rate audio. Choice made by the harness *and* the owner's ear (CLAUDE.md rule 9).
2. **Voicing.** pYIN currently marks 32% of silent/unvoiced frames as voiced; fixing that is a Phase 1 target because it creates ghost blobs. Plan: combine the tracker's confidence with loudness and a minimum note length.
3. **Note segmentation.** A hidden Markov model (HMM) that treats singing as moving between "attack → stable → release → silence" states for each candidate pitch (after Mauch et al.'s pYIN note tracker). It uses F0, voicing, and loudness, so vibrato stays one note and a re-attack on the same pitch becomes two.
4. **Per-note features.** Center pitch and drift from the F0 track; envelope via WORLD's CheapTrick (the same analysis WORLD resynthesis uses, so analysis and resynthesis agree); sibilance from high-band energy in unvoiced frames.

## 5. Accuracy targets (from `docs/ROADMAP.md`)

| Measure | Target (Phase 1 gate) | Data |
|---|---|---|
| Note F1 (onset ±50 ms, pitch ±50 cents), mean vs both annotators | ≥ 0.70 (owner decision 2026-10-10; human agreement 0.740, known gap) | vocadito |
| Raw pitch accuracy | ≥ 0.95 | MIR-1K |
| Cents error median / 95th pct | ≤ 10 / ≤ 50 | vocadito |
| Voicing false alarm | report; aim ≤ 0.10 | MIR-1K |

## 6. Speed and caching

- Python prototype: no speed target. C++ (Phase 2): at least 10× faster than real time on the Windows PC (a 3-minute vocal in ≤ 18 s).
- Runs once at capture time on a background thread, never the audio thread.
- Results are cached on disk keyed by (hash of the audio, `analysis_version`, settings). Changing the algorithm bumps `analysis_version`, so stale caches are ignored, never trusted.

## 7. Edge cases

| Case | Expected behaviour |
|---|---|
| Silence / no voice | Empty note list, no error |
| Clip shorter than 50 ms | Empty note list |
| Breaths, clicks, consonants | No notes (they're unvoiced or too short) |
| Octave errors (tracker jumps 12 semitones) | Segmenter penalises them; anything left is fixable in note assignment mode (Phase 3) |
| Vocal fry, whisper | Treated as unvoiced unless a pitch is clearly present |
| Clipping, DC offset | Analysed as-is; DC removed before tracking |
| Sample rates 44.1–96 kHz | Same notes (within 1 frame) for the same performance at any rate: tested |

## 8. Interfaces

Python (Phase 1): `clay_research.analysis.analyze(audio, sample_rate, settings) -> AnalysisResult`.
C++ (Phase 2): `clay::analysis::analyze(const AudioView&, const Settings&) -> AnalysisResult`, same fields, with parity tests against Python (tolerances in the roadmap's "Metric definitions").

## 9. Owner decisions (2026-10-10)

1. **Frame rate: 5 ms.** Smoother pitch curves and finer drift/vibrato edits; analysis is offline, so the extra time is acceptable.
2. **Stereo is analysed as mid (L+R)/2.** One set of notes for both channels.
3. **Default pitch range C2–C6** (65–1047 Hz), adjustable per clip; octave errors are fixed in note assignment mode.
4. **Center pitch = amplitude-weighted median of the note's stable middle** (transitions at each end excluded).
