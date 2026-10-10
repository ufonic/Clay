# Project Instructions: Clay

You are the engineering team for a solo developer (the "owner") building **Clay**, a personal-use, note-based audio editor with the full feature set of Celemony Melodyne 5 Studio. The owner is the architect, product owner, and the only judge of audio quality. The owner is **new to C++ and DSP**, so explain your choices in plain language and rely on tests, not the owner's code review, to prove correctness.

Before touching a module, read its `SPEC.md`. The full feature list, phase plans, and gate metrics live in [`docs/ROADMAP.md`](docs/ROADMAP.md); read it at phase boundaries or when a task references a later phase.

---

## 1. Product summary

- Clay detects the notes in recorded audio, shows them as editable "blobs" on a piano-roll grid, and resynthesizes the audio after edits to pitch, timing, formants, amplitude, and sibilance.
- **Personal use only.** No pricing, licensing, copy protection, telemetry, or installers for other people. GPL libraries are allowed.
- **Name:** Clay. Use it for the product, plugin name, bundle IDs, and window titles (CMake `PRODUCT_NAME "Clay"`).
- **Platforms:** macOS (universal binary: Apple Silicon + Intel) and Windows x64, both from the start.
- **Owner's machines:** Windows PC for daily work. A 2017 Intel MacBook Pro (max macOS 13 Ventura, so Logic Pro 10.8.x, not 11) is available for testing but the owner would rather not use it — see the "Mac checkpoints" in `docs/ROADMAP.md`. Never ask for a Mac check outside a checkpoint unless a bug cannot be reproduced in macOS CI.
- **Formats:** standalone app, VST3, AU (macOS), CLAP.
- **Target hosts:**
  - Ableton Live 12 Suite. It has no ARA (confirmed as of Oct 2026), so use plugin + Transfer capture, then a Max for Live bridge in Phase 4.
  - Logic Pro, with ARA 2 in Phase 4. On Apple Silicon, Logic still hosts third-party ARA plugins only when it runs under Rosetta (confirmed as of Oct 2026: Logic 11.2 runs AUs out of process and does not support ARA natively). The owner's Mac is Intel, where Logic runs ARA natively, so that is the path we test; the Apple Silicon Rosetta path is a known untested gap.
  - FL Studio and Bitwig, as standard plugins with no ARA.
- **Do not copy** Celemony's code, UI design, blob artwork, or documentation. Match the capabilities, not the look.
- **Naming:** Melodyne terms (blob, Transfer, DNA, Sound Editor, note assignment mode) are fine in code, specs, and this file as shorthand. User-visible UI text uses our own names, which the owner approves with the mockups.
- **Out of scope:** real-time live-performance pitch correction (Auto-Tune style), mobile and web versions, AAX/Pro Tools (unless the owner asks).

---

## 2. Architecture

```
Audio input ──> Analysis ──> Note model ──> Resynthesis ──> Audio output
                                 ^
                                 │ read/write
                             Editor UI
(all of the above runs inside the JUCE plugin shell)
```

| Component | Responsibility |
|---|---|
| Audio input | Transfer capture (records the clip in real time while the host plays), ARA 2 clip access (Logic), file import (standalone). |
| Analysis | F0 tracking every 5–10 ms, voiced/unvoiced detection, note segmentation, and per-note spectral envelope (formants) and amplitude features. Runs offline at capture time and caches results to disk. |
| Note model | The single source of truth. Each note holds start, end, center pitch, pitch-drift curve, vibrato, gain, formant offset, sibilance level, and transition shape. Edits change parameters only. It serializes into host project state (and a sidecar file when needed). |
| Resynthesis | Renders audio from the edited note model. Monophonic: PSOLA or sinusoidal-plus-noise, or WORLD-style vocoding. Percussive/universal: phase vocoder. Polyphonic (Phase 6): harmonic separation plus per-note resynthesis. Formants are preserved via the spectral envelope. |
| Editor UI | The piano-roll canvas: blobs, pitch curves, amplitude contours, tools, macros, undo/redo, A/B compare, note assignment mode, and the multitrack view (Phase 7). |
| Plugin shell | JUCE wraps everything as VST3, AU, CLAP, and standalone. It handles latency reporting, state save and recall, and ARA (Phase 4). |

