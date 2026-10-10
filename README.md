# Clay

A personal note-based audio editor: it detects the notes in recorded audio, shows them as editable blobs on a piano roll, and re-renders the audio after edits to pitch, timing, formants, amplitude, and sibilance. Standalone app plus VST3, AU, and CLAP plugins for macOS and Windows.

Personal use only.

- Project instructions: [`CLAUDE.md`](CLAUDE.md)
- Plan and gates: [`docs/ROADMAP.md`](docs/ROADMAP.md)
- Decisions log: [`docs/decisions.md`](docs/decisions.md)

## Status

Phase 0 · Foundation.

## Build (Windows)

```
git clone --recurse-submodules https://github.com/ufonic/Clay.git
cd Clay
tools\msvc.cmd cmake --preset windows-debug
tools\msvc.cmd cmake --build --preset windows-debug
tools\msvc.cmd ctest --preset windows-debug
```

Needs Visual Studio 2022+ Build Tools (C++ workload), CMake ≥ 3.25, and Ninja. macOS builds run in CI.
