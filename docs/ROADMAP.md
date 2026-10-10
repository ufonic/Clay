# Clay Roadmap

Work in order. Do not start a phase until the previous gate passes and the owner confirms. There is no timeline; the owner works when time allows. Effort sizes are relative (S < M < L < XL), not dates.

**Legend:** 👂 owner listening check · 🖐 owner hands-on (DAW, approval) · 🍎 needs the owner's Mac (batched into a Mac checkpoint) · 🔬 research, outcome uncertain

---

## Mac checkpoints

The owner has an old Mac and would rather not use it. Everything that can run headlessly runs in macOS CI: build (universal), unit and parity tests, pluginval, `auval`, benchmarks. CI uploads ad-hoc-signed builds as artifacts so the owner only downloads and opens them. The Mac is needed only for these four sessions:

| Checkpoint | When | What the owner does | Est. time |
|---|---|---|---|
| **A** | Before Phase 3 starts (moved from the Phase 0 gate) | Load the plugin AU in Logic and VST3 in Live; standalone opens | ~30 min |
| **B** | Phase 3 gate | Tune a lead vocal in Live and Logic; save, reopen, confirm recall | ~1–2 hours |
| **C** | Phase 4 gate | ARA in Logic; Max for Live auto-capture; FL Studio + Bitwig load and recall | ~2 hours |
| **D** | Phase 7 gate | 16-track session opens and plays; batch export runs | ~1 hour |

Before each checkpoint Claude writes `docs/mac-checkpoint-<X>.md`: download links, install steps, and a tick-box list, so a session is follow-the-list.

