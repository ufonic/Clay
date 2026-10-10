"""The lint must catch seeded violations (roadmap task 0.9) and stay quiet on clean code."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rt_lint  # noqa: E402


def lint(tmp_path, body: str) -> list[str]:
    f = tmp_path / "x.cpp"
    f.write_text(body, encoding="utf-8")
    return [finding.message for finding in rt_lint.lint_file(f)]


def region(code: str) -> str:
    return f"// clay:realtime-begin\nvoid f()\n{{\n{code}\n}}\n// clay:realtime-end\n"


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("auto* p = new float[64];", "heap allocation (new)"),
        ("delete p;", "heap deallocation (delete)"),
        ("void* p = malloc(16);", "C heap call"),
        ("auto p = std::make_unique<int>(1);", "heap allocation (make_unique/shared)"),
        ("v.push_back(1.0f);", "container growth can allocate"),
        ("std::vector<float> tmp(64);", "std type that allocates"),
        ('auto s = juce::String("x");', "juce::String allocates"),
        ("std::lock_guard<std::mutex> g(m);", "lock / blocking primitive"),
        ("const juce::ScopedLock sl(cs);", "JUCE lock"),
        ("std::this_thread::sleep_for(1ms);", "sleep"),
        ('printf("%d", x);', "console output"),
        ('DBG("block");', "logging"),
        ('auto* f = fopen("a", "r");', "file I/O"),
        ('throw std::runtime_error("x");', "exceptions (may allocate)"),
        ("while (true) {}", "unbounded loop"),
    ],
)
def test_catches_seeded_violation(tmp_path, code, expected):
    assert expected in lint(tmp_path, region(code))


def test_clean_realtime_code_passes(tmp_path):
    code = """
    juce::ScopedNoDenormals noDenormals;
    for (int ch = 0; ch < numChannels; ++ch)
        buffer.clear(ch, 0, numSamples);
    fifo.push(value); // lock-free FIFO, fixed capacity
    // new, delete, and printf in a comment are fine
    const char* label = "new delete mutex";
    """
    assert lint(tmp_path, region(code)) == []


def test_code_outside_regions_is_not_checked(tmp_path):
    assert lint(tmp_path, "void setup() { auto* p = new int(3); delete p; }\n") == []


def test_allow_comment_suppresses_one_line(tmp_path):
    code = "auto* p = new float[8]; // rt-lint: allow test-only scratch buffer"
    assert lint(tmp_path, region(code)) == []


def test_callback_outside_region_is_flagged(tmp_path):
    body = "void Proc::processBlock(juce::AudioBuffer<float>& b, juce::MidiBuffer& m)\n{\n}\n"
    assert lint(tmp_path, body) == ["audio callback outside a clay:realtime-begin region"]


def test_callback_declarations_and_calls_are_not_flagged(tmp_path):
    body = (
        "void processBlock(juce::AudioBuffer<float>&, juce::MidiBuffer&) override;\n"
        "using AudioProcessor::processBlock;\n"
        "void run() { proc.processBlock(buffer,\n midi); other->process(ctx); }\n"
    )
    assert lint(tmp_path, body) == []


def test_unbalanced_markers(tmp_path):
    assert "realtime-begin never closed" in lint(tmp_path, "// clay:realtime-begin\nint x;\n")
    assert "realtime-end without begin" in lint(tmp_path, "// clay:realtime-end\n")


def test_repo_code_is_clean():
    repo = Path(__file__).resolve().parents[2]
    assert rt_lint.main([str(repo / "engine"), str(repo / "plugin")]) == 0
