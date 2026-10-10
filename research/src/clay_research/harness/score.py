"""One-command scoring: run a tracker over a dataset and write a report.

Usage (from the repo root):
    uv run --project research python -m clay_research.harness.score --dataset mir1k
    uv run --project research python -m clay_research.harness.score --dataset mir1k --clip Ani_1_01
    uv run --project research python -m clay_research.harness.score --dataset mir1k \
        --baseline research/baselines/mir1k_pyin.json

Writes <out>/<dataset>_<tracker>.md and .json (default out: renders/reports/).
With --baseline, the report shows the change against that earlier JSON report and the
command exits non-zero if any gate metric got worse beyond --tolerance.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from clay_research.datasets import mir1k
from clay_research.datasets.common import REPO_ROOT

from .metrics import frame_scores
from .trackers import TRACKERS

DATASETS = {"mir1k": mir1k}

# Summary metrics and which direction is better (+1 higher, -1 lower).
SUMMARY_METRICS = {
    "raw_pitch_accuracy": +1,
    "voicing_recall": +1,
    "voicing_false_alarm": -1,
    "cents_error_median": -1,
    "cents_error_p95": -1,
}


@dataclass(frozen=True)
class Job:
    dataset: str
    tracker: str
    clip_id: str


def score_clip(job: Job) -> dict:
    clip = DATASETS[job.dataset].load(job.clip_id)
    est = TRACKERS[job.tracker](clip.audio, clip.sample_rate)
    return {"clip_id": job.clip_id, **frame_scores(clip.pitch, est).as_dict()}


def summarize(rows: list[dict]) -> dict[str, float]:
    """Mean over clips of each per-clip metric, skipping clips with no value."""
    summary = {}
    for key in SUMMARY_METRICS:
        values = np.array([r[key] for r in rows], dtype=float)
        values = values[np.isfinite(values)]
        summary[key] = float(values.mean()) if values.size else float("nan")
    summary["clips"] = len(rows)
    return summary


def compare(summary: dict, baseline: dict, tolerance: float) -> tuple[list[str], bool]:
    """Lines describing each metric's change, and whether any metric regressed."""
    lines, regressed = [], False
    for key, direction in SUMMARY_METRICS.items():
        new, old = summary.get(key, math.nan), baseline.get(key, math.nan)
        if not (math.isfinite(new) and math.isfinite(old)):
            continue
        delta = new - old
        worse = direction * delta < -tolerance * max(abs(old), 1e-9)
        regressed |= worse
        flag = "  ⚠ worse" if worse else ""
        lines.append(f"| {key} | {old:.4f} | {new:.4f} | {delta:+.4f}{flag} |")
    return lines, regressed


def write_report(
    out: Path, name: str, meta: dict, summary: dict, rows: list[dict], comparison: list[str] | None
) -> tuple[Path, Path]:
    out.mkdir(parents=True, exist_ok=True)
    json_path, md_path = out / f"{name}.json", out / f"{name}.md"
    json_path.write_text(json.dumps({**meta, "summary": summary, "clips": rows}, indent=1))

    worst = sorted(rows, key=lambda r: r["raw_pitch_accuracy"])[:10]
    md = [
        f"# Scoring report: {meta['tracker']} on {meta['dataset']}",
        "",
        f"{summary['clips']} clips · {meta['seconds']:.0f} s · {meta['date']}",
        "",
        "| Metric | Mean over clips |",
        "|---|---|",
        *[f"| {k} | {summary[k]:.4f} |" for k in SUMMARY_METRICS],
    ]
    if comparison is not None:
        md += [
            "",
            "## Against baseline",
            "",
            "| Metric | Baseline | Now | Change |",
            "|---|---|---|---|",
            *comparison,
        ]
    md += [
        "",
        "## Worst 10 clips by raw pitch accuracy",
        "",
        "| Clip | RPA | Voicing recall | False alarm | Median cents |",
        "|---|---|---|---|---|",
    ]
    md += [
        f"| {r['clip_id']} | {r['raw_pitch_accuracy']:.3f} | {r['voicing_recall']:.3f} | "
        f"{r['voicing_false_alarm']:.3f} | {r['cents_error_median']:.1f} |"
        for r in worst
    ]
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Score a pitch tracker on a dataset.")
    p.add_argument("--dataset", choices=sorted(DATASETS), default="mir1k")
    p.add_argument("--tracker", choices=sorted(TRACKERS), default="pyin")
    p.add_argument("--clip", action="append", help="score only these clip IDs (repeatable)")
    p.add_argument("--limit", type=int, help="score only the first N clips")
    p.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    p.add_argument("--out", type=Path, default=REPO_ROOT / "renders" / "reports")
    p.add_argument("--baseline", type=Path, help="earlier JSON report to compare against")
    p.add_argument(
        "--tolerance",
        type=float,
        default=0.005,
        help="relative change allowed before a metric counts as worse",
    )
    args = p.parse_args(argv)

    ids = args.clip or DATASETS[args.dataset].clip_ids()
    if args.limit:
        ids = ids[: args.limit]
    if not ids:
        print(f"No clips found for {args.dataset}; download it first (see data/README.md).")
        return 2

    jobs = [Job(args.dataset, args.tracker, cid) for cid in ids]
    start = time.time()
    if args.jobs > 1 and len(jobs) > 1:
        with ProcessPoolExecutor(max_workers=args.jobs) as pool:
            rows = list(pool.map(score_clip, jobs, chunksize=4))
    else:
        rows = [score_clip(j) for j in jobs]
    seconds = time.time() - start

    summary = summarize(rows)
    meta = {
        "dataset": args.dataset,
        "tracker": args.tracker,
        "date": time.strftime("%Y-%m-%d %H:%M"),
        "seconds": seconds,
    }
    comparison, regressed = None, False
    if args.baseline:
        baseline = json.loads(args.baseline.read_text())["summary"]
        comparison, regressed = compare(summary, baseline, args.tolerance)

    name = f"{args.dataset}_{args.tracker}" + (
        f"_{len(ids)}clips" if args.clip or args.limit else ""
    )
    md_path, json_path = write_report(args.out, name, meta, summary, rows, comparison)

    print(f"{args.tracker} on {args.dataset}: {len(rows)} clips in {seconds:.0f} s")
    for k in SUMMARY_METRICS:
        print(f"  {k:22s} {summary[k]:.4f}")
    if comparison:
        print("Against baseline:\n" + "\n".join(comparison))
    print(f"Report: {md_path}\n        {json_path}")
    return 1 if regressed else 0


if __name__ == "__main__":
    sys.exit(main())