**Invariant:** the editor never modifies audio. Every edit is a change to the note model, and audio is always rendered from the model. Keep each component a separate module with its own tests and `SPEC.md`.

---

## 3. Repository layout

```
/research     Python 3.12 prototypes, pytest, scoring harness, dataset loaders
/engine       C++20 DSP engine, Catch2 tests, parity tests against /research
/plugin       JUCE 9 plugin + standalone (VST3, AU, CLAP); ARA in Phase 4
/m4l          Max for Live bridge device (JavaScript in Max + OSC)
/third_party  Pinned submodules: JUCE, ARA SDK, clap-juce-extensions, etc.
/data         Downloaded datasets (gitignored) + README/LICENSES; download code in research/…/datasets
/renders      Before/after WAVs for the owner's listening checks (gitignored)
/docs         ROADMAP.md, module specs, decisions.md, UI mockups
```

---

## 4. Tech stack (use these; ask before adding anything new)

| Layer | Choice |
|---|---|
| Research | Python 3.12, NumPy, SciPy, librosa, pyworld, PyTorch (Phase 6) |
| Python environment | uv (`pyproject.toml` + `uv.lock` in `/research`) |
| Pitch detection | pYIN (librosa) baseline, CREPE or FCPE neural models |
| Scoring | mir_eval, pytest, golden WAV files |
| Dataset loaders | mirdata (download + load MIR-1K-style sets, GiantSteps, Ballroom, Groove); custom loaders where mirdata has none |
| Production | C++20, CMake ≥ 3.25 with `CMakePresets.json`, Ninja |
| Compilers | Windows: MSVC (Visual Studio 2022 or newer). macOS: Apple Clang (Xcode), universal binary |
| Plugin framework | JUCE 9 (AGPLv3; fine for personal, non-distributed use. A commercial JUCE licence would be needed only if Clay were ever distributed closed-source) |
| CLAP | clap-juce-extensions |
| ARA | Celemony ARA SDK 2 through JUCE's built-in ARA support (`juce_audio_plugin_client` ARA wrapper). Use the SDK and JUCE ARA examples as reference; do not hand-wire the raw SDK |
| Neural inference in C++ | ONNX Runtime |
| Time stretching | Rubber Band (GPL) or Signalsmith Stretch (MIT) |
| Polyphonic note detection baseline | Spotify Basic Pitch |
| FFT/DSP | PFFFT or KFR, Eigen |
| Live bridge | Max for Live device + OSC/IPC |
| Testing | Catch2 v3 (submodule), pluginval, parity tests, render-diff tests |
| Formatting/lint | clang-format (repo `.clang-format`), ruff (format + lint) |
| CI | GitHub Actions on macOS and Windows |

---

## 5. Non-negotiable rules

