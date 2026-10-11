# Clay

A personal note-based audio editor: it detects the notes in recorded audio, shows them as editable blobs on a piano roll, and re-renders the audio after edits to pitch, timing, formants, amplitude, and sibilance. Standalone app plus VST3, AU, and CLAP plugins for macOS and Windows.

Built for personal use; no releases, installers, or support.

- Project instructions: [`CLAUDE.md`](CLAUDE.md)
- Plan and gates: [`docs/ROADMAP.md`](docs/ROADMAP.md)
- Decisions log: [`docs/decisions.md`](docs/decisions.md)

## Status

Phase 2 · C++ engine port (Phase 0 foundation and Phase 1 Python prototype complete).

## Build (Windows)

```
git clone --recurse-submodules https://github.com/ufonic/Clay.git
cd Clay
tools\msvc.cmd cmake --preset windows-debug
tools\msvc.cmd cmake --build --preset windows-debug
tools\msvc.cmd ctest --preset windows-debug
```

Needs Visual Studio 2022+ Build Tools (C++ workload), CMake ≥ 3.25, and Ninja. macOS builds run in CI.

## License

Clay is licensed under the [GNU Affero General Public License v3.0](LICENSE) (AGPLv3), matching
[JUCE](https://juce.com)'s open-source licence. Third-party code in `third_party/` and the
bundled FCPE model (`engine/models/`, MIT) keep their own licences. Datasets are not included;
see [`data/LICENSES.md`](data/LICENSES.md).
