# Baselines

Committed scoring reports that new work is compared against (CLAUDE.md "Definition of done": harness scores no worse than baseline).

| File | What | Date |
|---|---|---|
| `mir1k_pyin.json` | librosa pYIN, 10 ms hop, 65–1047 Hz, all 1,000 MIR-1K clips (voice channel) | 2026-10-10 |

Compare a new run: `uv run --project research python -m clay_research.harness.score --dataset mir1k --baseline research/baselines/mir1k_pyin.json`. It exits non-zero if any metric is more than 0.5% worse.

Replace a baseline only when the owner approves a new default (log it in `docs/decisions.md`).
