"""Real-time safety lint for Clay's C++ audio-thread code.

Audio-thread code must sit between marker comments:

    // clay:realtime-begin
    void Processor::processBlock (...) { ... }
    // clay:realtime-end

Inside a marked region the lint rejects anything that can allocate, lock, block, do
I/O, or log (CLAUDE.md rule 2). It also fails if a known audio callback (processBlock,
process, renderNextBlock, getNextAudioBlock) is defined outside a marked region, so new
callbacks can't skip the check by accident.

To allow one line on purpose, end it with:  // rt-lint: allow <reason>

This is a text scan, not a compiler: it catches the common mistakes, and the
allocation-counting stress test catches what slips past it.

Usage:  python tools/rt_lint.py engine plugin
Exit code 1 if anything is found.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

BEGIN = "clay:realtime-begin"
END = "clay:realtime-end"
ALLOW = "rt-lint: allow"
SOURCE_SUFFIXES = {".h", ".hpp", ".cpp", ".cc", ".mm"}

# (pattern, what's wrong). Patterns match code with comments and strings removed.
BANNED: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bnew\b(?!\s*\()"), "heap allocation (new)"),
    (re.compile(r"\bdelete\b"), "heap deallocation (delete)"),
    (re.compile(r"\b(malloc|calloc|realloc|free|aligned_alloc)\s*\("), "C heap call"),
    (re.compile(r"\bmake_(unique|shared)\b"), "heap allocation (make_unique/shared)"),
    (
        re.compile(r"\.\s*(push_back|emplace_back|emplace|insert|resize|reserve|append)\s*\("),
        "container growth can allocate",
    ),
    (
        re.compile(r"\bstd::(string|vector|map|unordered_map|list|deque|function)\b"),
        "std type that allocates",
    ),
    (re.compile(r"\bjuce::String\b|\bString\s*\("), "juce::String allocates"),
    (
        re.compile(
            r"\b(mutex|recursive_mutex|shared_mutex|lock_guard|unique_lock|scoped_lock"
            r"|condition_variable)\b"
        ),
        "lock / blocking primitive",
    ),
    (
        re.compile(r"\b(CriticalSection|ScopedLock|SpinLock|ReadWriteLock|WaitableEvent)\b"),
        "JUCE lock",
    ),
    (re.compile(r"\.\s*(lock|wait|wait_for|wait_until|join)\s*\(\s*\)"), "blocking call"),
    (re.compile(r"\b(sleep_for|sleep_until|Sleep|usleep)\b|\bThread::sleep\b"), "sleep"),
    (re.compile(r"\b(cout|cerr|clog|printf|fprintf|puts|OutputDebugString)\b"), "console output"),
    (re.compile(r"\b(DBG|Logger::|jassertfalse_log)\b"), "logging"),
    (
        re.compile(
            r"\b(fopen|fread|fwrite|ifstream|ofstream|fstream|FileInputStream"
            r"|FileOutputStream)\b|\bFile\s*\("
        ),
        "file I/O",
    ),
    (re.compile(r"\b(URL|StreamingSocket|DatagramSocket|WebInputStream)\b"), "network I/O"),
    (re.compile(r"\bthrow\b"), "exceptions (may allocate)"),
    (re.compile(r"\bwhile\s*\(\s*(true|1)\s*\)|\bfor\s*\(\s*;\s*;\s*\)"), "unbounded loop"),
    (re.compile(r"\bdynamic_cast\b|\btypeid\b"), "RTTI (can lock in some runtimes)"),
]

# A callback *definition*: the name followed by "(", not called through . or ->, on a line
# with no ";" (declarations and calls end in ";"; definitions continue with a body).
CALLBACK = re.compile(
    r"(?<!\.)(?<!->)\b(processBlock|process|renderNextBlock|getNextAudioBlock)\s*\("
)


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    message: str
    code: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.message}\n    {self.code.strip()}"


def strip_comments_and_strings(line: str, in_block_comment: bool) -> tuple[str, bool]:
    """Remove // and /* */ comments and string/char literals from one line."""
    out, i = [], 0
    while i < len(line):
        if in_block_comment:
            end = line.find("*/", i)
            if end < 0:
                return "".join(out), True
            i, in_block_comment = end + 2, False
            continue
        two = line[i : i + 2]
        if two == "//":
            break
        if two == "/*":
            in_block_comment, i = True, i + 2
            continue
        if line[i] in "\"'":
            quote, i = line[i], i + 1
            while i < len(line) and line[i] != quote:
                i += 2 if line[i] == "\\" else 1
            out.append(quote * 2)
            i += 1
            continue
        out.append(line[i])
        i += 1
    return "".join(out), in_block_comment


def lint_file(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    in_region, region_start, in_comment = False, 0, False
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if BEGIN in raw:
            if in_region:
                findings.append(Finding(path, number, "nested realtime-begin", raw))
            in_region, region_start = True, number
            continue
        if END in raw:
            if not in_region:
                findings.append(Finding(path, number, "realtime-end without begin", raw))
            in_region = False
            continue

        code, in_comment = strip_comments_and_strings(raw, in_comment)
        if not code.strip():
            continue
        if not in_region and CALLBACK.search(code) and ";" not in code:
            findings.append(Finding(path, number, f"audio callback outside a {BEGIN} region", raw))
        if in_region and ALLOW not in raw:
            for pattern, message in BANNED:
                if pattern.search(code):
                    findings.append(Finding(path, number, message, raw))
    if in_region:
        findings.append(Finding(path, region_start, "realtime-begin never closed", ""))
    return findings


def source_files(roots: list[Path]) -> list[Path]:
    files = []
    for root in roots:
        if root.is_file():
            files.append(root)
        else:
            files += [p for p in root.rglob("*") if p.suffix in SOURCE_SUFFIXES]
    return sorted(f for f in files if "third_party" not in f.parts and "build" not in f.parts)


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    roots = [Path(a) for a in (args or ["engine", "plugin"])]
    files = source_files(roots)
    findings = [f for path in files for f in lint_file(path)]
    for finding in findings:
        print(finding)
    print(f"rt_lint: {len(files)} files, {len(findings)} problem(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