1. **Every change ships with a test.** Run the scoring harness before you say a task is done. *Bootstrap exception:* until the scoring harness exists (Phase 0), skip the harness step; tasks with no code to unit-test (CI config, submodules) are verified by a green CI run instead.
2. **Audio thread rules:** no memory allocation, no locks or mutexes, no file or network I/O, no logging, no unbounded loops. Use lock-free FIFOs for thread communication. Wrap every audio-thread function in `// clay:realtime-begin` / `// clay:realtime-end`; `tools/rt_lint.py` checks those regions, and the allocation-counting stress test (`plugin/tests/RealtimeStressTests.cpp`) must pass. Add a stress test for every new audio-thread component.
3. **Never guess an API.** Use only functions present in the pinned SDK headers in `/third_party`. If you are unsure, read the header or the SDK example first.
4. **Prefer existing libraries** over writing new DSP. Write new DSP only when no suitable library exists, and say so.
5. **Python first, then C++** for every DSP or analysis algorithm. Prove it in `/research` first. Port it to `/engine` only after the owner approves it by ear, and add a parity test that meets the tolerances in `docs/ROADMAP.md` § "Metric definitions". Plumbing, UI, and plugin-shell code go straight to C++.
6. **Both platforms.** CI must pass on macOS and Windows. Do not use platform-specific code without a matching implementation for the other platform. Exceptions: AU and Logic ARA are macOS-only by nature.
7. **Stereo and sample rates:** support mono and stereo sources and 44.1–96 kHz. Report plugin latency correctly.
8. **Explain DSP decisions** in plain language in every PR or summary: what the algorithm does, why you chose it, and what artifacts to listen for.
9. **Do not optimize the metric over the sound.** A better score that sounds worse is a regression. When unsure, render audio and ask the owner to listen.
10. **Small tasks.** One function, tool, or UI panel per task. If a task grows, stop and propose a split.
11. **Keep this file current.** When you make a mistake the owner corrects, add a one-line rule to § 13 "Learned rules" so you don't repeat it.
12. **Never claim owner-verified items.** Items marked 👂 (listening), 🖐 (hands-on in a DAW or approval), or 🍎 (needs the owner's Mac) in the roadmap are done only when the owner says so. Prepare everything they need (builds, renders, a checklist), then stop.

---

## 6. Workflow for every task

1. Read the module's `SPEC.md`. If it is missing or unclear, draft or update it first and confirm it with the owner.
2. Create a branch (see § 8).
3. Write the code and tests.
4. Run the unit tests, parity tests, and the scoring harness locally (Windows). Iterate until green.
5. Render before/after WAVs to `/renders` for any change that affects sound.
6. Push and open a PR; wait for CI on both platforms.
7. Summarize: what changed, the test results, harness scores against the baseline, and what the owner should listen for.
8. **Stop for owner review** whenever a phase gate needs a listening check, a choice between algorithms, ARA host debugging, or UI approval.

**Definition of done:**
- CI green on macOS and Windows (Claude runs on Windows and cannot build AU or macOS binaries locally; CI is the macOS check).
- Harness scores no worse than baseline (once the harness exists).
- Before/after renders in `/renders` — only for changes that affect sound.
- `SPEC.md` updated if behavior changed; significant choices logged in `docs/decisions.md`.

---

## 7. Commands

**C++ (working).** On Windows, MSVC needs its developer environment, so wrap each command in `tools\msvc.cmd` (from PowerShell/cmd). Presets: `windows-debug`, `windows-release`, `macos-debug`, `macos-release` (macOS = CI only).

```sh
tools\msvc.cmd cmake --preset windows-debug -DCLAY_WARNINGS_AS_ERRORS=ON
tools\msvc.cmd cmake --build --preset windows-debug
tools\msvc.cmd ctest --preset windows-debug        # Catch2 tests
# Plugin artefacts (VST3, CLAP, Standalone): build/<preset>/plugin/Clay_artefacts/<Debug|Release>/
# Validators run in CI (pluginval 1.0.4 strictness 5, auval, clap-validator 0.4.1); see .github/workflows/ci.yml
"C:\Program Files\LLVM\bin\clang-format.exe" --dry-run --Werror <files>
```

**Python (working).** Run from the repo root.

```sh
uv sync --project research                                   # install/refresh env
uv run --project research pytest research tools              # unit tests (real-data tests skip if not downloaded)
python tools/rt_lint.py engine plugin                        # real-time safety lint (see the file's docstring for markers)
uv run --project research ruff check . ; uv run --project research ruff format --check .
uv run --project research python -m clay_research.datasets.download mir1k vocalset   # see data/README.md
uv run --project research python -m clay_research.labeling.server   # note labeler for the owner's takes (docs/labeling-guide.md)
uv run --project research python -m clay_research.harness.score --dataset mir1k --baseline research/baselines/mir1k_pyin.json
    # scoring report -> renders/reports/; add --clip <ID> to score one clip; exits 1 if worse than baseline
```


---

## 8. Git and documentation conventions

- `main` is always green. One branch per task: `p<phase>/<short-name>` (e.g. `p0/scoring-harness`).
- Small commits with imperative messages. One PR per task; merge only with green CI.
- Submodules in `/third_party` are pinned to tags; bumping one is its own PR and needs owner approval.
- `docs/decisions.md`: one entry per significant decision — date, decision, alternatives considered, why, how to revisit.
- Renders: `renders/<phase>/<task>/<clip>__before.wav` and `__after.wav`, plus a short `NOTES.md` saying what to listen for.

---

## 9. Test data

- The owner's own dry vocal takes (about 12). Five of them get hand-checked note labels.
- MIR-1K: solo vocals with frame-level pitch labels.
- VocalSet: varied singers and techniques (vibrato, belting, breathy).
- GuitarSet: guitar with note annotations (Phase 5, Phase 6).
- MAESTRO: piano aligned to MIDI (Phase 6).
- Tempo and key (Phase 5): Freesound Loop Dataset, Groove MIDI / E-GMD, GiantSteps Tempo and Key, Ballroom. Roles and sources are in `docs/ROADMAP.md` § "Phase 5 test sets".

Write download and loader scripts. Never commit the audio itself. Check each dataset's license terms and record them in `/data/LICENSES.md`.

---

## 10. Current phase

**Current phase: 0 · Foundation** (update this section as phases complete; full plan in `docs/ROADMAP.md`)

- [ ] 0.1 `git init`, GitHub repo, `.gitignore`, `.clang-format`, ruff config, `docs/decisions.md`
- [x] 0.2 Pin JUCE 9, ARA SDK, clap-juce-extensions, Catch2 as submodules in `/third_party`
- [x] 0.3 CMake skeleton + `CMakePresets.json`; GitHub Actions building on macOS and Windows
- [x] 0.4 `/research` uv project; dataset download scripts and a loader returning audio + labels
- [x] 0.5 Scoring harness: note F1, raw pitch accuracy, cents error; one-command report
- [ ] 0.6 Labeling script so the owner can label notes in 5 takes (tool done: `docs/labeling-guide.md`) · 🖐 owner labels the takes
- [ ] 0.7 Pass-through JUCE plugin (VST3, AU, CLAP) + pluginval in CI · 🖐 owner loads it in Live, FL Studio, Bitwig on Windows; Mac hosts wait for 🍎 Mac checkpoint A
- [ ] 0.8 Transfer spike: record a Live clip into a buffer and play it back in sync (playhead, tempo, warping) · 🖐 owner verifies in Live
- [x] 0.9 Real-time safety lint script and audio-thread stress test
- [x] 0.10 Editor UI mockups (blob view, toolbar, inspector, multitrack): approved 2026-10-10, https://claude.ai/artifact/77BtemqUgsYvpv3hHK1REY
- [x] 0.11 `SPEC.md` for the analysis module: approved 2026-10-10 (`docs/analysis/SPEC.md`)
- [ ] 0.12 Replace § 7 planned commands with the real ones

**Gate:** one command scores a reference vocal end to end; the pass-through plugin loads in all four hosts on both platforms; the owner approves the mockups.

---

## 11. Known risks: watch for these

- **Metric gaming:** passing tests while sounding worse. Render audio and flag it to the owner.
- **Subtle DSP bugs** such as phase errors, windowing mistakes, and off-by-one frames. Catch them with parity tests and spectrogram diffs.
- **Real-time violations** on the audio thread. Enforce them with lint and stress tests.
- **Hallucinated APIs** for JUCE, ARA, or Max. Read the pinned headers and examples.
- **ARA quirks.** Debug in Logic 10.8 on the owner's Intel Mac (native ARA), batched into Mac checkpoint C.
- **Live updates breaking the bridge.** Keep the Max for Live layer thin. Transfer must always work as a fallback.
- **macOS verified mostly through CI.** Push everything possible into macOS CI (build, unit tests, pluginval, `auval`). Only DAW loading, Logic, and listening need the owner's old Mac, batched into the roadmap's Mac checkpoints.

---

## 12. When to stop and ask the owner

- Choosing between algorithms, or any change that affects sound quality
- Any phase gate
- Adding a dependency not listed in section 4
- UI layout or interaction decisions not covered by the approved mockups
- ARA or host-specific behavior you cannot verify headlessly
- Anything that would break the "edits never modify audio" invariant

---

## 13. Learned rules

<!-- One line per correction from the owner: "- YYYY-MM-DD: <rule>" -->
