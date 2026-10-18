#include "core/time_source.h"

#if defined(Q_OS_WIN)
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#elif defined(Q_OS_MACOS)
#include <mach/mach_time.h>
#else
#include <time.h>
#endif

namespace fc {

QDateTime SystemTimeSource::wallNow() const {
    return QDateTime::currentDateTime();
}

qint64 SystemTimeSource::elapsedNow() const {
#if defined(Q_OS_WIN)
    return static_cast<qint64>(GetTickCount64());
#elif defined(Q_OS_MACOS)
    static const mach_timebase_info_data_t scale = [] {
        mach_timebase_info_data_t value;
        mach_timebase_info(&value);
        return value;
    }();
    return static_cast<qint64>(static_cast<long double>(mach_continuous_time()) * scale.numer /
                               scale.denom / 1000000.0L);
#else
    timespec value{};
    clock_gettime(CLOCK_BOOTTIME, &value);
    return static_cast<qint64>(value.tv_sec) * 1000 + value.tv_nsec / 1000000;
#endif
}

} // namespace fc
