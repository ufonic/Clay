#pragma once

#include <string_view>

namespace clay::engine
{
struct Version
{
    int major;
    int minor;
    int patch;
};

// The engine's version, taken from the CMake project version.
Version version() noexcept;

// The same version as "major.minor.patch".
std::string_view versionString() noexcept;
} // namespace clay::engine
