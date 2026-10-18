#pragma once

#include <QDateTime>

namespace fc {

class TimeSource {
public:
    virtual ~TimeSource() = default;
    virtual QDateTime wallNow() const = 0;
    // Monotonic milliseconds including system suspend, never serialized.
    virtual qint64 elapsedNow() const = 0;
};

class SystemTimeSource final : public TimeSource {
public:
    QDateTime wallNow() const override;
    qint64 elapsedNow() const override;
};

} // namespace fc
