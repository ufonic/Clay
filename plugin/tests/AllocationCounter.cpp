// Replaces the global allocation functions for the test executable only, so tests can
// prove audio-thread code never allocates. Never link this into the plugin itself.

#include "AllocationCounter.h"

#include <cstdlib>
#include <new>

namespace
{
thread_local std::size_t* currentCounter = nullptr;

void noteAllocation() noexcept
{
    if (currentCounter != nullptr)
        ++*currentCounter;
}

void* allocate(std::size_t size)
{
    noteAllocation();
    if (void* p = std::malloc(size == 0 ? 1 : size))
        return p;
    throw std::bad_alloc();
}

void* allocateAligned(std::size_t size, std::align_val_t alignment)
{
    noteAllocation();
    const auto align = static_cast<std::size_t>(alignment);
#if defined(_MSC_VER)
    if (void* p = _aligned_malloc(size == 0 ? 1 : size, align))
        return p;
#else
    const auto rounded = ((size == 0 ? 1 : size) + align - 1) / align * align;
    if (void* p = std::aligned_alloc(align, rounded))
        return p;
#endif
    throw std::bad_alloc();
}

void freeAligned(void* p) noexcept
{
#if defined(_MSC_VER)
    _aligned_free(p);
#else
    std::free(p);
#endif
}
} // namespace

namespace clay::test
{
ScopedAllocationCounter::ScopedAllocationCounter() : previous_(currentCounter)
{
    currentCounter = &count_;
}

ScopedAllocationCounter::~ScopedAllocationCounter()
{
    currentCounter = previous_;
}
} // namespace clay::test

void* operator new(std::size_t size)
{
    return allocate(size);
}
void* operator new[](std::size_t size)
{
    return allocate(size);
}
void* operator new(std::size_t size, const std::nothrow_t&) noexcept
{
    try
    {
        return allocate(size);
    }
    catch (...)
    {
        return nullptr;
    }
}
void* operator new[](std::size_t size, const std::nothrow_t&) noexcept
{
    try
    {
        return allocate(size);
    }
    catch (...)
    {
        return nullptr;
    }
}
void* operator new(std::size_t size, std::align_val_t a)
{
    return allocateAligned(size, a);
}
void* operator new[](std::size_t size, std::align_val_t a)
{
    return allocateAligned(size, a);
}

void operator delete(void* p) noexcept
{
    std::free(p);
}
void operator delete[](void* p) noexcept
{
    std::free(p);
}
void operator delete(void* p, std::size_t) noexcept
{
    std::free(p);
}
void operator delete[](void* p, std::size_t) noexcept
{
    std::free(p);
}
void operator delete(void* p, const std::nothrow_t&) noexcept
{
    std::free(p);
}
void operator delete[](void* p, const std::nothrow_t&) noexcept
{
    std::free(p);
}
void operator delete(void* p, std::align_val_t) noexcept
{
    freeAligned(p);
}
void operator delete[](void* p, std::align_val_t) noexcept
{
    freeAligned(p);
}
void operator delete(void* p, std::size_t, std::align_val_t) noexcept
{
    freeAligned(p);
}
void operator delete[](void* p, std::size_t, std::align_val_t) noexcept
{
    freeAligned(p);
}
