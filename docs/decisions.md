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
