# Decisions log

One entry per significant decision, newest first. Format:

```
## YYYY-MM-DD · <decision>
- **Decision:** what we chose
- **Alternatives:** what else we considered
- **Why:** the reason, in plain language
- **Revisit if:** what would make us change it
```

---

## 2026-10-11 · ONNX Runtime 1.23.2 for FCPE in C++
- **Decision:** run FCPE's network in C++ with **ONNX Runtime 1.23.2** prebuilt binaries (win-x64, osx-universal2; SHA-256 pinned). Python research is pinned to the same version. The model (`engine/models/fcpe_c_v001.onnx`, 43 MB, MIT) is committed. Mel spectrogram, resampling, and the pitch decoder are ported by hand and parity-tested.
- **Alternatives:** ONNX Runtime 1.24–1.31 (no Intel Mac builds: Apple Silicon only since 1.24); building ONNX Runtime from source for x86_64 (much slower CI); hand-writing the network in C++ (rule 4: prefer libraries).
- **Why:** 1.23.2 is the newest release with a universal macOS build, and the owner's Mac is Intel. Opset 17 is well within its support. A year-old stable release is fine for offline analysis.
- **Revisit if:** Clay stops needing Intel Macs, or a needed fix lands only in newer ONNX Runtime (then build x86_64 from source or drop Intel).

