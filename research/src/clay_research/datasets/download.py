"""Download and extract datasets into data_root().

Usage (from the repo root):
    uv run --project research python -m clay_research.datasets.download mir1k vocalset

Downloads resume if interrupted and are checked against a published MD5 before
extracting. Audio is never committed to git (/data/* is gitignored).
"""

from __future__ import annotations

import argparse
import hashlib
import platform
import shutil
import struct
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

from .common import data_root


@dataclass(frozen=True)
class Source:
    name: str
    url: str
    filename: str
    md5: str
    license: str
    home: str
    keep_prefixes: tuple[str, ...] = ()  # zip only: extract members starting with these


SOURCES: dict[str, Source] = {
    "mir1k": Source(
        name="mir1k",
        # The original mirlab.org link is dead; this Figshare copy is the original archive.
        url="https://ndownloader.figshare.com/files/10256751",
        filename="MIR-1K.rar",
        md5="1810d01457ccbb84a0b41c4da53eee74",
        license="CC BY 4.0 (Figshare mirror)",
        home="https://figshare.com/articles/dataset/MIR-1K_rar/5802891",
    ),
    "vocalset": Source(
        name="vocalset",
        url="https://zenodo.org/api/records/1442513/files/VocalSet1-2.zip/content",
        filename="VocalSet1-2.zip",
        md5="c5e5efab412637fc94972b93c343a2f0",
        license="CC BY 4.0",
        home="https://zenodo.org/records/1442513",
        keep_prefixes=(
            "data_by_singer/",
            "readme-anon.txt",
            "train_singers_technique.txt",
            "test_singers_technique.txt",
        ),
    ),
}


def md5sum(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


def fetch(url: str, dest: Path) -> None:
    """Download url to dest, resuming a partial file if one exists."""
    have = dest.stat().st_size if dest.exists() else 0
    req = urllib.request.Request(url, headers={"Range": f"bytes={have}-"} if have else {})
    try:
        resp = urllib.request.urlopen(req)
    except urllib.error.HTTPError as e:
        if e.code == 416:  # range not satisfiable: already complete
            return
        raise
    with resp:
        resuming = have and resp.status == 206
        total = int(resp.headers.get("Content-Length", 0)) + (have if resuming else 0)
        mode = "ab" if resuming else "wb"
        done = have if resuming else 0
        with dest.open(mode) as f:
            while block := resp.read(1 << 20):
                f.write(block)
                done += len(block)
                if total:
                    print(f"\r  {dest.name}: {done / total:6.1%} of {total / 1e9:.2f} GB", end="")
    print()


def is_junk(member: str) -> bool:
    return member.startswith("__MACOSX/") or member.rsplit("/", 1)[-1] == ".DS_Store"


LOCAL_HEADER = struct.Struct("<4s22xHH")  # signature ... name length, extra length


def repair_wrapped_offsets(z: zipfile.ZipFile) -> int:
    """Fix member offsets in >4 GB zips written without ZIP64 (e.g. macOS Archive Utility).

    Such archives store each member's position in 32 bits, so positions past 4 GB wrap,
    and Python's zipfile then mis-locates some members ("Bad magic number for file
    header"). For each member, try its offset and ±4 GB and keep the one where the
    member's own local header, with the matching file name, actually is. Returns how
    many offsets were changed; raises if a member can't be found.
    """
    size = z.fp.seek(0, 2)
    changed = 0
    for info in z.infolist():
        for candidate in (
            info.header_offset,
            info.header_offset - (1 << 32),
            info.header_offset + (1 << 32),
        ):
            if not 0 <= candidate <= size - LOCAL_HEADER.size:
                continue
            z.fp.seek(candidate)
            signature, name_len, _ = LOCAL_HEADER.unpack(z.fp.read(LOCAL_HEADER.size))
            if signature != b"PK\x03\x04":
                continue
            raw_name = z.fp.read(name_len)
            if (
                raw_name.decode("utf-8", "replace") == info.filename
                or raw_name.decode("cp437", "replace") == info.filename
            ):
                changed += candidate != info.header_offset
                info.header_offset = candidate
                break
        else:
            raise zipfile.BadZipFile(f"can't locate {info.filename!r} in {z.filename}")
    return changed


def extract(archive: Path, out_dir: Path, keep_prefixes: tuple[str, ...]) -> None:
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as z:
            if repaired := repair_wrapped_offsets(z):
                print(f"  repaired {repaired} wrapped offsets in {archive.name}")
            members = [
                m
                for m in z.namelist()
                if not is_junk(m) and (not keep_prefixes or m.startswith(keep_prefixes))
            ]
            z.extractall(out_dir, members)
    elif archive.suffix == ".rar":
        # bsdtar (Windows 10+ System32\tar.exe, macOS /usr/bin/tar) reads RAR; GNU tar does not.
        tar = (
            r"C:\Windows\System32\tar.exe"
            if platform.system() == "Windows"
            else shutil.which("bsdtar") or "/usr/bin/tar"
        )
        subprocess.run([tar, "-xf", str(archive), "-C", str(out_dir)], check=True)
    else:
        raise ValueError(f"don't know how to extract {archive}")


def install(source: Source, root: Path) -> Path:
    out_dir = root / source.name
    out_dir.mkdir(parents=True, exist_ok=True)
    marker = out_dir / ".complete"
    if marker.exists():
        print(f"{source.name}: already installed in {out_dir}")
        return out_dir

    archive = out_dir / source.filename
    print(f"{source.name}: downloading {source.url}")
    fetch(source.url, archive)
    print(f"{source.name}: verifying MD5")
    actual = md5sum(archive)
    if actual != source.md5:
        raise RuntimeError(
            f"{source.name}: MD5 mismatch (got {actual}, expected {source.md5}); "
            f"delete {archive} and retry"
        )
    print(f"{source.name}: extracting")
    extract(archive, out_dir, source.keep_prefixes)
    marker.write_text(f"{source.home}\nlicense: {source.license}\n")
    print(f"{source.name}: done -> {out_dir} (you may delete {archive.name} to save space)")
    return out_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("datasets", nargs="+", choices=sorted(SOURCES))
    args = parser.parse_args(argv)
    for name in args.datasets:
        install(SOURCES[name], data_root())
    return 0


if __name__ == "__main__":
    sys.exit(main())
