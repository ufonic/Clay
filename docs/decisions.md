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
