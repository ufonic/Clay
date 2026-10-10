configure_file(src/BuildInfo.h.in "${CMAKE_CURRENT_BINARY_DIR}/generated/clay/engine/BuildInfo.h" @ONLY)

add_library(clay_engine STATIC
    src/Version.cpp
)
add_library(clay::engine ALIAS clay_engine)

target_include_directories(clay_engine
    PUBLIC
        include
        "${CMAKE_CURRENT_BINARY_DIR}/generated"
)
clay_set_warnings(clay_engine)

if(CLAY_BUILD_TESTS)
    add_executable(clay_engine_tests
        tests/VersionTests.cpp
    )
    target_link_libraries(clay_engine_tests PRIVATE clay::engine Catch2::Catch2WithMain)
    clay_set_warnings(clay_engine_tests)
    # PRE_TEST: discover tests when ctest runs, not at build time, so cross-built
    # slices of the universal binary don't have to execute during the build.
    catch_discover_tests(clay_engine_tests DISCOVERY_MODE PRE_TEST)
endif()