## 2026-10-11 · C++ dependencies for Phase 2: nlohmann/json, WORLD
- **Decision:** add **nlohmann/json v3.12.0** (MIT, header-only, submodule `third_party/nlohmann_json`) for reading/writing note model files in the engine. **WORLD** (modified BSD) is approved by the owner for the C++ resynthesis port (task 2.4), pinned to the commit pyworld 0.3.5 builds from so render parity can reach −60 dB.
- **Alternatives:** JUCE's `juce::JSON` (would pull juce_core into the JUCE-free engine and risk duplicate-symbol clashes with the plugin); a hand-written parser (CLAUDE.md rule 4: prefer libraries).
- **Why:** de-facto standard, tiny, keeps the engine independent of JUCE. The owner delegated library choices ("do whatever you think is best"); flagged in the Phase 2 summary.
- **Revisit if:** the owner objects, or file size/parse speed matters (binary format in 2.6's cache).

## 2026-10-11 · Rubber Band for time stretch; Phase 1 complete
- **Decision:** Clay stretches time with **Rubber Band R3** (GPLv2; fine for personal use). Owner accepted it at ±10% on 5 vocals; occasional small pops = minor. Phase 1 gate passed: note F1 0.707 ≥ 0.70, MIR-1K RPA 0.988, vocadito cents error median 3.6 / p95 24.6, ±2 st accepted.
- **Alternatives:** blind test vs Signalsmith Stretch (close second) and WORLD frame resampling (phasey).
- **Why:** best by ear; also has formant-preserving pitch shift if WORLD's phasiness ever needs a fallback (owner found it comparable, better on female vocals).
- **Revisit if:** the pops become audible in real edits (no clipping or sample jumps found; likely consonants/mouth clicks made more noticeable), or Signalsmith gains features we need (MIT would matter only if Clay were ever distributed).

## 2026-10-11 · Keep WORLD for pitch; Phase 1 pitch listening gate passed
- **Decision:** WORLD stays Clay's pitch engine. Owner accepted WORLD at ±2 st on 5 vocals: the slight phasiness on held notes is "minor".
- **Alternatives:** blind test vs Rubber Band R3 (owner: comparable; better on female vocals, WORLD better on male), PSOLA ("fuzzy"), Signalsmith without formants ("tinny").
- **Why:** sound was close, and WORLD fits the note model: exact per-frame pitch for per-note edits and drift flattening, separate formant control, small C++ library to port.
- **Revisit if:** phasiness bothers the owner in real editing. First try WORLD-side improvements (envelope resolution, aperiodicity tuning for high voices), then a per-voice option using Rubber Band for female vocals.

## 2026-10-11 · Rendering: original audio between notes; pitch-shifter comparison
- **Decision:** the renderer rebuilds only the notes; breaths and noise between notes stay the original recording (20 ms crossfade). A high-pass below the singer's lowest note removes WORLD's sub-bass. For the comparison with WORLD, research adds three pitch-shift libraries: pylibrb 0.1.2 (Rubber Band, GPLv2), praat-parselmouth 0.4.7 (PSOLA, GPLv3), python-stretch 0.3.1 (Signalsmith Stretch, MIT; this binding lacks formant preservation).
- **Alternatives:** a breath gate on the pitch track (zero-crossing rate + pitch stability) and WORLD's StoneMask pitch refinement. Both tried and removed: the gate unvoiced whole sung notes, StoneMask wandered up to 3 st inside held notes, and the owner heard glitches on long notes.
- **Why:** owner heard a phaser/warble on inhales in every WORLD render (WORLD makes even the noise of a "voiced" frame pitched), plus sub-bass. The splice fixed the inhales by ear. Shifted notes still sound "a little phasey" (WORLD's own sound), so the owner compares methods blind (`python -m clay_research.render.shift_compare`). The owner delegated library choice for comparisons.
- **Revisit if:** the owner picks a non-WORLD method (then decide how per-note edits, drift and formant shift map onto it), or Phase 2 needs a C++ port of the winner.

## 2026-10-10 · FCPE tracker; note gate ≥ 0.70 with a known gap to human level
- **Decision:** Clay uses **FCPE** for pitch tracking. The Phase 1 note gate is note F1 ≥ 0.70 on vocadito (was ≥ 0.740 = human agreement); the HMM segmenter scores 0.707 (2-fold cross-validated 0.709).
- **Alternatives:** pYIN (MIR-1K RPA 0.964, false alarm 0.32), CREPE full (no better, ~180× slower on CPU); for notes, keep working until 0.740.
- **Why:** FCPE is best on every pitch metric (MIR-1K RPA 0.988, false alarm 0.145, cents p95 23) at pYIN's speed, and exports to ONNX for C++. Notes: pitch on matched notes is human-level (13% vs 14% off by > 50 cents); the remaining gap is note boundaries (paired bootstrap: −0.033, 95% CI [−0.060, −0.006], so real but small). Parameter tuning saturated (held-out = defaults); loudness-rise and pitch-motion evidence added +0.002. Owner chose to move on and revisit.
- **Revisit if:** blob splits feel wrong in Phase 3 editing, or before Phase 2 ports the segmenter (try a learned onset detector).

## 2026-10-10 · Note gate on public data (vocadito); Mac checkpoint A moved before Phase 3
- **Decision:** the Phase 1 note-detection gate uses vocadito (40 solo vocals, two annotators) instead of the owner's labeled takes. Target: mean note F1 vs each annotator ≥ 0.740, which is how well the two annotators agree with each other. Mac checkpoint A (Logic + Live load) moves from the Phase 0 gate to just before Phase 3.
- **Alternatives:** owner labels 5 takes (original plan); targets of 0.70 or 0.80; combining checkpoint A with B.
- **Why:** owner's request. Measured: two expert annotators agree at only 0.740 under the gate rules (1 of 40 tracks reaches 0.90), so the original 0.95 target was impossible against human labels; "as good as a second human" is a meaningful, reachable bar (baseline 0.556). Phases 1–2 have no Mac-specific risk, and CI validates AU/VST3/CLAP on macOS (incl. Intel) on every run.
- **Revisit if:** Clay's notes score well but sound wrong to the owner (the annotators' conventions may differ from the owner's), or a macOS host bug appears that CI misses.

## 2026-10-10 · FL Studio and Bitwig hands-on checks moved to Phase 4
- **Decision:** Phase 0 no longer needs the owner to test FL Studio or Bitwig. They're covered by CI validators (pluginval for VST3, clap-validator for CLAP) until the Phase 4 gate, which already requires load + state recall in both. Mac checkpoint A shrinks to Logic + Live.
- **Alternatives:** test all four hosts now (original plan).
- **Why:** owner's request; Live (the primary host) and Transfer are already verified hands-on, and the validators exercise the same plugin-format code those hosts use.
- **Revisit if:** a host-specific bug turns up in Live or Logic that the validators missed (then bring the FL/Bitwig check forward).

## 2026-10-10 · Transfer verified in Live 12
- **Decision:** the Phase 0 Transfer approach (capture indexed by host timeline sample, played back at the playhead) is confirmed in Live 12 on Windows: null test −80 to −85 dB, holding with Warp on, after a tempo change, and while looping. Live keeps Transfer as its path until the Max for Live bridge in Phase 4.
- **Alternatives:** none needed; this was the spike's open risk.
- **Why:** the residual isn't zero because Live's playback isn't bit-identical between passes; a one-sample offset would read about −40 dB or worse, so sync is sample-exact. "In sync" threshold set to −70 dB.
- **Revisit if:** another host or Live version reads above −70 dB.

## 2026-10-10 · Editor mockups and analysis spec approved
- **Decision:** owner approved the editor mockups (https://claude.ai/artifact/77BtemqUgsYvpv3hHK1REY: editor, note assignment mode, multitrack) and the analysis SPEC with all four proposed defaults: 5 ms frames, stereo as mid, C2–C6 default range, center pitch = amplitude-weighted median of the stable middle.
- **Alternatives:** 10 ms frames; per-side stereo analysis; narrower or auto-detected range; whole-note average or settle-point center pitch.
- **Why:** see `docs/analysis/SPEC.md` § 9. The mockups are the reference for Phase 3 UI work; layout or interaction choices they don't cover still go to the owner.
- **Revisit if:** Phase 1 listening shows the center-pitch rule pulls notes the wrong way, or 5 ms analysis is too slow in C++.

## 2026-10-10 · JUCE 9 instead of JUCE 8
- **Decision:** pin JUCE 9.0.3 (the plan said JUCE 8). Pin clap-juce-extensions to `main` commit `7adee3a`, which has JUCE 9 support.
- **Alternatives:** JUCE 8.0.15 (last JUCE 8 release).
- **Why:** JUCE 9 is current and will keep getting fixes; starting on it avoids a migration later. Its breaking changes (SVG/Drawable rework, Windows multi-touch off by default) don't affect code we haven't written yet. Runtime minimum is still macOS 10.11, so the 2017 MacBook Pro is fine. JUCE 9.0.3 has no native CLAP, so clap-juce-extensions is still needed.
- **Revisit if:** clap-juce-extensions breaks on JUCE 9, or the owner prefers the plan's JUCE 8 (switching back is a one-line submodule change now, harder after Phase 3).

## 2026-10-10 · Mac testing on the owner's 2017 Intel MacBook Pro
- **Decision:** macOS is verified by CI plus four batched "Mac checkpoints" (end of Phases 0, 3, 4, 7) on a 2017 Intel MacBook Pro. Deployment target macOS 13.0; Logic Pro 10.8.x; native ARA on Intel.
- **Alternatives:** buy/borrow an Apple Silicon Mac; CI-only macOS.
- **Why:** the owner has this Mac and prefers to use it rarely. CI covers build, tests, and plugin validation.
- **Revisit if:** an Apple Silicon Mac becomes available (then test Logic ARA under Rosetta), or Intel-only bugs start costing more than a Mac would.

## 2026-10-10 · Phase 5 tempo/key test sets
- **Decision:** gate on Freesound Loop Dataset (tempo + key) and Groove MIDI Dataset loops (tempo); report GiantSteps, Ballroom, E-GMD without gating.
- **Alternatives:** gate on GiantSteps Key (published detectors score well under the 85% target there).
- **Why:** loops match how the owner will use tempo/key detection, and GMD tempo is exact from MIDI.
- **Revisit if:** library baselines in task 5.0 are far from the gates.

## 2026-10-10 · Project name, tooling
- **Decision:** the project is named **Clay**. Windows toolchain: MSVC 14.50 (Visual Studio 2026 Build Tools), CMake + Ninja, uv-managed Python 3.12, clang-format, ruff. Private GitHub repo `Clay`.
- **Why:** owner's choice (name, repo); tooling per CLAUDE.md § 4.
