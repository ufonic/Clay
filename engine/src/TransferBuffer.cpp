#include "clay/engine/TransferBuffer.h"

#include <algorithm>
#include <cmath>
#include <cstring>

namespace clay::engine
{
namespace
{
// The span of [position, position + numSamples) that lies inside [0, capacity), as an
// offset into the block and a length.
struct Overlap
{
    int blockOffset;
    std::int64_t bufferIndex;
    int length;
};

Overlap overlap(std::int64_t position, int numSamples, std::int64_t capacity) noexcept
{
    const auto first = std::max<std::int64_t>(position, 0);
    const auto last = std::min<std::int64_t>(position + numSamples, capacity);
    if (last <= first)
        return {0, 0, 0};
    return {static_cast<int>(first - position), first, static_cast<int>(last - first)};
}
} // namespace

void TransferBuffer::prepare(int numChannels, double sampleRate, double maxSeconds)
{
    channels_ = std::max(numChannels, 0);
    capacity_ = static_cast<std::int64_t>(std::ceil(sampleRate * maxSeconds));
    data_.assign(static_cast<std::size_t>(channels_),
                 std::vector<float>(static_cast<std::size_t>(capacity_), 0.0f));
    clear();
}

void TransferBuffer::clear() noexcept
{
    start_.store(0, std::memory_order_release);
    end_.store(0, std::memory_order_release);
}

// clay:realtime-begin
void TransferBuffer::silence(std::int64_t from, std::int64_t to) noexcept
{
    for (auto& channel : data_)
        std::fill(channel.begin() + from, channel.begin() + to, 0.0f);
}

int TransferBuffer::write(std::int64_t position, const float* const* input, int numInputChannels,
                          int numSamples) noexcept
{
    const auto o = overlap(position, numSamples, capacity_);
    if (o.length == 0 || channels_ == 0)
        return 0;

    for (int ch = 0; ch < channels_; ++ch)
    {
        // A mono input feeds every stored channel.
        const float* src = input[std::min(ch, numInputChannels - 1)] + o.blockOffset;
        std::memcpy(data_[static_cast<std::size_t>(ch)].data() + o.bufferIndex, src,
                    static_cast<std::size_t>(o.length) * sizeof(float));
    }

    // Grow the captured range. If the host jumped, the range now spans a gap that was
    // never captured in this take: silence it so stale audio from an earlier take can't
    // play there. That is a bounded memset (at most the buffer's capacity), only on jumps.
    const auto blockStart = o.bufferIndex;
    const auto blockEnd = o.bufferIndex + o.length;
    if (!hasCapture())
    {
        start_.store(blockStart, std::memory_order_release);
        end_.store(blockEnd, std::memory_order_release);
        return o.length;
    }
    const auto start = start_.load(std::memory_order_relaxed);
    const auto end = end_.load(std::memory_order_relaxed);
    if (blockStart > end)
        silence(end, blockStart);
    if (blockEnd < start)
        silence(blockEnd, start);
    if (blockStart < start)
        start_.store(blockStart, std::memory_order_release);
    if (blockEnd > end)
        end_.store(blockEnd, std::memory_order_release);
    return o.length;
}

int TransferBuffer::read(std::int64_t position, float* const* output, int numOutputChannels,
                         int numSamples) const noexcept
{
    for (int ch = 0; ch < numOutputChannels; ++ch)
        std::fill(output[ch], output[ch] + numSamples, 0.0f);

    const auto start = capturedStart();
    const auto end = capturedEnd();
    if (end <= start || channels_ == 0)
        return 0;

    const auto first = std::max(position, start);
    const auto last = std::min(position + numSamples, end);
    if (last <= first)
        return 0;

    const auto blockOffset = static_cast<int>(first - position);
    const auto length = static_cast<int>(last - first);
    for (int ch = 0; ch < numOutputChannels; ++ch)
    {
        // A mono capture plays on every output channel.
        const auto& src = data_[static_cast<std::size_t>(std::min(ch, channels_ - 1))];
        std::memcpy(output[ch] + blockOffset, src.data() + first,
                    static_cast<std::size_t>(length) * sizeof(float));
    }
    return length;
}
// clay:realtime-end
} // namespace clay::engine
