"""Analysis parity on real vocals: C++ FCPE (engine/tools/clay_fcpe) vs Python FCPE.

Usage (from the repo root, after building the engine):
    uv run --project research python -m clay_research.parity.fcpe_dataset vocadito mir1k
    ... --exe build/windows-release/engine/clay_fcpe.exe --limit 50

For every clip: voicing agreement (>= 99.5%), median and max pitch difference on frames
both call voiced (<= 1 and <= 5 cents): docs/ROADMAP.md "Analysis parity". Exits 1 if
any clip fails. Datasets aren't in CI, so this runs locally; CI covers the synthetic
fixtures.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from clay_research.datasets import mir1k, vocadito
from clay_research.datasets.common import REPO_ROOT
from clay_research.harness.trackers import fcpe

from .export_fcpe import ONNX_PATH

DATASETS = {"vocadito": vocadito, "mir1k": mir1k}
VOICING_MIN = 0.995
MEDIAN_CENTS_MAX = 1.0
MAX_CENTS_MAX = 5.0
BATCH = 50  # clips per clay_fcpe call


@dataclass
class Result:
    clip: str
    frames: int
    voicing: float
    median_cents: float
    max_cents: float

    @property
    def passed(self) -> bool:
        return (
            self.voicing >= VOICING_MIN
            and self.median_cents <= MEDIAN_CENTS_MAX
            and self.max_cents <= MAX_CENTS_MAX
        )


def compare(clip: str, python_f0: np.ndarray, cpp_f0: np.ndarray) -> Result:
    if len(python_f0) != len(cpp_f0):
        return Result(clip, len(python_f0), 0.0, np.inf, np.inf)
    a, b = python_f0 > 0, cpp_f0 > 0
    both = a & b
    cents = 1200 * np.abs(np.log2(cpp_f0[both] / python_f0[both])) if both.any() else np.zeros(1)
    return Result(
        clip, len(python_f0), float(np.mean(a == b)), float(np.median(cents)), float(cents.max())
    )


def default_exe() -> Path:
    for preset in ("windows-release", "windows-debug", "macos-release", "macos-debug"):
        for name in ("clay_fcpe.exe", "clay_fcpe"):
            p = REPO_ROOT / "build" / preset / "engine" / name
            if p.exists():
                return p
    raise FileNotFoundError("clay_fcpe not built; build the engine first (CLAUDE.md § 7)")


def run_dataset(name: str, exe: Path, limit: int | None) -> list[Result]:
    module = DATASETS[name]
    ids = module.clip_ids()[:limit]
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        jobs: dict[int, list[tuple[str, np.ndarray, Path, Path]]] = {}
        for cid in ids:
            clip = module.load(cid)
            audio = clip.audio.mean(axis=1) if clip.audio.ndim == 2 else clip.audio
            audio = np.ascontiguousarray(audio, dtype="<f4")
            src, dst = Path(tmp) / f"{name}_{cid}.in.f32", Path(tmp) / f"{name}_{cid}.out.f32"
            audio.tofile(src)
            jobs.setdefault(clip.sample_rate, []).append((cid, audio, src, dst))
        for rate, clips in jobs.items():
            # Batches keep the command line under Windows' 32k-character limit.
            for start in range(0, len(clips), BATCH):
                args = [str(exe), str(ONNX_PATH), str(rate)]
                for _, _, src, dst in clips[start : start + BATCH]:
                    args += [str(src), str(dst)]
                subprocess.run(args, check=True)
            for cid, audio, _, dst in clips:
                cpp = np.fromfile(dst, dtype="<f4")
                results.append(compare(f"{name}/{cid}", fcpe(audio, rate).frequencies_hz, cpp))
    return results


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("datasets", nargs="+", choices=sorted(DATASETS))
    ap.add_argument("--exe", type=Path, default=None)
    ap.add_argument("--limit", type=int, default=None, help="first N clips per dataset")
    args = ap.parse_args(argv)
    exe = args.exe or default_exe()
    failed = 0
    for name in args.datasets:
        results = run_dataset(name, exe, args.limit)
        bad = [r for r in results if not r.passed]
        failed += len(bad)
        worst = max(results, key=lambda r: r.max_cents)
        print(
            f"{name}: {len(results) - len(bad)}/{len(results)} clips pass | "
            f"voicing min {min(r.voicing for r in results):.4f} | "
            f"median cents max {max(r.median_cents for r in results):.4f} | "
            f"max cents {worst.max_cents:.4f} ({worst.clip})"
        )
        for r in bad[:20]:
            print(
                f"  FAIL {r.clip}: voicing {r.voicing:.4f}, "
                f"median {r.median_cents:.3f}, max {r.max_cents:.3f}"
            )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
