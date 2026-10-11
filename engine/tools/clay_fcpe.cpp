// clay_fcpe: run the C++ FCPE tracker on raw audio (for parity checks on real datasets,
// driven by `python -m clay_research.parity.fcpe_dataset`).
//
// Usage: clay_fcpe <model.onnx> <sample_rate> <in.f32> <out.f32> [<in.f32> <out.f32> ...]
// Input: mono little-endian float32 samples. Output: pitch in Hz per 10 ms frame (0 =
// unvoiced), little-endian float32. Several pairs share one loaded model.

#include "clay/analysis/Fcpe.h"

#include <cstdio>
#include <cstdlib>
#include <exception>
#include <fstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace
{
std::vector<float> readFloats(const std::string& path)
{
    std::ifstream in(path, std::ios::binary | std::ios::ate);
    if (!in)
        throw std::runtime_error("cannot read " + path);
    const auto bytes = static_cast<std::size_t>(in.tellg());
    std::vector<float> v(bytes / sizeof(float));
    in.seekg(0);
    in.read(reinterpret_cast<char*>(v.data()), static_cast<std::streamsize>(v.size() * sizeof(float)));
    return v;
}

void writeFloats(const std::string& path, const std::vector<float>& v)
{
    std::ofstream out(path, std::ios::binary);
    if (!out)
        throw std::runtime_error("cannot write " + path);
    out.write(reinterpret_cast<const char*>(v.data()),
              static_cast<std::streamsize>(v.size() * sizeof(float)));
}
} // namespace

int main(int argc, char** argv)
{
    if (argc < 5 || (argc - 3) % 2 != 0)
    {
        std::fprintf(stderr, "usage: clay_fcpe <model.onnx> <sample_rate> <in.f32> <out.f32> [...]\n");
        return 2;
    }
    try
    {
        const clay::analysis::FcpeTracker tracker(argv[1]);
        const int rate = std::atoi(argv[2]);
        for (int i = 3; i + 1 < argc; i += 2)
            writeFloats(argv[i + 1], tracker.track(readFloats(argv[i]), rate).f0Hz);
        return 0;
    }
    catch (const std::exception& e)
    {
        std::fprintf(stderr, "clay_fcpe: %s\n", e.what());
        return 1;
    }
}
