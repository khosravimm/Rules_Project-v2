from __future__ import annotations

from datetime import datetime, timedelta, timezone

from api.config import TIMEFRAME_SECONDS


def compute_time_window_around(center_ts_utc: datetime, timeframe: str, before_bars: int, after_bars: int) -> tuple[datetime, datetime]:
    """Return (start_utc, end_utc) around a center timestamp for the given timeframe."""
    if timeframe not in TIMEFRAME_SECONDS:
        raise ValueError(f"Unsupported timeframe '{timeframe}'")
    if before_bars < 0 or after_bars < 0:
        raise ValueError("before_bars and after_bars must be non-negative")

    if center_ts_utc.tzinfo is None:
        center_ts_utc = center_ts_utc.replace(tzinfo=timezone.utc)
    else:
        center_ts_utc = center_ts_utc.astimezone(timezone.utc)

    delta = timedelta(seconds=TIMEFRAME_SECONDS[timeframe])
    start = center_ts_utc - before_bars * delta
    end = center_ts_utc + after_bars * delta
    return start, end


__all__ = ["compute_time_window_around"]
