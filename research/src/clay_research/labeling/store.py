"""Where the owner's takes and their note labels live, and the label file format.

Audio:  data/owner_takes/<take>.wav            (gitignored: never commit audio)
Labels: research/labels/owner/<take>.json      (committed: hand-checked labels are precious)

Label file:
    {"take": "verse1", "verified": true,
     "notes": [{"onset": 0.52, "offset": 0.91, "midi": 62.0}, ...]}

Times are seconds from the start of the file; midi is the intended note (whole
semitones unless the singer meant something in between).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from clay_research.datasets.common import REPO_ROOT, Note, data_root

LABELS_DIR = REPO_ROOT / "research" / "labels" / "owner"
TAKE_NAME = re.compile(r"^[A-Za-z0-9 _.-]+$")


def audio_dir() -> Path:
    return data_root() / "owner_takes"


def take_names(directory: Path | None = None) -> list[str]:
    directory = directory or audio_dir()
    return sorted(p.stem for p in directory.glob("*.wav")) if directory.exists() else []


def check_name(take: str) -> str:
    """Reject names that could escape the folders (the labeler takes names from URLs)."""
    if not TAKE_NAME.match(take) or ".." in take:
        raise ValueError(f"bad take name: {take!r}")
    return take


def label_path(take: str, labels_dir: Path | None = None) -> Path:
    return (labels_dir or LABELS_DIR) / f"{check_name(take)}.json"


def load_labels(take: str, labels_dir: Path | None = None) -> tuple[list[Note], bool] | None:
    """(notes, verified) for a take, or None if it has no label file yet."""
    path = label_path(take, labels_dir)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    notes = [Note(float(n["onset"]), float(n["offset"]), float(n["midi"])) for n in data["notes"]]
    return notes, bool(data.get("verified", False))


def save_labels(
    take: str, notes: list[Note], verified: bool, labels_dir: Path | None = None
) -> Path:
    for n in notes:
        if not (0 <= n.onset < n.offset):
            raise ValueError(f"note must have 0 <= onset < offset: {n}")
        if not (0 < n.midi < 128):
            raise ValueError(f"note pitch out of MIDI range: {n}")
    path = label_path(take, labels_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(notes, key=lambda n: (n.onset, n.midi))
    payload = {
        "take": take,
        "verified": verified,
        "notes": [
            {"onset": round(n.onset, 4), "offset": round(n.offset, 4), "midi": round(n.midi, 2)}
            for n in ordered
        ],
    }
    path.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    return path
