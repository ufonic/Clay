# Datasets

Downloaded datasets live here, one folder per dataset. Everything except this README and `LICENSES.md` is gitignored: **never commit audio.**

## Download

From the repo root:

```
uv run --project research python -m clay_research.datasets.download mir1k vocalset
```

Each download resumes if interrupted, is checked against a published MD5, and is then extracted. A `.complete` marker in the folder means it's installed. After that, the archive (`.rar` / `.zip`) can be deleted to save space.

| Dataset | Size (download) | Folder | Loader |
|---|---|---|---|
| MIR-1K | 0.8 GB | `data/mir1k/` | `clay_research.datasets.mir1k` |
| VocalSet 1.2 | 6.0 GB (only `data_by_singer` is extracted) | `data/vocalset/` | `clay_research.datasets.vocalset` |

Set `CLAY_DATA_DIR` to keep datasets somewhere else (e.g. an external drive).

Later phases add GuitarSet, MAESTRO, GiantSteps, Ballroom, Groove MIDI, and the Freesound Loop Dataset (see `docs/ROADMAP.md`).
