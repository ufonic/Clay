# Third-party dependencies

Pinned git submodules. Never edit code in here; bump a pin in its own PR with owner approval (CLAUDE.md § 8).

Clone with: `git clone --recurse-submodules`, or after a plain clone: `git submodule update --init --recursive`.

| Submodule | Pin | License | Used for |
|---|---|---|---|
| `JUCE` | tag `9.0.3` | AGPLv3 / commercial JUCE licence (see `JUCE/LICENSE.md`) | Plugin shell, standalone app, UI, ARA wrapper |
| `ARA_SDK` | tag `releases/2.3.0` (+ nested `ARA_API`, `ARA_Library`, `ARA_Examples`) | Apache 2.0 | ARA 2 for Logic (Phase 4), via JUCE's ARA support |
| `clap-juce-extensions` | commit `7adee3a` on `main` (2026-10-06) | MIT | CLAP format. Pinned to a commit, not a tag: the last tag (`0.26.0`) is from 2022 and predates JUCE 9 support (#178, July 2026) and fixes to latency reporting (#190) and transport (#192) |
| `Catch2` | tag `v3.16.1` | BSL-1.0 | C++ unit tests |

**JUCE licensing note:** JUCE is AGPLv3 unless you buy a commercial licence. Clay is personal use and never distributed, so AGPLv3 is fine. If that ever changes, a commercial JUCE licence may be required; read `JUCE/LICENSE.md` first.
