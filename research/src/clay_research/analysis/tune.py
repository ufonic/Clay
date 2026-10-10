"""Tune the HMM segmenter on vocadito with 2-fold cross-validation.

Usage (from the repo root):
    uv run --project research python -m clay_research.analysis.tune --tracker fcpe --trials 200

Honest scoring: the clips are split into two halves; parameters are searched on one half
and scored on the other half they never saw, then the halves swap. The mean held-out
score is the number to trust (and the one compared with the Phase 1 gate). Finally the
search runs once on all clips to produce the parameters to ship; that in-sample score is
reported but flatters itself, so it is not the gate number.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import math
import os
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from clay_research.datasets import vocadito
from clay_research.datasets.common import REPO_ROOT
from clay_research.harness.metrics import note_scores
from clay_research.harness.trackers import TRACKERS

from .notes import Features, SegmenterParams, decode, features

# (low, high, log-scale?) search ranges for each tunable parameter.
SPACE: dict[str, tuple[float, float, bool]] = {
    "sustain_sigma": (0.3, 1.2, False),
    "attack_sigma": (0.6, 3.0, False),
    "unvoiced_in_note": (0.01, 0.4, True),
    "voiced_in_silence": (0.005, 0.4, True),
    "p_stay_sustain": (0.95, 0.997, False),
    "p_stay_attack": (0.2, 0.9, False),
    "p_note_change": (1e-4, 3e-2, True),
    "p_reattack": (1e-5, 1e-2, True),
    "p_start": (1e-3, 1e-1, True),
    "onset_weight": (0.0, 6.0, False),
    "min_note_s": (0.03, 0.15, False),
    "trim_fraction": (0.0, 0.3, False),
}

_cache: dict[str, tuple[Features, list, list]] = {}


def _load(clip_id: str, tracker: str) -> tuple[Features, list, list]:
    if clip_id not in _cache:
        clip = vocadito.load(clip_id)
        track = TRACKERS[tracker](clip.audio, clip.sample_rate)
        f = features(track, clip.audio, clip.sample_rate)
        _cache[clip_id] = (
            f,
            vocadito.load_notes(clip_id, "A1"),
            vocadito.load_notes(clip_id, "A2"),
        )
    return _cache[clip_id]


def _score_params(args: tuple[dict, list[str], str]) -> float:
    values, ids, tracker = args
    p = SegmenterParams(**values)
    f1s = []
    for cid in ids:
        f, a1, a2 = _load(cid, tracker)
        est = decode(f, p)
        f1s.append((note_scores(a1, est).f1 + note_scores(a2, est).f1) / 2)
    return float(np.mean(f1s))


def _sample(rng: random.Random) -> dict:
    out = {}
    for name, (lo, hi, log) in SPACE.items():
        out[name] = (
            math.exp(rng.uniform(math.log(lo), math.log(hi))) if log else rng.uniform(lo, hi)
        )
    return out


def search(ids: list[str], tracker: str, trials: int, seed: int, pool) -> tuple[dict, float]:
    """Random search (plus the defaults as trial 0); returns the best values and score."""
    rng = random.Random(seed)
    defaults = {k: getattr(SegmenterParams(), k) for k in SPACE}
    candidates = [defaults] + [_sample(rng) for _ in range(trials - 1)]
    scores = list(pool.map(_score_params, [(c, ids, tracker) for c in candidates]))
    best = int(np.argmax(scores))
    # Refine: small random steps around the best point.
    center = candidates[best]
    local = []
    for _ in range(max(trials // 4, 8)):
        c = {}
        for name, (lo, hi, log) in SPACE.items():
            v = center[name]
            if log:
                v = math.exp(math.log(v) + rng.gauss(0, 0.3))
            else:
                v = v + rng.gauss(0, 0.1 * (hi - lo))
            c[name] = min(max(v, lo), hi)
        local.append(c)
    local_scores = list(pool.map(_score_params, [(c, ids, tracker) for c in local]))
    if local and max(local_scores) > scores[best]:
        i = int(np.argmax(local_scores))
        return local[i], local_scores[i]
    return candidates[best], scores[best]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tracker", choices=sorted(TRACKERS), default="fcpe")
    ap.add_argument("--trials", type=int, default=200)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    ap.add_argument(
        "--out", type=Path, default=REPO_ROOT / "research" / "src" / "clay_research" / "analysis"
    )
    args = ap.parse_args(argv)

    ids = vocadito.clip_ids()
    rng = random.Random(args.seed)
    shuffled = ids[:]
    rng.shuffle(shuffled)
    folds = [sorted(shuffled[::2], key=int), sorted(shuffled[1::2], key=int)]

    start = time.time()
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        default_all = _score_params(
            ({k: getattr(SegmenterParams(), k) for k in SPACE}, ids, args.tracker)
        )
        held_out = []
        for k in (0, 1):
            train, test = folds[k], folds[1 - k]
            best, train_score = search(train, args.tracker, args.trials, args.seed + k, pool)
            test_score = _score_params((best, test, args.tracker))
            held_out.append(test_score)
            print(
                f"fold {k}: tuned on {len(train)} clips {train_score:.4f} -> "
                f"held-out {len(test)} clips {test_score:.4f}"
            )
        cv = float(np.mean(held_out))
        final, in_sample = search(ids, args.tracker, args.trials, args.seed + 99, pool)

    result = {
        "tracker": args.tracker,
        "trials": args.trials,
        "date": time.strftime("%Y-%m-%d %H:%M"),
        "default_params_score_all": default_all,
        "cross_validated_score": cv,
        "in_sample_score": in_sample,
        "human_agreement": vocadito.HUMAN_AGREEMENT_F1,
        "params": {**dataclasses.asdict(SegmenterParams()), **final},
    }
    path = args.out / f"segmenter_params_{args.tracker}.json"
    path.write_text(json.dumps(result, indent=1) + "\n")
    print(f"defaults on all clips:        {default_all:.4f}")
    print(
        f"cross-validated (gate number): {cv:.4f}  vs human agreement "
        f"{vocadito.HUMAN_AGREEMENT_F1:.3f}"
    )
    print(f"tuned on all clips (in-sample): {in_sample:.4f}")
    print(f"saved {path}  ({time.time() - start:.0f} s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
