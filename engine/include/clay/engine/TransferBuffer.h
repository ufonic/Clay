#pragma once

#include <atomic>
#include <cstdint>
#include <vector>

namespace clay::engine
{
// Stores audio captured from the host by its position on the host timeline, so it can be
// played back in sync later ("Transfer"). Phase 0 spike: keeps everything in memory, up
// to a fixed length chosen in prepare().
//
// Threading: prepare() and clear() run on the message thread while audio is stopped.
// write()/read() run on the audio thread and never allocate, lock, or block. The
// captured range can be read from any thread.
class TransferBuffer
{
public:
    // Allocates room for maxSeconds of audio. Not real-time safe.
    void prepare(int numChannels, double sampleRate, double maxSeconds);
    void clear() noexcept;

    int numChannels() const noexcept { return channels_; }
    std::int64_t capacity() const noexcept { return capacity_; }

    // Copies numSamples per channel starting at timeline sample `position`. Parts outside
    // [0, capacity) are skipped. Returns how many samples were stored.
    int write(std::int64_t position, const float* const* input, int numInputChannels,
              int numSamples) noexcept;

    // Fills output with captured audio for timeline [position, position + numSamples).
    // Samples never captured (or out of range) come back as silence. Returns how many
    // samples were inside the captured range.
    int read(std::int64_t position, float* const* output, int numOutputChannels,
             int numSamples) const noexcept;

    // Captured timeline range [start, end); start >= end means nothing captured.
    std::int64_t capturedStart() const noexcept { return start_.load(std::memory_order_acquire); }
    std::int64_t capturedEnd() const noexcept { return end_.load(std::memory_order_acquire); }
    bool hasCapture() const noexcept { return capturedEnd() > capturedStart(); }

private:
    void silence(std::int64_t from, std::int64_t to) noexcept;

    int channels_ = 0;
    std::int64_t capacity_ = 0;
    std::vector<std::vector<float>> data_;
    std::atomic<std::int64_t> start_{0};
    std::atomic<std::int64_t> end_{0};
};
} // namespace clay::engine
