#pragma once

#include <cstddef>

namespace clay::test
{
// Counts heap allocations made on the current thread while it is alive.
// Works because the test executable replaces global operator new (AllocationCounter.cpp).
class ScopedAllocationCounter
{
public:
    ScopedAllocationCounter();
    ~ScopedAllocationCounter();

    ScopedAllocationCounter(const ScopedAllocationCounter&) = delete;
    ScopedAllocationCounter& operator=(const ScopedAllocationCounter&) = delete;

    std::size_t count() const noexcept { return count_; }

private:
    std::size_t count_ = 0;
    std::size_t* previous_ = nullptr;
};
} // namespace clay::test
