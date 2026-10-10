#include "clay/engine/Version.h"

#include <catch2/catch_test_macros.hpp>
#include <string>

TEST_CASE("Version string matches the numeric version", "[version]")
{
    const auto v = clay::engine::version();
    const auto expected =
        std::to_string(v.major) + "." + std::to_string(v.minor) + "." + std::to_string(v.patch);

    CHECK(clay::engine::versionString() == expected);
}

TEST_CASE("Version is not 0.0.0", "[version]")
{
    const auto v = clay::engine::version();
    CHECK((v.major + v.minor + v.patch) > 0);
}