**The owner's Mac: 2017 MacBook Pro (Intel).**
- **macOS ceiling is 13 Ventura.** Set `CMAKE_OSX_DEPLOYMENT_TARGET` to `13.0` (lower it if `sw_vers` on the Mac shows 12). Before adding any dependency, check that its minimum macOS is ≤ 13 (watch ONNX Runtime and PyTorch-exported models in Phase 2+).
- **Logic Pro 10.8.x is the newest that runs on Ventura** (Logic 11 needs macOS 14.4). ARA and plugin testing target 10.8. Check that Live 12, FL Studio, and Bitwig versions in use still support Ventura at each checkpoint.
- **ARA runs natively on Intel**, so checkpoint C tests native ARA. The Apple Silicon + Rosetta ARA path stays untested — a known gap, accepted for personal use until an Apple Silicon Mac is available.
- **The Intel slice of the universal binary is tested in CI under Rosetta** (GitHub's macOS runners are Apple Silicon; verified working 2026-10-10). Intel-only bugs should show up in CI, not at the Mac checkpoints.
- **Performance gates are measured on the Windows PC.** On the Mac, "smooth enough to use" is the bar.

---

## Metric definitions

Every gate below uses these definitions. Change them only with owner approval, and log the change in `docs/decisions.md`.

| Metric | Definition | Tool |
|---|---|---|
| **Note F1** | Onset-only note F-measure: onset tolerance 50 ms, pitch tolerance 50 cents, offsets ignored (`offset_ratio=None`). Also report F1 with offsets (offset ratio 0.2) for information. On vocadito, scored against **each** annotator; `note_f1_mean` = mean of the two. | `mir_eval.transcription.precision_recall_f1_overlap` |
| **Raw pitch accuracy (RPA)** | Share of voiced reference frames whose estimate is within 50 cents. | `mir_eval.melody.raw_pitch_accuracy` |
| **Voicing** | Voicing recall and false-alarm rate. | `mir_eval.melody.voicing_measures` |
| **Cents error** | Median and 95th-percentile absolute error, in cents, over frames voiced in both reference and estimate. | harness |
| **Analysis parity** (C++ vs Python) | Same frames: voicing agrees on ≥ 99.5% of frames; F0 median diff ≤ 1 cent, max ≤ 5 cents on voiced frames; note boundaries within ±1 frame; note pitches within 1 cent. | parity test |
| **Render parity** (C++ vs Python) | Null test: RMS of (C++ − Python) at least 60 dB below the RMS of the Python render, per clip; no single 50 ms window worse than 40 dB. | parity test |
| **Render speed** | Offline render time ÷ audio duration, Release build, one thread, 48 kHz stereo, on the owner's Windows machine. | benchmark |
| **Tempo accuracy** (Phase 5) | Share of clips where \|estimate − label\| ≤ 1 BPM (strict; double/half tempo counts as wrong). Also report Accuracy1 (±4%) and Accuracy2 (±4% allowing ×2, ×3, ×½, ×⅓) for comparison with published results. | harness |
| **Key accuracy** (Phase 5) | Exact match (tonic + major/minor) rate. Also report the MIREX weighted score (fifths, relative, parallel errors get partial credit). | `mir_eval.key.evaluate` |
| **Transition error** (Phase 3+) | After snapping every note to its nearest semitone, median cents error of note centers ≤ 3 cents vs. target. | harness |

Datasets per metric: **vocadito** (Note F1; 40 solo vocals, two annotators, CC BY 4.0), MIR-1K and vocadito (RPA, voicing, cents error), VocalSet (listening material), owner's labeled takes (optional extra Note F1 check), GuitarSet and MAESTRO (Phase 5–6 Note F1), Phase 5 test sets below (tempo, key).

---

## Feature inventory

LLM fit: **High** = Claude can build and verify it end to end. **Medium** = Claude builds it, the owner tunes it by ear. **Low** = research or sparse documentation; work closely with the owner. IDs are stable labels, not an order.

| # | Feature | Tier | Fit | Phase |
|---|---|---|---|---|
| 1 | Monophonic pitch detection (F0 tracking) | Essential | Medium | 1–2 |
| 2 | Note segmentation into blobs | Essential | Medium | 1–2 |
| 6 | Monophonic resynthesis (pitch shift, time stretch) | Essential | Medium | 1–2 |
| 37 | Stereo, 44.1–96 kHz, latency reporting | Essential | High | 2 |
| 3 | Blob editor: drag pitch and time, piano-roll grid | Essential | High | 3 |
| 4 | Pitch correction macro (center + drift amount) | Essential | High | 3 |
| 5 | Timing correction: move, stretch, quantize to grid | Essential | Medium | 3 |
| 7 | Undo/redo, A/B compare, bypass | Essential | High | 3 |
| 8 | Plugin shell with Transfer capture | Essential | High | 3 |
| 9 | Standalone app with file import/export | Essential | High | 3 |
| 35 | Note assignment mode: fix octave errors, missed notes, wrong splits | Essential | Medium | 3 |
| 36 | Project save and recall in each DAW; analysis cache on disk | Essential | High | 3 |
| 10 | Pitch drift and vibrato editing | Assistant | Medium | 4 |
| 11 | Pitch transitions between notes | Assistant | Medium | 4 |
| 12 | Formant shift independent of pitch | Assistant | Medium | 4 |
| 13 | Note amplitude editing | Assistant | High | 4 |
| 14 | Sibilance detection and level control | Assistant | Medium | 4 |
| 15 | Note separation: split, join, attack/release | Assistant | High | 4 |
| 16 | Timing macro; quantize to MIDI or other audio | Assistant | Medium | 4 |
| 17 | Snap to scale | Assistant | High | 4 |
| 18 | Monophonic audio-to-MIDI export | Assistant | High | 4 |
| 19 | ARA 2 integration (Logic Pro, under Rosetta) | Assistant | Low | 4 |
| 20 | Live workflow: Max for Live companion and auto-capture | Assistant | Medium | 4 |
| 38 | Live 12 global key/scale sync via Max for Live | Assistant | Medium | 4 |
| 39 | Keyboard shortcuts; MIDI keyboard input to set note pitch | Assistant | High | 4 |
| 21 | Detection modes: melodic, percussive, universal | Editor | Medium | 5 |
| 22 | Percussive and universal resynthesis | Editor | Medium | 5 |
| 23 | Tempo detection and tempo map editing | Editor | Medium | 5 |
| 24 | Key and scale detection | Editor | High | 5 |
| 25 | Scale editing, custom tunings, reference pitch | Editor | High | 5 |
| 29 | Polyphonic audio-to-MIDI export (Basic Pitch) | Editor | High | 5 |
| 26 | Polyphonic note detection (DNA-equivalent) | Editor | Low | 6 |
| 27 | Polyphonic per-note editing and resynthesis | Editor | Low | 6 |
| 28 | Chord re-voicing of samples | Editor | Low | 6 |
| 30 | Multitrack editing in one window | Studio | Medium | 7 |
| 31 | Cross-track reference (lead vs doubles) | Studio | High | 7 |
| 32 | Sound Editor: overtone/timbre reshaping | Studio | Medium | 7 |
| 33 | Unlimited instances, session management | Studio | High | 7 |
| 34 | Batch processing and export | Studio | High | 7 |

---

## Phase overview

```
P0 Foundation (S) ─> P1 Python prototype (M) ─> P2 C++ port (M) ─> P3 Plugin + editor (M)
   ─> P4 Assistant + DAW integration (L) ─> P5 Editor tier mono/percussive (M)
   ─> P6 Polyphonic research (XL, 🔬, may stop) ─> P7 Studio tier (M)
```

The first usable tool arrives at the end of **Phase 3** (tune a lead vocal in Live and Logic). Phases 4–7 add features on a working product. Phase 6 is the only phase that may fail; Phase 7 does not depend on it.

---

## Phase 0 · Foundation (S)

Goal: everything needed to measure, build, and load a plugin, before any real DSP.

| # | Task | Verified by |
|---|---|---|
| 0.1 | `git init`, GitHub repo, `.gitignore`, `.clang-format`, ruff config, `docs/decisions.md` | CI lint job |
| 0.2 | Pin JUCE 9, ARA SDK, clap-juce-extensions, Catch2 as submodules | CI checkout + build |
| 0.3 | CMake skeleton + presets; GitHub Actions on macOS (universal) and Windows | green CI |
| 0.4 | `/research` uv project; download scripts + loaders for MIR-1K, VocalSet (GuitarSet, MAESTRO later) | pytest on loaders (small fixture clips) |
| 0.5 | Scoring harness: all metrics above, one command, Markdown + JSON report | pytest with known-answer fixtures |
| 0.6 | Labeling script (load take, show pYIN guess, owner corrects notes, save labels) | tests + Chrome check; owner labeling optional (gate uses vocadito) |
| 0.7 | Pass-through plugin (VST3, AU, CLAP, standalone), latency = 0, pluginval in CI | pluginval ≥ 5 + clap-validator + auval in CI; 🖐 Live (Windows), 🍎 Logic + Live (Mac). FL Studio + Bitwig hands-on moved to the Phase 4 gate |
| 0.8 | Transfer spike in Live: capture clip to buffer, play back in sync incl. tempo change and warped clip | 🖐 owner, in Live |
| 0.9 | Real-time lint (flags allocation, locks, I/O, logging in audio callbacks) + stress test | lint catches seeded violations |
| 0.10 | UI mockups: blob view, toolbar, inspector, note assignment mode, multitrack | 🖐 owner approves |
| 0.11 | `docs/analysis/SPEC.md` | owner confirms |

**Gate:** one command scores a reference vocal end to end; the pass-through plugin loads in Live on Windows (FL Studio, Bitwig: validators now, hands-on at the Phase 4 gate; Logic + Live on Mac: 🍎 checkpoint A before Phase 3); the owner approves the mockups.

---

## Phase 1 · Python prototype (M)

Goal: prove analysis and monophonic resynthesis sound good, in Python, before writing C++.

| # | Task | Verified by |
|---|---|---|
| 1.1 | pYIN baseline F0 tracker → harness baseline scores | harness report |
| 1.2 | CREPE and FCPE trackers; pick one with the owner (log in decisions.md) | harness comparison + 👂 |
| 1.3 | HMM note segmenter (pitch + energy + voicing) | Note F1 |
| 1.4 | Note model data structure + JSON serialization (shared schema for C++) | round-trip tests |
| 1.5 | WORLD-based pitch shift and formant preservation from the note model | unit tests + 👂 |
| 1.6 | Time stretch per note (Rubber Band or Signalsmith; pick with owner) | unit tests + 👂 |
| 1.7 | Render scripts: ±1, ±2 semitone and ±10% time versions of every clip | renders exist |

**Gate:**
- Note F1 (`note_f1_mean`) ≥ **0.740 on vocadito**: as good as a second human (the two annotators agree at 0.740). Baseline 0.556.
- RPA ≥ 0.95 on MIR-1K (baseline 0.964); cents error median ≤ 10, 95th percentile ≤ 50 on vocadito (baseline 8.5 / 57.8).
- 👂 Owner hears no objectionable artifacts at ±2 semitones on 5 vocals (public: VocalSet / vocadito; the owner's own takes if available).

---

## Phase 2 · C++ engine port (M)

Goal: the approved Python algorithms, real-time-safe in C++, matching Python.

| # | Task | Verified by |
|---|---|---|
| 2.1 | Engine library skeleton, note model in C++ reading the Phase 1 JSON schema | round-trip vs Python |
| 2.2 | Port the F0 tracker (ONNX Runtime if neural) | analysis parity |
| 2.3 | Port the segmenter | analysis parity |
| 2.4 | Port resynthesis + time stretch | render parity |
| 2.5 | Stereo handling and 44.1/48/88.2/96 kHz on every module | parameterized tests |
| 2.6 | Analysis cache on disk (versioned format) | invalidation tests |
| 2.7 | Benchmarks in CI (track, don't gate, on CI runners) | benchmark report |

**Gate:** analysis and render parity pass on every clip; render speed ≥ 10× real time; real-time lint passes; 👂 owner spot-checks 3 C++ renders against Python.

---

## Phase 3 · Plugin and editor, Essential-equivalent (M)

Goal: the first usable tool. Features 3–9, 35, 36.

| # | Task | Verified by |
|---|---|---|
| 3.1 | Engine inside the plugin; Transfer capture → analysis → playback | integration test + 🖐 |
| 3.2 | Piano-roll canvas: grid, blobs, pitch curve, zoom/scroll | UI snapshot tests + 🖐 |
| 3.3 | Pitch tool (drag blob), time tool (move/stretch), quantize to grid | model tests |
| 3.4 | Pitch correction macro (center + drift amount) | Transition error ≤ 3 cents |
| 3.5 | Note assignment mode (fix octave errors, add/remove/split notes) | model tests + 🖐 |
| 3.6 | Undo/redo (command pattern over the note model), A/B, bypass | model tests |
| 3.7 | State save/recall in host project + sidecar | reload tests; 🖐 in each host |
| 3.8 | Standalone: import/export WAV/AIFF/FLAC | round-trip tests |
| 3.9 | Correct latency reporting | host delay-compensation test 🖐 |

**Gate:** 🖐 the owner tunes a 3-minute lead vocal in under 15 minutes in Live on Windows, then repeats it in Live and Logic at 🍎 Mac checkpoint B; pluginval passes at strictness ≥ 5 on all formats.

---

## Phase 4 · Assistant features and DAW integration (L)

| # | Task | Verified by |
|---|---|---|
| 4.1 | Pitch drift + vibrato editing, transitions between notes (10, 11) | model tests + 👂 |
| 4.2 | Formant shift independent of pitch (12) | 👂 ±3 st |
| 4.3 | Amplitude editing; split/join/attack/release (13, 15) | model tests |
| 4.4 | Sibilance detection + level (14) | labeled sibilant frames + 👂 |
| 4.5 | Timing macro; quantize to MIDI or other audio (16) | alignment tests |
| 4.6 | Snap to scale; mono MIDI export (17, 18) | tests vs labels |
| 4.7 | Keyboard shortcuts; MIDI keyboard sets note pitch (39) | tests + 🖐 |
| 4.8 | ARA 2 via JUCE ARA in Logic 10.8, native on the Intel Mac (19) | 🔬 🍎 Logic (checkpoint C) |
| 4.9 | Max for Live device: auto-send clips over OSC, sync Live 12 global key/scale (20, 38) | 🖐 Live |

**Gate:** 👂 ±3 semitone formant shifts sound natural; 🍎 ARA works in Logic 10.8 on the Intel Mac (checkpoint C); 🖐 a Live clip tunes without pressing Transfer; 🖐 plugin loads, passes audio, and recalls state in FL Studio and Bitwig (VST3 and CLAP, Windows; deferred here from Phase 0).

---

## Phase 5 · Editor tier, mono and percussive (M)

### Phase 5 test sets

All are free to download for research and personal use. Claude writes the download scripts in `/data` (using mirdata where it has a loader) and records each license in `/data/LICENSES.md`. Do not commit audio.

| Set | What it is | Labels | Role |
|---|---|---|---|
| [Freesound Loop Dataset (FSLD)](https://zenodo.org/records/3967852) | 9,455 loops from Freesound; ~3,000 human-annotated | Tempo, key, instrument, genre | **Gate (tempo):** loops annotated as drums/percussion with human-checked tempo. **Gate (key):** melodic/harmonic loops with human-checked key, excluding ones marked as having no key. |
| [Groove MIDI Dataset](https://magenta.tensorflow.org/datasets/groove) (GMD) | Real drummers on an electronic kit, MIDI + audio, CC BY 4.0 | Exact tempo from the MIDI | **Gate (tempo):** "beat" segments cut into 4-bar loops at bar lines. The tempo is exact, so this checks the labels as well as the detector. |
| [E-GMD](https://magenta.tensorflow.org/datasets/e-gmd) | GMD re-recorded through 43 drum kits (444 hours) | Exact tempo from the MIDI | Optional robustness set (different kit sounds). Very large: download a subset only. |
| [GiantSteps Tempo](https://github.com/GiantSteps/giantsteps-tempo-dataset) | 664 two-minute EDM previews; audio fetched from Beatport by the repo's script | Human-corrected tempo | **Report only:** full tracks, not loops. Skip the 3 files with tempo 0. |
| [GiantSteps Key](https://github.com/GiantSteps/giantsteps-key-dataset) | ~600 two-minute EDM previews | Human-corrected key | **Report only:** published key detectors score well under 85% exact on this set, so it is context, not a gate. |
| [Ballroom](https://mtg.upf.edu/ismir2004/contest/tempoContest/node5.html) | 698 thirty-second dance excerpts | Tempo | **Report only:** a classic tempo benchmark, for comparison with papers. Use mirdata if the MTG links are dead. |

Before 5.3/5.4 start: download the sets, run a library baseline (Claude proposes the libraries; the owner approves any new dependency), and show the owner the baseline scores. If a baseline is already far from the gate, raise it before building.

| # | Task | Verified by |
|---|---|---|
| 5.0 | Download scripts + loaders for the Phase 5 test sets; baseline scores | harness report |
| 5.1 | Detection modes: melodic, percussive, universal (21) | per-mode harness |
| 5.2 | Phase-vocoder resynthesis for percussive/universal (22) | 👂 |
| 5.3 | Tempo detection + tempo map editing (23) | BPM accuracy |
| 5.4 | Key and scale detection (24) | label match |
| 5.5 | Scale editing, custom tunings, reference pitch (25) | unit tests |
| 5.6 | Polyphonic MIDI export via Basic Pitch (29) | Note F1 on GuitarSet/MAESTRO (report, not gate) |
| 5.7 | Research spike on polyphonic separation → written report to owner | 🔬 owner reads |

**Gate:**
- Tempo accuracy (±1 BPM, strict) ≥ 90% on the FSLD drum loops and ≥ 90% on the GMD loops.
- Key accuracy (exact match) ≥ 85% on the FSLD key-annotated loops.
- GiantSteps, Ballroom, and E-GMD scores are reported but do not gate.

---

## Phase 6 · Polyphonic research, DNA-equivalent (XL) 🔬

Research. Implement papers, run PyTorch experiments on GuitarSet and MAESTRO, sweep parameters, and summarize results after each experiment. Claude cannot judge whether separation sounds usable, so always render audio and ask.

| # | Task | Verified by |
|---|---|---|
| 6.1 | Literature survey + experiment plan | owner approves plan |
| 6.2 | Polyphonic note detection (26) | Note F1 on GuitarSet/MAESTRO |
| 6.3 | Harmonic separation + per-note resynthesis (27) | 👂 |
| 6.4 | Chord re-voicing (28) | 👂 |

**Gate:** 👂 a single string in a strummed chord moves one semitone, and the owner judges it acceptable. If it misses, the owner decides whether to continue or move to Phase 7.

---

## Phase 7 · Studio tier (M)

| # | Task | Verified by |
|---|---|---|
| 7.1 | Multitrack view in one window (30) | 🖐 |
| 7.2 | Cross-track reference, lead vs doubles (31) | tests |
| 7.3 | Sound Editor: overtone/timbre reshaping (32) | 👂 |
| 7.4 | Unlimited instances + session management (33) | stress test |
| 7.5 | Batch processing and export (34) | speed benchmark |

**Gate:** 🖐 16 tracks edit smoothly in one window on the Windows PC (≥ 60 fps scroll/zoom, no audio dropouts); a full session batch-exports faster than real time; 🍎 the same session opens and plays at Mac checkpoint D.

---

## Open questions for the owner

1. **Mac software:** confirm the installed macOS (`sw_vers`) and Logic version before checkpoint A.
2. **Time-stretch library:** Rubber Band (GPL, very mature) vs Signalsmith Stretch (MIT, simpler). Decide in task 1.6 by ear.
3. **UI naming:** our own names for blobs, Transfer, etc. — decide with the mockups (0.10).
